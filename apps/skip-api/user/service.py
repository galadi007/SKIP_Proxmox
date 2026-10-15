from user.errors import (
    GroupNotFoundError,
    LeaderRequiredError,
    UserNotFoundError,
)
from user.models import Group, PlatformUser


class UserService:
    """Service handling platform users, group hierarchies, and onboarding."""

    def __init__(self) -> None:
        self._users: dict[str, PlatformUser] = {}
        self._groups: dict[str, Group] = {}

    def get_or_create_user(
        self, user_id: str, username: str, email: str | None = None
    ) -> PlatformUser:
        if user_id not in self._users:
            self._users[user_id] = PlatformUser(
                user_id=user_id,
                username=username,
                email=email,
                is_onboarded=False,
            )
        return self._users[user_id]

    def get_user(self, user_id: str) -> PlatformUser:
        if user_id not in self._users:
            raise UserNotFoundError(user_id)
        return self._users[user_id]

    def onboard_user(
        self, user_id: str, group_id: str | None = None
    ) -> PlatformUser:
        user = self.get_user(user_id)
        if group_id:
            self.add_member_to_group(group_id, user_id)
        user.is_onboarded = True
        user.home_directory = f"/home/{user.username}"
        return user

    def create_group(
        self, group_id: str, name: str, leader_user_id: str, parent_id: str | None = None
    ) -> Group:
        if parent_id and parent_id not in self._groups:
            raise GroupNotFoundError(parent_id)

        group = Group(
            id=group_id,
            name=name,
            parent_id=parent_id,
            leaders={leader_user_id},
            members={leader_user_id},
        )
        self._groups[group_id] = group

        if leader_user_id in self._users:
            self._users[leader_user_id].groups.add(group_id)

        return group

    def get_group(self, group_id: str) -> Group:
        if group_id not in self._groups:
            raise GroupNotFoundError(group_id)
        return self._groups[group_id]

    def list_groups(self) -> list[Group]:
        return list(self._groups.values())

    def add_member_to_group(self, group_id: str, user_id: str) -> Group:
        group = self.get_group(group_id)
        group.members.add(user_id)
        if user_id in self._users:
            self._users[user_id].groups.add(group_id)
        return group

    def remove_leader_from_group(self, group_id: str, user_id: str) -> Group:
        group = self.get_group(group_id)
        if len(group.leaders) <= 1 and user_id in group.leaders:
            raise LeaderRequiredError(group_id)
        group.leaders.discard(user_id)
        return group
