from functools import lru_cache
import logging
from typing import Any

from auth.authentik import AuthentikClient, get_authentik_client
from auth.dtos import AuthenticatedUser
from auth.service import is_admin
from teams.dtos import TeamCreateRequest, TeamMember, TeamResponse
from teams.errors import (
    TeamAccessDeniedError,
    TeamAlreadyExistsError,
    TeamNotFoundError,
    TeamValidationError,
)

logger = logging.getLogger(__name__)


class TeamService:
    """Service fuer Self-Service-Teams und -Arbeitsgruppen."""

    def __init__(self, authentik_client: AuthentikClient | None = None) -> None:
        self._authentik = authentik_client
        # In-Memory-Speicher fuer Tests / Fallback wenn Authentik offline ist
        self._memory_teams: dict[str, dict[str, Any]] = {}

    @property
    def is_configured(self) -> bool:
        return self._authentik is not None and self._authentik.is_configured

    def _format_team_response(self, raw: dict[str, Any], current_user: AuthenticatedUser) -> TeamResponse:
        attrs = raw.get("attributes", {}) or {}
        owner = attrs.get("owner", raw.get("owner", ""))
        members_data = raw.get("members", [])
        if not members_data and "users_obj" in raw:
            members_data = [
                {
                    "username": m.get("username"),
                    "name": m.get("name"),
                    "email": m.get("email"),
                    "is_owner": m.get("username") == owner,
                }
                for m in raw.get("users_obj", [])
            ]

        members = [
            TeamMember(
                username=m.get("username", ""),
                name=m.get("name"),
                email=m.get("email"),
                is_owner=m.get("username") == owner,
            )
            for m in members_data
        ]

        admin_or_owner = is_admin(current_user) or current_user.username == owner
        return TeamResponse(
            id=str(raw.get("id", raw.get("pk", ""))),
            name=raw.get("name", ""),
            description=attrs.get("description", raw.get("description", "")),
            owner=owner,
            is_owner=admin_or_owner,
            members=members,
        )

    def create_team(self, user: AuthenticatedUser, request: TeamCreateRequest) -> TeamResponse:
        clean_name = request.name.strip().lower().replace(" ", "-")
        if not clean_name:
            raise TeamValidationError("Teamname darf nicht leer sein.")

        full_name = clean_name if clean_name.startswith("team-") else f"team-{clean_name}"

        if self.is_configured and self._authentik:
            if self._authentik.get_team(full_name):
                raise TeamAlreadyExistsError(full_name)
            raw = self._authentik.create_team(
                team_name=full_name,
                owner_username=user.username,
                description=request.description,
            )
            if not raw:
                raise TeamValidationError(f"Team '{full_name}' konnte in Authentik nicht angelegt werden.")
            # Details mit users_obj abfragen
            full_group = self._authentik.get_team(full_name) or raw
            return self._format_team_response(full_group, user)

        # Fallback fuer Memory-Mocking
        if full_name in self._memory_teams:
            raise TeamAlreadyExistsError(full_name)
        new_team = {
            "id": full_name,
            "name": full_name,
            "description": request.description,
            "owner": user.username,
            "members": [
                {"username": user.username, "name": user.username, "email": None, "is_owner": True}
            ],
            "attributes": {
                "managed_by": "skip-platform",
                "type": "team",
                "owner": user.username,
                "description": request.description,
            },
        }
        self._memory_teams[full_name] = new_team
        return self._format_team_response(new_team, user)

    def list_teams(self, user: AuthenticatedUser) -> list[TeamResponse]:
        if self.is_configured and self._authentik:
            raw_teams = self._authentik.list_teams(username=user.username, is_admin=is_admin(user))
            return [self._format_team_response(t, user) for t in raw_teams]

        # Memory Fallback
        results = []
        user_admin = is_admin(user)
        for t in self._memory_teams.values():
            owner = t.get("owner", "")
            member_names = {m["username"] for m in t.get("members", [])}
            if user_admin or user.username == owner or user.username in member_names:
                results.append(self._format_team_response(t, user))
        return sorted(results, key=lambda x: x.name.lower())

    def get_team(self, user: AuthenticatedUser, team_name: str) -> TeamResponse:
        full_name = team_name if team_name.startswith("team-") else f"team-{team_name}"

        if self.is_configured and self._authentik:
            group = self._authentik.get_team(full_name)
            if not group:
                raise TeamNotFoundError(full_name)
            resp = self._format_team_response(group, user)
            member_names = {m.username for m in resp.members}
            if not (is_admin(user) or user.username == resp.owner or user.username in member_names):
                raise TeamAccessDeniedError("Kein Zugriff auf dieses Team.")
            return resp

        if full_name not in self._memory_teams:
            raise TeamNotFoundError(full_name)
        team = self._memory_teams[full_name]
        resp = self._format_team_response(team, user)
        member_names = {m.username for m in resp.members}
        if not (is_admin(user) or user.username == resp.owner or user.username in member_names):
            raise TeamAccessDeniedError("Kein Zugriff auf dieses Team.")
        return resp

    def add_member(self, user: AuthenticatedUser, team_name: str, username: str) -> TeamResponse:
        team = self.get_team(user, team_name)
        if not team.is_owner:
            raise TeamAccessDeniedError("Nur der Team-Owner oder Administratoren koennen Mitglieder hinzufuegen.")

        if self.is_configured and self._authentik:
            success = self._authentik.add_user_to_team(team.name, username)
            if not success:
                raise TeamValidationError(f"Benutzer '{username}' konnte dem Team nicht hinzugefuegt werden.")
            return self.get_team(user, team_name)

        # Memory Fallback
        mem_team = self._memory_teams[team.name]
        if not any(m["username"] == username for m in mem_team["members"]):
            mem_team["members"].append(
                {"username": username, "name": username, "email": None, "is_owner": False}
            )
        return self._format_team_response(mem_team, user)

    def remove_member(self, user: AuthenticatedUser, team_name: str, username: str) -> TeamResponse:
        team = self.get_team(user, team_name)
        is_self_removal = user.username == username

        if not (team.is_owner or is_self_removal):
            raise TeamAccessDeniedError("Keine Berechtigung zum Entfernen dieses Mitglieds.")

        if username == team.owner:
            raise TeamValidationError("Der Team-Owner kann nicht entfernt werden. Das Team muss geloescht werden.")

        if self.is_configured and self._authentik:
            success = self._authentik.remove_user_from_team(team.name, username)
            if not success:
                raise TeamValidationError(f"Benutzer '{username}' konnte nicht entfernt werden.")
            return self.get_team(user, team_name)

        # Memory Fallback
        mem_team = self._memory_teams[team.name]
        mem_team["members"] = [m for m in mem_team["members"] if m["username"] != username]
        return self._format_team_response(mem_team, user)

    def delete_team(self, user: AuthenticatedUser, team_name: str) -> bool:
        team = self.get_team(user, team_name)
        if not team.is_owner:
            raise TeamAccessDeniedError("Nur der Team-Owner oder Administratoren koennen das Team loeschen.")

        if self.is_configured and self._authentik:
            success = self._authentik.delete_team(team.name)
            if not success:
                raise TeamValidationError(f"Team '{team.name}' konnte nicht geloescht werden.")
            return True

        # Memory Fallback
        if team.name in self._memory_teams:
            del self._memory_teams[team.name]
        return True


@lru_cache
def get_team_service() -> TeamService:
    authentik = get_authentik_client()
    return TeamService(authentik_client=authentik)
