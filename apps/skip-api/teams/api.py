from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth.dtos import AuthenticatedUser
from auth.oidc import get_current_user
from teams.dtos import AddTeamMemberRequest, TeamCreateRequest, TeamResponse
from teams.errors import (
    TeamAccessDeniedError,
    TeamAlreadyExistsError,
    TeamNotFoundError,
    TeamValidationError,
)
from teams.service import TeamService, get_team_service

router = APIRouter(prefix="/api/teams", tags=["Teams"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TeamNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, TeamAlreadyExistsError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, TeamAccessDeniedError):
        return HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    if isinstance(exc, TeamValidationError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get("", response_model=list[TeamResponse])
def list_teams(
    user: AuthenticatedUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> list[TeamResponse]:
    """Listet alle Teams auf, in denen der aktuelle Benutzer Mitglied oder Owner ist."""
    return service.list_teams(user)


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    body: TeamCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamResponse:
    """Erstellt ein neues Team. Der Aufrufer wird automatisch Owner und erstes Mitglied."""
    try:
        return service.create_team(user, body)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.get("/{team_name}", response_model=TeamResponse)
def get_team(
    team_name: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamResponse:
    """Gibt Details und Mitgliederliste eines Teams zurueck."""
    try:
        return service.get_team(user, team_name)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/{team_name}/members", response_model=TeamResponse)
def add_member(
    team_name: str,
    body: AddTeamMemberRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamResponse:
    """Fuegt einen Plattform-Benutzer zum Team hinzu (nur Owner oder Administrator)."""
    try:
        return service.add_member(user, team_name, body.username)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.delete("/{team_name}/members/{username}", response_model=TeamResponse)
def remove_member(
    team_name: str,
    username: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamResponse:
    """Entfernt ein Mitglied aus dem Team (nur Owner/Admin oder Austritt des Mitglieds selbst)."""
    try:
        return service.remove_member(user, team_name, username)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.delete("/{team_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_name: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> Response:
    """Loescht ein Team aus Authentik (nur Owner oder Administrator)."""
    try:
        service.delete_team(user, team_name)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        raise _translate_error(exc) from exc
