class StorageError(Exception):
    """Basis-Exception fuer Speicherfehler."""


class StorageFileNotFoundError(StorageError):
    """Datei oder Verzeichnis existiert nicht."""


class StorageAccessDeniedError(StorageError):
    """Keine Berechtigung fuer den Zugriff auf die Datei oder Freigabe."""


class ShareNotFoundError(StorageError):
    """Freigabe existiert nicht oder wurde widerrufen."""
