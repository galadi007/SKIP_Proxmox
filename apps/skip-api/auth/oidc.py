import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError, PyJWKClientError
from jwt.jwks_client import PyJWKClient
from pydantic import BaseModel

from .dtos import AuthenticatedUser

DEV_FALLBACK_GROUPS = ["team-data", "skip-admins"]
UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


class OidcSettings(BaseModel):
    issuer_url: str = ""
    jwks_url: str = ""
    client_id: str = ""
    allow_dev_fallback: bool = True

    @classmethod
    def from_env(cls) -> "OidcSettings":
        issuer = os.environ.get("OIDC_ISSUER_URL", "").strip()
        jwks = os.environ.get("OIDC_JWKS_URL", "").strip()
        if not jwks and issuer:
            jwks = f"{issuer.rstrip('/')}/jwks/"
        skip_env = os.environ.get("SKIP_ENV", "local").strip()
        return cls(
            issuer_url=issuer,
            jwks_url=jwks,
            client_id=os.environ.get("OIDC_CLIENT_ID", "").strip(),
            # Ohne konfigurierten IdP oder lokal darf der X-User-Header genutzt werden.
            allow_dev_fallback=skip_env == "local" or not issuer,
        )


@lru_cache
def get_oidc_settings() -> OidcSettings:
    return OidcSettings.from_env()


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)


def user_from_claims(payload: dict[str, Any]) -> AuthenticatedUser:
    username = (
        payload.get("preferred_username")
        or payload.get("username")
        or payload.get("email")
        or payload.get("sub")
        or "unknown"
    )
    raw_groups = payload.get("groups", [])
    if isinstance(raw_groups, str):
        raw_groups = [raw_groups]
    groups = list(dict.fromkeys(g for g in raw_groups if isinstance(g, str) and g.strip()))
    return AuthenticatedUser(
        username=username,
        email=payload.get("email"),
        groups=groups,
        sub=payload.get("sub"),
        raw_claims=payload,
    )


def verify_token(token: str, settings: OidcSettings) -> AuthenticatedUser:
    """Validiert ein Bearer-JWT (RS256) gegen die JWKS von Authentik.

    Der Issuer variiert je nach Aufrufweg (Ingress vs. Cluster-DNS), deshalb
    wird nur Signatur und Ablauf geprueft, nicht `iss`/`aud`.
    """
    if not settings.jwks_url:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "OIDC ist nicht konfiguriert (OIDC_ISSUER_URL/OIDC_JWKS_URL fehlen).",
            headers=UNAUTHORIZED_HEADERS,
        )
    try:
        signing_key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except (InvalidTokenError, PyJWKClientError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"Ungueltiges Authentifizierungs-Token: {exc}",
            headers=UNAUTHORIZED_HEADERS,
        ) from exc
    except Exception as exc:  # JWKS nicht erreichbar o. ae.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"Token-Validierung fehlgeschlagen: {exc}",
            headers=UNAUTHORIZED_HEADERS,
        ) from exc
    return user_from_claims(payload)


security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    x_user: str | None = Header(default=None),
    settings: OidcSettings = Depends(get_oidc_settings),
) -> AuthenticatedUser:
    """FastAPI-Dependency: Bearer-Token validieren, lokal alternativ X-User."""
    if credentials and credentials.credentials:
        return verify_token(credentials.credentials, settings)
    if x_user and settings.allow_dev_fallback:
        return AuthenticatedUser(
            username=x_user,
            email=x_user if "@" in x_user else None,
            groups=list(DEV_FALLBACK_GROUPS),
            sub=f"dev-user-{x_user}",
            raw_claims={"dev_mode": True},
        )
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Authentifizierung erforderlich (Bearer-Token oder lokal X-User-Header).",
        headers=UNAUTHORIZED_HEADERS,
    )
