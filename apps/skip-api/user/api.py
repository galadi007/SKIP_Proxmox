from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException, status

from user.dtos import (
    GroupCreateRequest,
    GroupResponse,
    UserOnboardRequest,
    UserResponse,
)
from user.errors import GroupNotFoundError, LeaderRequiredError, UserNotFoundError
from user.models import Group, PlatformUser
from user.service import UserService


def require_user(x_user: str = Header(default="default-dev-user")) -> str:
    return x_user


@lru_cache
def get_user_service() -> UserService:
    return UserService()


router = APIRouter(
    prefix="/api/users",
    tags=["User Management"],
)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (UserNotFoundError, GroupNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, LeaderRequiredError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


def _to_user_response(user: PlatformUser) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        is_onboarded=user.is_onboarded,
        groups=sorted(list(user.groups)),
        home_directory=user.home_directory,
    )


def _to_group_response(group: Group) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        parent_id=group.parent_id,
        leaders=sorted(list(group.leaders)),
        members=sorted(list(group.members)),
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    x_user: str = Depends(require_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Returns the current authenticated user's profile, creating a stub if new."""
    user = service.get_or_create_user(user_id=x_user, username=x_user)
    return _to_user_response(user)


@router.post("/onboard", response_model=UserResponse)
def onboard_user(
    dto: UserOnboardRequest,
    x_user: str = Depends(require_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Onboards the current user into a group and initializes user resources."""
    try:
        user = service.get_or_create_user(user_id=x_user, username=x_user)
        onboarded_user = service.onboard_user(user.user_id, group_id=dto.group_id)
        return _to_user_response(onboarded_user)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.get("/groups", response_model=list[GroupResponse])
def list_groups(
    service: UserService = Depends(get_user_service),
) -> list[GroupResponse]:
    """Lists all registered organizational groups."""
    return [_to_group_response(g) for g in service.list_groups()]


@router.post("/groups", response_model=GroupResponse)
def create_group(
    dto: GroupCreateRequest,
    x_user: str = Depends(require_user),
    service: UserService = Depends(get_user_service),
) -> GroupResponse:
    """Creates a new organizational group with the caller as initial leader."""
    try:
        group = service.create_group(
            group_id=dto.id,
            name=dto.name,
            leader_user_id=x_user,
            parent_id=dto.parent_id,
        )
        return _to_group_response(group)
    except Exception as exc:
        raise _translate_error(exc) from exc
