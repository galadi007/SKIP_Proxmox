from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from auth.dtos import AuthenticatedUser
from teams.api import router
from teams.dtos import TeamCreateRequest
from teams.errors import (
    TeamAccessDeniedError,
    TeamAlreadyExistsError,
    TeamValidationError,
)
from teams.service import TeamService, get_team_service


@pytest.fixture
def team_service() -> TeamService:
    # Service ohne Authentik nutzt internen Memory-Speicher
    return TeamService(authentik_client=None)


def test_create_team(team_service: TeamService) -> None:
    alice = AuthenticatedUser(username="alice", groups=[])
    req = TeamCreateRequest(name="ki-lab", description="Forschungsgruppe KI")
    team = team_service.create_team(alice, req)

    assert team.name == "team-ki-lab"
    assert team.owner == "alice"
    assert team.is_owner is True
    assert team.description == "Forschungsgruppe KI"
    assert len(team.members) == 1
    assert team.members[0].username == "alice"
    assert team.members[0].is_owner is True


def test_create_team_already_exists(team_service: TeamService) -> None:
    alice = AuthenticatedUser(username="alice", groups=[])
    req = TeamCreateRequest(name="ki-lab")
    team_service.create_team(alice, req)

    with pytest.raises(TeamAlreadyExistsError):
        team_service.create_team(alice, req)


def test_list_teams_visibility(team_service: TeamService) -> None:
    alice = AuthenticatedUser(username="alice", groups=[])
    bob = AuthenticatedUser(username="bob", groups=[])
    charlie = AuthenticatedUser(username="charlie", groups=[])
    admin = AuthenticatedUser(username="admin", groups=["skip-admins"])

    team_service.create_team(alice, TeamCreateRequest(name="team-alpha"))
    team_service.create_team(bob, TeamCreateRequest(name="team-beta"))

    # Alice sieht nur team-alpha
    alice_teams = team_service.list_teams(alice)
    assert len(alice_teams) == 1
    assert alice_teams[0].name == "team-alpha"

    # Charlie sieht gar kein Team
    assert len(team_service.list_teams(charlie)) == 0

    # Admin sieht alle Teams
    assert len(team_service.list_teams(admin)) == 2


def test_add_and_remove_member(team_service: TeamService) -> None:
    alice = AuthenticatedUser(username="alice", groups=[])
    bob = AuthenticatedUser(username="bob", groups=[])
    charlie = AuthenticatedUser(username="charlie", groups=[])

    team_service.create_team(alice, TeamCreateRequest(name="proj-x"))

    # Nicht-Owner (Bob) darf keine Mitglieder hinzufuegen
    with pytest.raises(TeamAccessDeniedError):
        team_service.add_member(bob, "team-proj-x", "charlie")

    # Owner (Alice) fuegt Bob hinzu
    team = team_service.add_member(alice, "team-proj-x", "bob")
    assert len(team.members) == 2
    assert {m.username for m in team.members} == {"alice", "bob"}

    # Bob kann sich selbst entfernen (Team verlassen)
    updated = team_service.remove_member(bob, "team-proj-x", "bob")
    assert len(updated.members) == 1
    assert updated.members[0].username == "alice"

    # Alice kann sich nicht selbst aus ihrem eigenen Team entfernen
    with pytest.raises(TeamValidationError):
        team_service.remove_member(alice, "team-proj-x", "alice")


def test_delete_team(team_service: TeamService) -> None:
    alice = AuthenticatedUser(username="alice", groups=[])
    bob = AuthenticatedUser(username="bob", groups=[])

    team_service.create_team(alice, TeamCreateRequest(name="doomed"))

    # Bob darf es nicht loeschen
    with pytest.raises(TeamAccessDeniedError):
        team_service.delete_team(bob, "team-doomed")

    # Alice darf es loeschen
    assert team_service.delete_team(alice, "team-doomed") is True
    assert len(team_service.list_teams(alice)) == 0


def test_teams_api_endpoints() -> None:
    app = FastAPI()
    app.include_router(router)
    service = TeamService(authentik_client=None)
    app.dependency_overrides[get_team_service] = lambda: service

    client = TestClient(app)
    headers = {"X-User": "alice"}

    # 1. Team anlegen
    resp = client.post("/api/teams", json={"name": "deeplearning", "description": "DL Lab"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "team-deeplearning"
    assert resp.json()["is_owner"] is True

    # 2. Teams listen
    list_resp = client.get("/api/teams", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 3. Mitglied hinzufuegen
    add_resp = client.post("/api/teams/team-deeplearning/members", json={"username": "bob"}, headers=headers)
    assert add_resp.status_code == 200
    assert len(add_resp.json()["members"]) == 2

    # 4. Mitglied entfernen
    del_mem_resp = client.delete("/api/teams/team-deeplearning/members/bob", headers=headers)
    assert del_mem_resp.status_code == 200
    assert len(del_mem_resp.json()["members"]) == 1

    # 5. Team loeschen
    del_resp = client.delete("/api/teams/team-deeplearning", headers=headers)
    assert del_resp.status_code == 204
