class UserError(Exception):
    """Base exception for user domain errors."""

    pass


class UserNotFoundError(UserError):
    def __init__(self, user_id: str):
        super().__init__(f"User '{user_id}' not found")
        self.user_id = user_id


class GroupNotFoundError(UserError):
    def __init__(self, group_id: str):
        super().__init__(f"Group '{group_id}' not found")
        self.group_id = group_id


class LeaderRequiredError(UserError):
    def __init__(self, group_id: str):
        super().__init__(f"Group '{group_id}' must have at least one leader")
        self.group_id = group_id


class PermissionDeniedError(UserError):
    def __init__(self, action: str):
        super().__init__(f"Permission denied for action: {action}")
        self.action = action
