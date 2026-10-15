import base64
import logging
import os
from dataclasses import dataclass
from functools import cache
from typing import cast

import requests
from kubernetes import client, config
from kubernetes.client import ApiException

from skip_capability_sdk import (
    Binding,
    Claim,
    InvalidClaimError,
    SecretRef,
    TransientError,
)

from .client import LiteLLMClient, LiteLLMError

CAPABILITY_TYPE = "llm-access"
SECRET_KEY = "api-key"
# Endpoint liegt zusaetzlich im Secret, damit Workloads Endpoint und Key ueber
# dieselbe secretKeyRef beziehen koennen, ohne den Claim-Status zu lesen.
ENDPOINT_KEY = "endpoint"
MANAGED_BY = "skip-platform"

logger = logging.getLogger(__name__)


@cache
def core_v1() -> client.CoreV1Api:
    """Lazy konfigurierter CoreV1-Client (erst In-Cluster, dann Kubeconfig als Fallback)."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    return client.CoreV1Api()


@dataclass(frozen=True)
class DesiredKey:
    """Soll-Zustand des virtuellen Keys, abgeleitet aus dem Claim."""

    alias: str
    models: tuple[str, ...]
    secret_name: str


def ensure_secret(*, owner: Claim, name: str, api_key: str, endpoint: str) -> None:
    """Erstellt oder aktualisiert das Secret mit dem rohen virtuellen Key und dem Endpoint.

    Das Secret gehört dem CapabilityClaim, damit die Garbage Collection es
    zusammen mit dem Claim entfernt.
    """
    owner_reference = client.V1OwnerReference(
        api_version=owner.api_version,
        kind=owner.kind,
        name=owner.name,
        uid=owner.uid,
        controller=True,
        block_owner_deletion=True,
    )

    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=name,
            namespace=owner.namespace,
            labels={
                "app.kubernetes.io/managed-by": MANAGED_BY,
                "platform.skip.io/capability": CAPABILITY_TYPE,
            },
            owner_references=[owner_reference],
        ),
        type="Opaque",
        string_data={SECRET_KEY: api_key, ENDPOINT_KEY: endpoint},
    )

    try:
        core_v1().patch_namespaced_secret(
            name=name, namespace=owner.namespace, body=secret
        )
    except ApiException as e:
        if e.status != 404:
            raise

        core_v1().create_namespaced_secret(namespace=owner.namespace, body=secret)


def read_secret_value(*, namespace: str, name: str, key: str) -> str | None:
    """Liefert den dekodierten Wert unter `key` oder None, falls nicht vorhanden."""
    try:
        secret = cast(
            client.V1Secret,
            core_v1().read_namespaced_secret(name=name, namespace=namespace),
        )
    except ApiException as e:
        if e.status == 404:
            return None
        raise

    encoded = (secret.data or {}).get(key)

    if encoded is None:
        return None

    return base64.b64decode(encoded).decode("utf-8")


def build_key_alias(*, namespace: str, claim_name: str) -> str:
    """LiteLLM-Key-Aliase müssen global eindeutig sein; Namespace + Name reicht dafür."""
    return f"skip-{namespace}-{claim_name}"


class LiteLLMCapability:
    """Stellt virtuelle LiteLLM-Keys für CapabilityClaims vom Typ `llm-access` bereit."""

    def __init__(
        self,
        litellm: LiteLLMClient | None = None,
        public_base_url: str | None = None,
    ) -> None:
        self._litellm = litellm
        self._public_base_url = public_base_url

    @property
    def litellm(self) -> LiteLLMClient:
        if self._litellm is None:
            self._litellm = LiteLLMClient.from_env()
        return self._litellm

    @property
    def public_base_url(self) -> str:
        """Endpunkt für die Workloads; Standard ist die interne Proxy-URL."""
        if self._public_base_url is None:
            self._public_base_url = os.environ.get(
                "LITELLM_PUBLIC_BASE_URL", self.litellm.base_url
            )
        return self._public_base_url

    def initialize(self) -> None:
        """Prüft beim Start, ob LiteLLM mit dem konfigurierten Master-Key erreichbar ist."""
        try:
            self.litellm.check_connection()
        except (LiteLLMError, requests.RequestException) as exc:
            raise TransientError(f"Cannot connect to LiteLLM: {exc}") from exc

        logger.info("Connected to LiteLLM at %s", self.litellm.base_url)

    def provision(self, claim: Claim) -> Binding:
        """Stellt sicher, dass:

          1. ein virtueller LiteLLM-Key existiert,
          2. seine erlaubten Modelle zum CapabilityClaim passen,
          3. der rohe Key in einem Kubernetes-Secret liegt.

        Das Kubernetes-Secret ist die lokale Quelle der Wahrheit für den rohen Key.
        """
        desired = self._desired_key(claim)
        binding = Binding(
            endpoint=self.public_base_url,
            secret_ref=SecretRef(name=desired.secret_name, key=SECRET_KEY),
        )

        try:
            existing_key = read_secret_value(
                namespace=claim.namespace, name=desired.secret_name, key=SECRET_KEY
            )

            # Normalfall: Wir kennen den rohen Key und gleichen nur die Policy ab.
            # Das Secret wird trotzdem gepatcht, damit der Endpoint-Schluessel
            # auch bei aelteren Secrets vorhanden und aktuell ist.
            if existing_key and self._sync_policy(claim, desired, existing_key):
                ensure_secret(
                    owner=claim,
                    name=desired.secret_name,
                    api_key=existing_key,
                    endpoint=binding.endpoint,
                )
                return binding

            # Kein brauchbarer Key: entweder erster Lauf, Secret verloren oder
            # LiteLLM kennt den Key nicht mehr.
            self._recreate_key(claim, desired, endpoint=binding.endpoint)
        except (LiteLLMError, requests.RequestException, ApiException) as exc:
            raise TransientError(f"LiteLLM provisioning failed: {exc}") from exc

        return binding

    def cleanup(self, claim: Claim) -> None:
        key_alias = build_key_alias(namespace=claim.namespace, claim_name=claim.name)

        try:
            self.litellm.delete_key_by_alias(key_alias=key_alias)
        except (LiteLLMError, requests.RequestException) as exc:
            raise TransientError(
                f"Could not remove LiteLLM virtual key: {exc}"
            ) from exc

        logger.info(
            "Deleted LiteLLM virtual key for %s/%s", claim.namespace, claim.name
        )

    @staticmethod
    def _desired_key(claim: Claim) -> DesiredKey:
        """Leitet den Soll-Zustand aus dem Claim ab und validiert das Spec."""
        models = claim.properties.get("models")

        if not isinstance(models, list) or not models:
            raise InvalidClaimError(
                "spec.properties.models must contain at least one model"
            )

        if not all(isinstance(model, str) for model in models):
            raise InvalidClaimError("spec.properties.models must be a list of strings")

        return DesiredKey(
            alias=build_key_alias(namespace=claim.namespace, claim_name=claim.name),
            models=tuple(models),
            secret_name=f"{claim.name}-credentials",
        )

    def _sync_policy(
        self, claim: Claim, desired: DesiredKey, existing_key: str
    ) -> bool:
        """Gleicht die LiteLLM-Policy (z. B. Modellliste) des bekannten Keys ab.

        Liefert False, wenn LiteLLM den Key nicht mehr kennt und er neu
        angelegt werden muss.
        """
        logger.info(
            "LiteLLM key exists for %s/%s; reconciling policy",
            claim.namespace,
            claim.name,
        )

        if self.litellm.update_key(
            key=existing_key, key_alias=desired.alias, models=list(desired.models)
        ):
            return True

        logger.warning(
            "Secret exists but LiteLLM lost the key for %s/%s; replacing",
            claim.namespace,
            claim.name,
        )

        return False

    def _recreate_key(
        self, claim: Claim, desired: DesiredKey, *, endpoint: str
    ) -> None:
        """Legt Key und Secret neu an."""
        self.litellm.delete_key_by_alias(key_alias=desired.alias)

        new_key = self.litellm.generate_key(
            key_alias=desired.alias,
            models=list(desired.models),
            metadata={
                "managed-by": MANAGED_BY,
                "kubernetes-namespace": claim.namespace,
                "capability-claim": claim.name,
            },
        )

        ensure_secret(
            owner=claim, name=desired.secret_name, api_key=new_key, endpoint=endpoint
        )

        logger.info(
            "Created LiteLLM virtual key for %s/%s", claim.namespace, claim.name
        )
