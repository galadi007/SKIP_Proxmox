"""Berechtigungen pro Benutzer: wie viele Apps, wie viel CPU/RAM, welche Capability-Klassen.

Vorbereitung, kein fertiges Quota-System: `EntitlementProvider` ist die
Schnittstelle, `StaticEntitlementProvider` ein Mock mit Defaults aus der
Umgebung (Admins unbegrenzt). Spaeter kann hier z. B. eine Zuordnung ueber
Authentik-Gruppen oder ein Tenant-Modell haengen.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from .dtos import AuthenticatedUser
from .service import is_admin


class EntitlementExceededError(Exception):
    """Der Benutzer ueberschreitet eine seiner Berechtigungen."""


@dataclass(frozen=True)
class Entitlements:
    max_apps: int | None = None  # None = unbegrenzt
    max_cpu_per_app: str | None = None  # Kubernetes-Quantity, z. B. "4"
    max_memory_per_app: str | None = None  # z. B. "8Gi"
    capability_classes: frozenset[str] | None = None  # None = alle

    def to_dict(self) -> dict[str, Any]:
        return {
            "maxApps": self.max_apps,
            "maxCpuPerApp": self.max_cpu_per_app,
            "maxMemoryPerApp": self.max_memory_per_app,
            "capabilityClasses": (
                sorted(self.capability_classes)
                if self.capability_classes is not None
                else None
            ),
        }


UNLIMITED = Entitlements()


class EntitlementProvider(Protocol):
    def for_user(self, user: AuthenticatedUser) -> Entitlements: ...


class StaticEntitlementProvider:
    """Mock: dieselben Grenzen fuer alle Benutzer, Admins ohne Grenzen."""

    def __init__(self, default: Entitlements) -> None:
        self.default = default

    def for_user(self, user: AuthenticatedUser) -> Entitlements:
        return UNLIMITED if is_admin(user) else self.default


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else None


def _env_str(name: str) -> str | None:
    raw = os.environ.get(name, "").strip()
    return raw or None


@lru_cache
def get_entitlement_provider() -> EntitlementProvider:
    classes = _env_str("ALLOWED_CAPABILITY_CLASSES")
    return StaticEntitlementProvider(
        Entitlements(
            max_apps=_env_int("MAX_APPS_PER_USER") or 10,
            max_cpu_per_app=_env_str("MAX_CPU_PER_APP") or "8",
            max_memory_per_app=_env_str("MAX_MEMORY_PER_APP") or "32Gi",
            capability_classes=(
                frozenset(item.strip() for item in classes.split(",") if item.strip())
                if classes
                else None
            ),
        )
    )


# --- Kubernetes-Quantities -------------------------------------------------

_MEMORY_UNITS = {
    "": 1,
    "k": 10**3,
    "M": 10**6,
    "G": 10**9,
    "T": 10**12,
    "Ki": 2**10,
    "Mi": 2**20,
    "Gi": 2**30,
    "Ti": 2**40,
}
_QUANTITY_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([A-Za-z]*)\s*$")


def parse_cpu(quantity: str | int | float) -> float:
    """CPU-Quantity in Millicores ("500m" -> 500, "2" -> 2000)."""
    match = _QUANTITY_RE.fullmatch(str(quantity))
    if not match:
        raise ValueError(f"invalid cpu quantity: {quantity!r}")
    number, unit = float(match.group(1)), match.group(2)
    if unit == "m":
        return number
    if unit == "":
        return number * 1000
    raise ValueError(f"invalid cpu unit: {quantity!r}")


def parse_memory(quantity: str) -> int:
    """Memory-Quantity in Bytes ("512Mi" -> 536870912)."""
    match = _QUANTITY_RE.fullmatch(str(quantity))
    if not match or match.group(2) not in _MEMORY_UNITS:
        raise ValueError(f"invalid memory quantity: {quantity!r}")
    return int(float(match.group(1)) * _MEMORY_UNITS[match.group(2)])


def check_deployment(
    entitlements: Entitlements,
    *,
    owned_apps: int,
    resources: dict[str, Any] | None,
    capability_classes: set[str],
) -> None:
    """Prueft ein geplantes Deployment gegen die Berechtigungen des Benutzers."""
    if entitlements.max_apps is not None and owned_apps >= entitlements.max_apps:
        raise EntitlementExceededError(
            f"Maximale Anzahl an Apps erreicht ({entitlements.max_apps})"
        )

    limits = (resources or {}).get("limits") or {}
    if entitlements.max_cpu_per_app and limits.get("cpu") is not None:
        if parse_cpu(limits["cpu"]) > parse_cpu(entitlements.max_cpu_per_app):
            raise EntitlementExceededError(
                f"CPU-Limit {limits['cpu']} ueberschreitet das Maximum "
                f"{entitlements.max_cpu_per_app} pro App"
            )
    if entitlements.max_memory_per_app and limits.get("memory") is not None:
        if parse_memory(limits["memory"]) > parse_memory(entitlements.max_memory_per_app):
            raise EntitlementExceededError(
                f"Memory-Limit {limits['memory']} ueberschreitet das Maximum "
                f"{entitlements.max_memory_per_app} pro App"
            )

    if entitlements.capability_classes is not None:
        forbidden = capability_classes - set(entitlements.capability_classes)
        if forbidden:
            raise EntitlementExceededError(
                f"Capability-Klasse(n) nicht erlaubt: {', '.join(sorted(forbidden))}"
            )
