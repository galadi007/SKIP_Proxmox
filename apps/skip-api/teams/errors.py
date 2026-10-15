class TeamError(Exception):
    """Basisklasse fuer Team-bezogene Fehler."""


class TeamNotFoundError(TeamError):
    def __init__(self, team_name: str) -> None:
        super().__init__(f"Team '{team_name}' wurde nicht gefunden.")


class TeamAlreadyExistsError(TeamError):
    def __init__(self, team_name: str) -> None:
        super().__init__(f"Team '{team_name}' existiert bereits.")


class TeamAccessDeniedError(TeamError):
    def __init__(self, message: str = "Keine Berechtigung fuer diese Aktion.") -> None:
        super().__init__(message)


class TeamValidationError(TeamError):
    pass
