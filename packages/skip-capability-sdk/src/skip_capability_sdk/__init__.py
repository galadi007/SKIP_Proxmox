from dataclasses import dataclass
from typing import Any, Mapping, Protocol

ENTRY_POINT_GROUP = "skip.capabilities"


class CapabilityError(Exception):
    """Basisklasse für Fehler, die eine Capability beim Bereitstellen meldet."""


class TransientError(CapabilityError):
    """Vorübergehender Fehler; der Operator versucht es später erneut."""


class InvalidClaimError(CapabilityError):
    """Der Claim ist ungültig; ohne Änderung am Claim ist ein Retry sinnlos."""


@dataclass(frozen=True)
class Claim:
    """Der für eine Capability relevante Ausschnitt eines CapabilityClaim."""

    name: str
    namespace: str
    uid: str
    api_version: str
    kind: str
    spec: Mapping[str, Any]

    @classmethod
    def from_body(cls, body: Mapping[str, Any]) -> "Claim":
        meta = body["metadata"]

        return cls(
            name=meta["name"],
            namespace=meta["namespace"],
            uid=meta["uid"],
            api_version=body["apiVersion"],
            kind=body["kind"],
            spec=body.get("spec") or {},
        )

    @property
    def type(self) -> str:
        return self.spec.get("type", "")

    @property
    def properties(self) -> Mapping[str, Any]:
        return self.spec.get("properties") or {}


@dataclass(frozen=True)
class SecretRef:
    name: str
    key: str


@dataclass(frozen=True)
class Binding:
    """Verbindungsdaten, die der Operator nach `.status.binding` schreibt."""

    endpoint: str
    secret_ref: SecretRef

    def to_status(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "secretRef": {"name": self.secret_ref.name, "key": self.secret_ref.key},
        }


class Capability(Protocol):
    """Ein Plattform-Service, der für einen CapabilityClaim bereitgestellt werden kann."""

    def initialize(self) -> None:
        """Bereitet die Capability vor und prüft ihre Abhängigkeiten."""
        ...

    def provision(self, claim: Claim) -> Binding:
        """Bringt den externen Service in Einklang mit dem Claim."""
        ...

    def cleanup(self, claim: Claim) -> None:
        """Gibt externe Ressourcen frei, wenn der Claim gelöscht wird."""
        ...


__all__ = [
    "Binding",
    "Capability",
    "CapabilityError",
    "Claim",
    "ENTRY_POINT_GROUP",
    "InvalidClaimError",
    "SecretRef",
    "TransientError",
]
