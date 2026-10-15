import logging
import os
from importlib.metadata import EntryPoint, entry_points

from skip_capability_sdk import (
    ENTRY_POINT_GROUP,
    Capability,
    CapabilityError,
    TransientError,
)

logger = logging.getLogger(__name__)


def enabled_plugins() -> set[str] | None:
    """Liest CAPABILITY_PLUGINS (kommagetrennt); None bedeutet: alle installierten."""
    raw = os.environ.get("CAPABILITY_PLUGINS", "").strip()

    if not raw:
        return None

    return {name.strip() for name in raw.split(",") if name.strip()}


def load_capabilities(
    eps: list[EntryPoint] | None = None,
    enabled: set[str] | None = None,
) -> dict[str, Capability]:
    """Lädt alle Capability-Plugins der Entry-Point-Gruppe `skip.capabilities`.

    Der Name des Entry Points ist der `spec.type`, das Ziel eine ohne
    Argumente instanziierbare Klasse (oder Factory). Ein defektes Plugin wird
    protokolliert und übersprungen, damit es die übrigen nicht blockiert.
    """
    if eps is None:
        eps = list(entry_points(group=ENTRY_POINT_GROUP))

    registry: dict[str, Capability] = {}

    for ep in eps:
        if enabled is not None and ep.name not in enabled:
            logger.info("Capability plugin %r is installed but not enabled", ep.name)
            continue

        if ep.name in registry:
            logger.error(
                "Duplicate capability plugin %r (%s); keeping the first one",
                ep.name,
                ep.value,
            )
            continue

        try:
            registry[ep.name] = ep.load()()
        except Exception:
            logger.exception(
                "Failed to load capability plugin %r (%s)", ep.name, ep.value
            )
            continue

        logger.info("Loaded capability plugin %r (%s)", ep.name, ep.value)

    if enabled is not None:
        for name in sorted(enabled - registry.keys()):
            logger.warning(
                "Capability plugin %r is enabled but could not be loaded", name
            )

    return registry


def initialize_capability(name: str, capability: Capability) -> None:
    """Ruft den `initialize`-Hook auf und vereinheitlicht Fehler zu `TransientError`.

    Auch unerwartete Exceptions gelten als vorübergehend: der Operator
    versucht die Initialisierung später erneut, statt das Plugin aufzugeben.
    """
    try:
        capability.initialize()
    except CapabilityError as exc:
        raise TransientError(f"capability {name!r} is not available: {exc}") from exc
    except Exception as exc:
        logger.exception("Capability plugin %r failed to initialize", name)
        raise TransientError(
            f"capability {name!r} failed to initialize: {exc!r}"
        ) from exc
