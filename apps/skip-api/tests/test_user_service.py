import pytest

from user.errors import LeaderRequiredError
from user.service import UserService


def test_user_creation_and_onboarding():
    service = UserService()
    user = service.get_or_create_user(user_id="user-123", username="johndoe", email="john@example.com")
    assert user.user_id == "user-123"
    assert user.is_onboarded is False

    onboarded = service.onboard_user("user-123")
    assert onboarded.is_onboarded is True
    assert onboarded.home_directory == "/home/johndoe"


def test_group_hierarchy_and_membership():
    service = UserService()
    service.get_or_create_user(user_id="leader-1", username="leader1")
    service.get_or_create_user(user_id="member-1", username="member1")

    # Create root group
    org = service.create_group(group_id="org-1", name="FH SWF", leader_user_id="leader-1")
    assert "leader-1" in org.leaders
    assert "leader-1" in org.members

    # Add member
    service.add_member_to_group(group_id="org-1", user_id="member-1")
    updated_org = service.get_group("org-1")
    assert "member-1" in updated_org.members

    # Create child group
    team = service.create_group(group_id="team-1", name="Team Data", leader_user_id="leader-1", parent_id="org-1")
    assert team.parent_id == "org-1"


def test_leader_required_constraint():
    service = UserService()
    service.get_or_create_user(user_id="leader-1", username="leader1")
    service.create_group(group_id="org-1", name="FH SWF", leader_user_id="leader-1")

    with pytest.raises(LeaderRequiredError):
        service.remove_leader_from_group("org-1", "leader-1")
