from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from kubernetes import client

from auth.authentik import AuthentikClient, app_group_name
from auth.dtos import AuthenticatedUser
from auth.entitlements import EntitlementProvider, check_deployment
from auth.service import allowed_namespaces_for, is_admin, user_namespace_name
from templates.service import AbstractTemplateService

from .dtos import AppMember, AppMembers, ComponentStatus, DeployRequest, Deployment
from .errors import (
    DeploymentConflictError,
    DeploymentForbiddenError,
    DeploymentNotFoundError,
    InvalidDeploymentError,
)
from .render import (
    CLAIM_PLURAL,
    AppsUrlSettings,
    ClaimPlan,
    ComponentPlan,
    render_application,
)

INSTANCE_GROUP = "kro.run"
INSTANCE_KIND = "Application"
CLAIM_GROUP = "platform.skip.io"
CLAIM_VERSION = "v1alpha1"
OWNER_LABEL = "platform.skip.de/owner"
TEMPLATE_LABEL = "platform.skip.de/template"
APP_LABEL = "platform.skip.de/app"
COMPONENT_LABEL = "platform.skip.de/component"
MANAGED_BY_LABEL = "platform.skip.de/managed-by"
NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,44}[a-z0-9])?$")
# Ready=False mit diesen Gruenden ist kein Fehler, sondern "noch unterwegs".
PROGRESSING_REASONS = {None, "", "Progressing", "Reconciling", "Pending", "Creating"}


