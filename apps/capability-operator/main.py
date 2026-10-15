import os

import kopf

from skip_capability_sdk import Capability, Claim, InvalidClaimError, TransientError

from capability_operator.conditions import ready_condition
from capability_operator.plugins import (
    enabled_plugins,
    initialize_capability,
    load_capabilities,
)

GROUP = os.environ.get("API_GROUP", "platform.skip.io")
VERSION = os.environ.get("API_VERSION", "v1alpha1")
PLURAL = "capabilityclaims"

RETRY_DELAY_SECONDS = 10


# Registry der unterstützten Capabilities, Schlüssel ist `spec.type` des Claims.
# Wird beim Start aus den installierten Plugins befüllt.
capabilities: dict[str, Capability] = {}

# Typen, deren `initialize` erfolgreich war. Schlägt die Initialisierung beim
# Start fehl, wird sie vor dem nächsten provision/cleanup erneut versucht.
initialized: set[str] = set()


def ensure_initialized(capability_type: str) -> None:
    """Initialisiert die Capability einmalig; wirft `TransientError` bei Fehlschlag."""
    if capability_type in initialized:
        return

    initialize_capability(capability_type, capabilities[capability_type])
    initialized.add(capability_type)


@kopf.on.startup()
def load_capability_plugins(logger: kopf.Logger, **_):
    capabilities.update(load_capabilities(enabled=enabled_plugins()))

    if not capabilities:
        logger.warning("No capability plugins loaded; every claim will be unsupported")
        return

    logger.info("Serving capability types: %s", ", ".join(sorted(capabilities)))

    # Ein nicht erreichbarer Service soll den Operator nicht blockieren: die
    # Plugins bleiben registriert und werden beim nächsten Claim erneut
    # initialisiert.
    for capability_type in sorted(capabilities):
        try:
            ensure_initialized(capability_type)
        except TransientError as exc:
            logger.warning("%s; retrying on the next claim", exc)
        else:
            logger.info("Initialized capability %r", capability_type)


def set_ready(patch: kopf.Patch, *, status: str, reason: str, message: str) -> None:
    patch.status["conditions"] = [
        ready_condition(status=status, reason=reason, message=message[:1000])
    ]


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile_capability_claim(
    body: kopf.Body,
    namespace: str | None,
    patch: kopf.Patch,
    **_,
):
    if namespace is None:
        return

    claim = Claim.from_body(body)
    capability = capabilities.get(claim.type)

    if capability is None:
        # Unbekannter Typ: sichtbar im Status melden und nicht erneut versuchen.
        set_ready(
            patch,
            status="False",
            reason="UnsupportedCapability",
            message=f"unknown capability type {claim.type!r}",
        )
        raise kopf.PermanentError(f"unsupported capability type {claim.type!r}")

    try:
        ensure_initialized(claim.type)
    except TransientError as exc:
        set_ready(
            patch, status="False", reason="CapabilityUnavailable", message=str(exc)
        )
        raise kopf.TemporaryError(str(exc), delay=RETRY_DELAY_SECONDS) from exc

    try:
        binding = capability.provision(claim)
    except InvalidClaimError as exc:
        set_ready(patch, status="False", reason="InvalidClaim", message=str(exc))
        raise kopf.PermanentError(str(exc)) from exc
    except TransientError as exc:
        set_ready(patch, status="False", reason="ProvisioningFailed", message=str(exc))
        raise kopf.TemporaryError(str(exc), delay=RETRY_DELAY_SECONDS) from exc

    patch.status["binding"] = binding.to_status()
    set_ready(
        patch,
        status="True",
        reason="Provisioned",
        message=f"{claim.type} capability is ready",
    )


@kopf.on.delete(GROUP, VERSION, PLURAL)
def cleanup_capability_claim(body: kopf.Body, namespace: str | None, **_):
    if namespace is None:
        return

    claim = Claim.from_body(body)
    capability = capabilities.get(claim.type)

    if capability is None:
        return

    try:
        ensure_initialized(claim.type)
        capability.cleanup(claim)
    except TransientError as exc:
        # Kopf behält seinen Finalizer und versucht das Löschen erneut.
        raise kopf.TemporaryError(str(exc), delay=RETRY_DELAY_SECONDS) from exc
