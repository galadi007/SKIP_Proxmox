import os
import re
from functools import lru_cache

from .dtos import AuthenticatedUser

ADMIN_GROUP = "skip-admins"
NAMESPACE_MAX_LENGTH = 63


@lru_cache
def configured_namespaces() -> frozenset[str]:
    """Gruppen-Namespaces aus ALLOWED_NAMESPACES (kommagetrennt)."""
    return frozenset(
        item.strip()
        for item in os.environ.get("ALLOWED_NAMESPACES", "team-data").split(",")
        if item.strip()
    )


def user_namespace_name(username: str) -> str:
    """Persoenlicher Namespace `user-<username>` als gueltiger K8s-Name."""
    cleaned = re.sub(r"[^a-z0-9-]", "-", f"user-{username.lower()}")
    cleaned = re.sub(r"-+", "-", cleaned)[:NAMESPACE_MAX_LENGTH].strip("-")
    return cleaned or "user-default"


def is_admin(user: AuthenticatedUser) -> bool:
    return ADMIN_GROUP in user.groups


def allowed_namespaces_for(
    user: AuthenticatedUser, namespaces: frozenset[str] | set[str]
) -> list[str]:
    """Namespaces, in die der Benutzer deployen darf.

    Jeder Benutzer bekommt seinen persoenlichen Namespace; dazu kommen die
    konfigurierten Gruppen-Namespaces, in deren gleichnamiger Authentik-Gruppe
    er Mitglied ist. Admins (`skip-admins`) duerfen ueberall hin.
    """
    personal = user_namespace_name(user.username)
    if is_admin(user):
        return sorted(set(namespaces) | {personal})
    return sorted({personal} | (set(namespaces) & set(user.groups)))
