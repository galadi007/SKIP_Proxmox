from pydantic import BaseModel, Field


class TeamMember(BaseModel):
    username: str = Field(description="Authentik-Benutzername")
    name: str | None = Field(default=None, description="Vollstaendiger Name")
    email: str | None = Field(default=None, description="E-Mail-Adresse")
    is_owner: bool = Field(default=False, description="Ist der Benutzer Team-Owner")


class TeamCreateRequest(BaseModel):
    name: str = Field(description="Name des Teams, z. B. 'ki-arbeitsgruppe' oder 'projekt-alpha'")
    description: str = Field(default="", description="Optionale Beschreibung des Teams")


class TeamResponse(BaseModel):
    id: str = Field(description="Eindeutige Authentik-Gruppen-ID")
    name: str = Field(description="Vollstaendiger Gruppenname (z. B. team-ki-arbeitsgruppe)")
    description: str = Field(default="", description="Beschreibung des Teams")
    owner: str = Field(description="Benutzername des Gruenders/Owners")
    is_owner: bool = Field(description="Ob der aufrufende Benutzer Owner oder Admin ist")
    members: list[TeamMember] = Field(default_factory=list, description="Liste der Teammitglieder")


class AddTeamMemberRequest(BaseModel):
    username: str = Field(description="Hinzuzufuegender Authentik-Benutzername")
