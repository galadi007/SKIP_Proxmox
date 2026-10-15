from typing import Any

from pydantic import BaseModel, Field


class DeployRequest(BaseModel):
    template: str
    name: str
    namespace: str
    values: dict[str, Any] = Field(default_factory=dict)


class ComponentStatus(BaseModel):
    name: str
    instance: str  # Name der Application-Instanz (= Service-/DNS-Name)
    phase: str | None = None
    message: str | None = None
    url: str | None = None  # oeffentliche URL (Ingress), falls die Komponente HTTP freigibt


class Deployment(BaseModel):
    template: str
    namespace: str
    name: str
    phase: str | None = None
    message: str | None = None
    url: str | None = None  # URL der ersten HTTP-Komponente
    components: list[ComponentStatus] = Field(default_factory=list)
    status: dict[str, Any] = Field(default_factory=dict)
    owner: str | None = None
    is_owner: bool = Field(default=False, serialization_alias="isOwner")


class AppMember(BaseModel):
    username: str
    name: str | None = None
    email: str | None = None


class AppMembers(BaseModel):
    namespace: str
    name: str
    owner: str | None = None
    is_owner: bool = Field(default=False, serialization_alias="isOwner")
    members: list[AppMember] = Field(default_factory=list)


class AddMemberRequest(BaseModel):
    username: str
