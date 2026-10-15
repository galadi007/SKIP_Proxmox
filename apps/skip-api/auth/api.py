from fastapi import APIRouter, Depends, Query

from .authentik import AuthentikClient, get_authentik_client
from .entitlements import EntitlementProvider, get_entitlement_provider
from .dtos import (
    AuthenticatedUser,
    NamespaceList,
    UserProfile,
    UserSearchResult,
    UserSummary,
    GroupSearchResult,
)
from .oidc import get_current_user
from .service import allowed_namespaces_for, configured_namespaces

router = APIRouter(prefix="/api", tags=["Auth"])


@router.get("/me", response_model=UserProfile)
def me(
    user: AuthenticatedUser = Depends(get_current_user),
    entitlements: EntitlementProvider = Depends(get_entitlement_provider),
    authentik: AuthentikClient | None = Depends(get_authentik_client),
) -> UserProfile:
    """Profil, Gruppen, erlaubte Namespaces und Berechtigungen des Benutzers."""
    groups = list(user.groups)
    if authentik and authentik.is_configured:
        try:
            if u := authentik.get_user(user.username):
                live_groups = [
                    g["name"]
                    for g in u.get("groups_obj", [])
                    if isinstance(g, dict) and "name" in g
                ]
                groups.extend(live_groups)
        except Exception:
            pass

    unique_groups = list(dict.fromkeys(g for g in groups if isinstance(g, str) and g.strip()))

    effective_user = AuthenticatedUser(
        username=user.username,
        email=user.email,
        groups=unique_groups,
        sub=user.sub,
        raw_claims=user.raw_claims,
    )

    return UserProfile(
        username=effective_user.username,
        email=effective_user.email,
        groups=effective_user.groups,
        allowed_namespaces=allowed_namespaces_for(effective_user, configured_namespaces()),
        entitlements=entitlements.for_user(effective_user).to_dict(),
    )


@router.get("/namespaces", response_model=NamespaceList)
def list_namespaces(
    user: AuthenticatedUser = Depends(get_current_user),
) -> NamespaceList:
    """Namespaces, in die der Benutzer deployen darf."""
    return NamespaceList(
        namespaces=allowed_namespaces_for(user, configured_namespaces())
    )


@router.get("/users", response_model=UserSearchResult)
def search_users(
    query: str = Query(default=""),
    _: AuthenticatedUser = Depends(get_current_user),
    authentik: AuthentikClient | None = Depends(get_authentik_client),
) -> UserSearchResult:
    """Aktive Authentik-Benutzer fuer die Autovervollstaendigung beim Teilen."""
    users = authentik.search_users(query) if authentik else []
    return UserSearchResult(users=[UserSummary(**item) for item in users])


@router.get("/groups", response_model=GroupSearchResult)
def list_groups(
    _: AuthenticatedUser = Depends(get_current_user),
    authentik: AuthentikClient | None = Depends(get_authentik_client),
) -> GroupSearchResult:
    """Verfuegbare Authentik-Gruppen fuer Gruppenfreigaben."""
    groups = authentik.list_groups() if authentik else []
    return GroupSearchResult(groups=groups)