def owner_label_value(user: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", user)[:63]


class AbstractDeployService(ABC):
    @abstractmethod
    def deploy(self, request: DeployRequest, user: AuthenticatedUser) -> Deployment:
        raise NotImplementedError

    @abstractmethod
    def list(self, user: AuthenticatedUser) -> list[Deployment]:
        raise NotImplementedError

    @abstractmethod
    def get(
        self, template: str, namespace: str, name: str, user: AuthenticatedUser
    ) -> Deployment:
        raise NotImplementedError

    @abstractmethod
    def delete(
        self, template: str, namespace: str, name: str, user: AuthenticatedUser
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_members(
        self, template: str, namespace: str, name: str, user: AuthenticatedUser
    ) -> AppMembers:
        raise NotImplementedError

    @abstractmethod
    def add_member(
        self,
        template: str,
        namespace: str,
        name: str,
        username: str,
        user: AuthenticatedUser,
    ) -> AppMembers:
        raise NotImplementedError

    @abstractmethod
    def remove_member(
        self,
        template: str,
        namespace: str,
        name: str,
        username: str,
        user: AuthenticatedUser,
    ) -> AppMembers:
        raise NotImplementedError


class KubernetesDeployService(AbstractDeployService):
    """Deployt AppTemplates als Instanzen der Application-RGD und setzt die Zugriffsregeln durch.

    Eine App besteht aus einer Application-Instanz je Komponente des Templates
    (`<app>-<komponente>`, Label `platform.skip.de/app`). Ablauf beim Deploy:
    Parameter validieren -> Komponenten und CapabilityClaims rendern
    (deploy/render.py) -> Berechtigungen pruefen -> Instanzen anlegen (erst
    Dry-Run fuer alle, dann Create) -> Claims mit OwnerReferences auf alle
    Instanzen anlegen -> Authentik-Gruppe fuer das Sharing.

    Zugriff auf eine Instanz haben der Ersteller (Owner-Label), Mitglieder
    der Gruppe `skip-admins` sowie Mitglieder der Authentik-Gruppe
    `app-<namespace>-<name>` (nur lesend). Ohne konfigurierten
    Authentik-Client (`authentik=None`) gibt es kein Sharing.
    """

    def __init__(
        self,
        template_service: AbstractTemplateService,
        allowed_namespaces: set[str] | frozenset[str],
        authentik: AuthentikClient | None = None,
        entitlements: EntitlementProvider | None = None,
        urls: AppsUrlSettings | None = None,
        custom_objects: Callable[[], client.CustomObjectsApi] = client.CustomObjectsApi,
        extensions: Callable[[], client.ApiextensionsV1Api] = client.ApiextensionsV1Api,
        core_api: Callable[[], client.CoreV1Api] = client.CoreV1Api,
    ) -> None:
        self.template_service = template_service
        self.allowed_namespaces = frozenset(allowed_namespaces)
        self._authentik = authentik
        self._entitlements = entitlements
        self._urls = urls if urls is not None else AppsUrlSettings()
        self._custom_objects = custom_objects
        self._extensions = extensions
        self._core_api = core_api

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def deploy(self, request: DeployRequest, user: AuthenticatedUser) -> Deployment:
        self._validate_request(request, user)
        template = self.template_service.get_template(request.template)
        rendered = render_application(
            template,
            request.name,
            request.values,
            namespace=request.namespace,
            urls=self._urls,
        )
        self._check_entitlements(user, rendered.components, template)
        if self._load_app(request.namespace, request.name):
            raise DeploymentConflictError(f"'{request.name}' existiert bereits")

        if request.namespace == user_namespace_name(user.username):
            self._ensure_namespace(request.namespace, user)

        version, plural = self._instance_type(INSTANCE_KIND)
        owner = owner_label_value(user.username)
        instances = [
            self._instance_manifest(request, component, version, owner)
            for component in rendered.components
        ]
        objects = self._custom_objects()
        created: list[dict] = []
        try:
            for instance in instances:
                objects.create_namespaced_custom_object(
                    INSTANCE_GROUP,
                    version,
                    request.namespace,
                    plural,
                    instance,
                    dry_run="All",
                )
            for instance in instances:
                created.append(
                    objects.create_namespaced_custom_object(
                        INSTANCE_GROUP, version, request.namespace, plural, instance
                    )
                )
            self._create_claims(request.namespace, created, rendered.claims)
        except (client.ApiException, InvalidDeploymentError) as exc:
            # Keine halbe App zuruecklassen: bereits angelegte Instanzen (und
            # damit per GC ihre Claims) wieder entfernen.
            for instance in created:
                self._delete_instance(instance, version, plural)
            if isinstance(exc, InvalidDeploymentError):
                raise
            if exc.status == 409:
                raise DeploymentConflictError(
                    f"'{request.name}' existiert bereits"
                ) from exc
            raise InvalidDeploymentError(
                f"Validierung fehlgeschlagen: {exc.reason} -- {exc.body}"
            ) from exc

        if self._authentik:
            # Gruppe app-<ns>-<name> anlegen und den Ersteller eintragen.
            self._authentik.add_user_to_app_group(
                request.namespace, request.name, user.username
            )
        return Deployment(
            template=request.template,
            namespace=request.namespace,
            name=request.name,
            owner=owner,
            is_owner=True,
            url=next((plan.url for plan in rendered.components if plan.url), None),
            components=[
                ComponentStatus(name=plan.name, instance=plan.instance, url=plan.url)
                for plan in rendered.components
            ],
        )

    def list(self, user: AuthenticatedUser) -> list[Deployment]:
        version, plural = self._instance_type(INSTANCE_KIND)
        items = self._custom_objects().list_cluster_custom_object(
            INSTANCE_GROUP, version, plural
        )["items"]
        groups: dict[tuple[str, str], list[dict]] = {}
        for item in items:
            if not item.get("metadata", {}).get("labels", {}).get(TEMPLATE_LABEL):
                continue
            key = (item["metadata"]["namespace"], self._app_name_of(item))
            groups.setdefault(key, []).append(item)
        result: list[Deployment] = []
        for (namespace, name), instances in sorted(groups.items()):
            is_owner = self._access(instances[0], user)
            if is_owner is None:
                continue
            result.append(self._summarize(name, instances, is_owner))
        return result

    def get(
        self, template: str, namespace: str, name: str, user: AuthenticatedUser
    ) -> Deployment:
        instances = self._require_app(namespace, name)
        is_owner = self._require_access(instances[0], user)
        return self._summarize(name, instances, is_owner)

    def delete(
        self, template: str, namespace: str, name: str, user: AuthenticatedUser
    ) -> None:
        version, plural = self._instance_type(INSTANCE_KIND)
        instances = self._require_app(namespace, name)
        self._require_access(instances[0], user, owner=True)
        # Claims und Secrets haengen per OwnerReferences an den Instanzen und
        # werden von der Garbage Collection mit entfernt.
        for instance in instances:
            self._delete_instance(instance, version, plural)
        if self._authentik:
            self._authentik.delete_app_group(namespace, name)

    # ------------------------------------------------------------------
    # Sharing (Authentik-Gruppen)
    # ------------------------------------------------------------------

    def list_members(
        self, template: str, namespace: str, name: str, user: AuthenticatedUser
    ) -> AppMembers:
        instance = self._require_app(namespace, name)[0]
        is_owner = self._require_access(instance, user)
        return self._members(instance, is_owner)

    def add_member(
        self,
        template: str,
        namespace: str,
        name: str,
        username: str,
        user: AuthenticatedUser,
    ) -> AppMembers:
        instance = self._require_app(namespace, name)[0]
        self._require_access(instance, user, owner=True)
        authentik = self._require_authentik()
        if not authentik.add_user_to_app_group(namespace, name, username):
            raise InvalidDeploymentError(
                f"Benutzer '{username}' konnte nicht hinzugefuegt werden"
            )
        return self._members(instance, is_owner=True)

    def remove_member(
        self,
        template: str,
        namespace: str,
        name: str,
        username: str,
        user: AuthenticatedUser,
    ) -> AppMembers:
        instance = self._require_app(namespace, name)[0]
        self._require_access(instance, user, owner=True)
        if self._owner_of(instance) == owner_label_value(username):
            raise InvalidDeploymentError(
                "Der Besitzer der App kann nicht als Mitglied entfernt werden"
            )
        authentik = self._require_authentik()
        if not authentik.remove_user_from_app_group(namespace, name, username):
            raise InvalidDeploymentError(
                f"Benutzer '{username}' konnte nicht entfernt werden"
            )
        return self._members(instance, is_owner=True)

    # ------------------------------------------------------------------
    # Autorisierung & Berechtigungen
    # ------------------------------------------------------------------

    @staticmethod
    def _owner_of(instance: dict) -> str:
        return instance["metadata"].get("labels", {}).get(OWNER_LABEL, "")

    def _access(self, instance: dict, user: AuthenticatedUser) -> bool | None:
        """True = Owner/Admin, False = lesendes Mitglied, None = kein Zugriff."""
        if is_admin(user) or self._owner_of(instance) == owner_label_value(
            user.username
        ):
            return True
        namespace = instance["metadata"]["namespace"]
        name = self._app_name_of(instance)
        if app_group_name(namespace, name) in user.groups:
            return False
        # Token kann veraltet sein (Freigabe nach dem Login) -> live nachfragen.
        if self._authentik and self._authentik.is_member(namespace, name, user.username):
            return False
        return None

    def _require_access(
        self, instance: dict, user: AuthenticatedUser, owner: bool = False
    ) -> bool:
        access = self._access(instance, user)
        if access is None:
            raise DeploymentForbiddenError("Keine Zugriffsberechtigung fuer diese App")
        if owner and not access:
            raise DeploymentForbiddenError(
                "Diese Aktion erfordert Besitzer- oder Administrator-Rechte"
            )
        return access

    def _require_authentik(self) -> AuthentikClient:
        if not self._authentik:
            raise InvalidDeploymentError(
                "App-Sharing ist nicht verfuegbar: Authentik ist nicht konfiguriert"
            )
        return self._authentik

    def _check_entitlements(
        self, user: AuthenticatedUser, components: list[ComponentPlan], template
    ) -> None:
        if self._entitlements is None:
            return
        owned = sum(1 for item in self.list(user) if item.is_owner)
        check_deployment(
            self._entitlements.for_user(user),
            owned_apps=owned,
            resources=_sum_limits(components),
            capability_classes={item.class_ for item in template.spec.capabilities},
        )

    def _members(self, instance: dict, is_owner: bool) -> AppMembers:
        namespace = instance["metadata"]["namespace"]
        name = self._app_name_of(instance)
        members = (
            self._authentik.get_app_group_members(namespace, name)
            if self._authentik
            else []
        )
        return AppMembers(
            namespace=namespace,
            name=name,
            owner=self._owner_of(instance) or None,
            is_owner=is_owner,
            members=[AppMember(**member) for member in members],
        )

    # ------------------------------------------------------------------
    # Validierung & Kubernetes
    # ------------------------------------------------------------------

    def _validate_request(self, request: DeployRequest, user: AuthenticatedUser) -> None:
        allowed = allowed_namespaces_for(user, self.allowed_namespaces)
        if request.namespace not in allowed:
            raise DeploymentForbiddenError(
                f"Keine Berechtigung fuer Namespace '{request.namespace}'. "
                f"Erlaubte Namespaces: {', '.join(allowed)}"
            )
        if not NAME_RE.fullmatch(request.name):
            raise InvalidDeploymentError(
                "Name: Kleinbuchstaben/Ziffern/Bindestriche, max. 46 Zeichen"
            )

    def _ensure_namespace(self, namespace: str, user: AuthenticatedUser) -> None:
        """Legt den persoenlichen Namespace `user-<username>` bei Bedarf an."""
        core = self._core_api()
        try:
            core.read_namespace(namespace)
            return
        except client.ApiException as exc:
            if exc.status != 404:
                raise
        core.create_namespace(
            client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=namespace,
                    labels={
                        MANAGED_BY_LABEL: "skip-platform",
                        OWNER_LABEL: owner_label_value(user.username),
                    },
                )
            )
        )

    @staticmethod
    def _app_name_of(instance: dict) -> str:
        labels = instance["metadata"].get("labels", {})
        return labels.get(APP_LABEL) or instance["metadata"]["name"]

    def _load_app(self, namespace: str, name: str) -> list[dict]:
        """Alle Komponenten-Instanzen einer App (leer, wenn es sie nicht gibt)."""
        version, plural = self._instance_type(INSTANCE_KIND)
        items = self._custom_objects().list_namespaced_custom_object(
            INSTANCE_GROUP,
            version,
            namespace,
            plural,
            label_selector=f"{APP_LABEL}={name}",
        )["items"]
        return sorted(items, key=lambda item: item["metadata"]["name"])

    def _require_app(self, namespace: str, name: str) -> list[dict]:
        instances = self._load_app(namespace, name)
        if not instances:
            raise DeploymentNotFoundError("App nicht gefunden")
        return instances

    def _instance_manifest(
        self, request: DeployRequest, component: ComponentPlan, version: str, owner: str
    ) -> dict:
        return {
            "apiVersion": f"{INSTANCE_GROUP}/{version}",
            "kind": INSTANCE_KIND,
            "metadata": {
                "name": component.instance,
                "namespace": request.namespace,
                "labels": {
                    OWNER_LABEL: owner,
                    TEMPLATE_LABEL: request.template,
                    APP_LABEL: request.name,
                    COMPONENT_LABEL: component.name,
                },
            },
            "spec": component.spec,
        }

    def _delete_instance(self, instance: dict, version: str, plural: str) -> None:
        try:
            self._custom_objects().delete_namespaced_custom_object(
                INSTANCE_GROUP,
                version,
                instance["metadata"]["namespace"],
                plural,
                instance["metadata"]["name"],
            )
        except client.ApiException as exc:
            if exc.status != 404:
                raise

    def _instance_type(self, kind: str) -> tuple[str, str]:
        for crd in self._extensions().list_custom_resource_definition().items:
            if crd.spec.group == INSTANCE_GROUP and crd.spec.names.kind == kind:
                version = next(item.name for item in crd.spec.versions if item.served)
                return version, crd.spec.names.plural
        raise InvalidDeploymentError(
            f"Keine CRD fuer Kind '{kind}' -- RGD nicht angewendet oder nicht Active?"
        )

    def _create_claims(
        self, namespace: str, created: list[dict], claims: list[ClaimPlan]
    ) -> None:
        """Legt die CapabilityClaims an; sie gehoeren allen Komponenten-Instanzen
        der App und werden erst entfernt, wenn die letzte Instanz weg ist."""
        if not claims:
            return
        owner_references = [
            {
                "apiVersion": instance["apiVersion"],
                "kind": instance["kind"],
                "name": instance["metadata"]["name"],
                "uid": instance["metadata"]["uid"],
            }
            for instance in created
        ]
        labels = created[0]["metadata"]["labels"]
        objects = self._custom_objects()
        for plan in claims:
            manifest = plan.manifest(namespace)
            manifest["metadata"]["ownerReferences"] = owner_references
            manifest["metadata"]["labels"] = {
                TEMPLATE_LABEL: labels[TEMPLATE_LABEL],
                APP_LABEL: labels[APP_LABEL],
                "platform.skip.io/capability": plan.capability,
            }
            try:
                objects.create_namespaced_custom_object(
                    CLAIM_GROUP, CLAIM_VERSION, namespace, CLAIM_PLURAL, manifest
                )
            except client.ApiException as exc:
                if exc.status != 409:
                    raise InvalidDeploymentError(
                        f"CapabilityClaim '{plan.name}' konnte nicht angelegt werden: "
                        f"{exc.reason} -- {exc.body}"
                    ) from exc

    def _url_of(self, instance: dict) -> str | None:
        ingress = (instance.get("spec") or {}).get("ingress") or {}
        if ingress.get("enabled") and ingress.get("host"):
            return self._urls.url(ingress["host"])
        return None

    def _summarize(self, name: str, instances: list[dict], is_owner: bool) -> Deployment:
        """Fasst die Komponenten-Instanzen einer App zu einem Eintrag zusammen."""
        first = instances[0]
        components = [
            ComponentStatus(
                name=item["metadata"].get("labels", {}).get(COMPONENT_LABEL)
                or item["metadata"]["name"],
                instance=item["metadata"]["name"],
                url=self._url_of(item),
                **self._phase_of(item),
            )
            for item in instances
        ]
        failed = next((c for c in components if c.phase == "Failed"), None)
        deploying = next((c for c in components if c.phase == "Deploying"), None)
        if failed:
            phase, message = "Failed", f"{failed.name}: {failed.message}"
        elif deploying:
            phase, message = "Deploying", f"{deploying.name}: {deploying.message}"
        else:
            phase, message = "Running", None
        return Deployment(
            template=first["metadata"].get("labels", {}).get(TEMPLATE_LABEL, ""),
            name=name,
            namespace=first["metadata"]["namespace"],
            phase=phase,
            message=message,
            url=next((c.url for c in components if c.url), None),
            components=components,
            status={c.instance: (item.get("status") or {}) for c, item in zip(components, instances)},
            owner=self._owner_of(first) or None,
            is_owner=is_owner,
        )

    @staticmethod
    def _phase_of(instance: dict) -> dict[str, Any]:
        """Phase und Meldung einer einzelnen Application-Instanz."""
        status = instance.get("status", {}) or {}
        state = status.get("state")
        conditions = status.get("conditions", []) or []
        failing = [
            condition
            for condition in conditions
            if condition.get("status") == "False"
            and (
                condition.get("type") in ("Failed", "Error")
                or (
                    condition.get("type") == "Ready"
                    and condition.get("reason") not in PROGRESSING_REASONS
                )
            )
        ]
        ready = any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in conditions
        )
        replicas = status.get("availableReplicas", status.get("readyReplicas"))
        if state == "Failed" or failing:
            phase = "Failed"
            message = (
                failing[0].get("message") if failing else "Deployment fehlgeschlagen"
            )
        elif replicas or state == "Active" or ready:
            phase = "Running"
            message = None
        else:
            phase = "Deploying"
            message = "Ressourcen werden initialisiert..."
        return {"phase": phase, "message": message}


def _sum_limits(components: list[ComponentPlan]) -> dict[str, Any]:
    """Summe der CPU-/Memory-Limits aller Komponenten (fuer die Berechtigungspruefung)."""
    from auth.entitlements import parse_cpu, parse_memory

    cpu = 0.0
    memory = 0
    for component in components:
        limits = (component.spec.get("resources") or {}).get("limits") or {}
        if "cpu" in limits:
            cpu += parse_cpu(limits["cpu"])
        if "memory" in limits:
            memory += parse_memory(limits["memory"])
    return {"limits": {"cpu": f"{int(cpu)}m", "memory": str(memory)}}
