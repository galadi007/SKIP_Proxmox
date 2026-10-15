from pydantic import BaseModel, Field


class UserOnboardRequest(BaseModel):
    """Request DTO for initial user onboarding."""

    group_id: str | None = None


class UserResponse(BaseModel):
    """Response DTO for platform user information."""

    user_id: str
    username: str
    email: str | None = None
    is_onboarded: bool
    groups: list[str] = Field(default_factory=list)
    home_directory: str | None = None


class GroupCreateRequest(BaseModel):
    """Request DTO to create a new group/node in the hierarchy."""

    id: str
    name: str
    parent_id: str | None = None


class GroupResponse(BaseModel):
    """Response DTO for group details."""

    id: str
    name: str
    parent_id: str | None = None
    leaders: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)
