from pydantic import BaseModel, Field


class Group(BaseModel):
    """Hierarchical organization node (e.g. Org, Department, Team)."""

    id: str
    name: str
    parent_id: str | None = None
    leaders: set[str] = Field(default_factory=set)  # Set of user_ids (Authentik sub)
    members: set[str] = Field(default_factory=set)  # Set of user_ids (Authentik sub)


class PlatformUser(BaseModel):
    """Platform user profile linked to Authentik via user_id (sub)."""

    user_id: str  # Authentik sub UUID
    username: str
    email: str | None = None
    is_onboarded: bool = False
    groups: set[str] = Field(default_factory=set)  # Group IDs the user belongs to
    home_directory: str | None = None
