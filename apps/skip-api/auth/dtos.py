from typing import Any

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    """Ein per OIDC-Token (oder Dev-Fallback) verifizierter Benutzer."""

    username: str
    email: str | None = None
    groups: list[str] = Field(default_factory=list)
    sub: str | None = None
    raw_claims: dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:
        return self.username


class UserProfile(BaseModel):
    username: str
    email: str | None = None
    groups: list[str] = Field(default_factory=list)
    allowed_namespaces: list[str] = Field(
        default_factory=list, serialization_alias="allowedNamespaces"
    )
    entitlements: dict[str, Any] = Field(default_factory=dict)


class NamespaceList(BaseModel):
    namespaces: list[str]


class UserSummary(BaseModel):
    username: str
    name: str | None = None
    email: str | None = None


class UserSearchResult(BaseModel):
    users: list[UserSummary]


class GroupSearchResult(BaseModel):
    groups: list[str]
