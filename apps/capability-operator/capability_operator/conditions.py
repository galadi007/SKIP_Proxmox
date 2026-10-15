from datetime import UTC, datetime


def ready_condition(*, status: str, reason: str, message: str = "") -> dict[str, str]:
    """Erzeugt eine Ready-Condition mit allen Pflichtfeldern der CRD."""
    return {
        "type": "Ready",
        "status": status,
        "reason": reason,
        "message": message,
        "lastTransitionTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
