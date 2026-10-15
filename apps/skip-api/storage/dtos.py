from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StorageOverview(BaseModel):
    """Status und Speicherinformationen fuer den aktuellen Benutzer."""

    username: str
    bucket: str
    home_prefix: str
    total_files: int = 0
    total_size_bytes: int = 0
    endpoint: str


class FileInfo(BaseModel):
    """Metadaten einer Datei oder eines Ordners im Objektspeicher."""

    key: str
    name: str
    size_bytes: int = 0
    last_modified: datetime | None = None
    is_dir: bool = False


class FolderCreateRequest(BaseModel):
    """Anfrage zum Erstellen eines neuen Ordners."""

    name: str = Field(description="Name des neuen Ordners")
    parent: str = Field(default="", description="Optionaler Elternordner")


class ShareRequest(BaseModel):
    """Anfrage zum Freigeben einer Datei oder eines Ordners."""

    path: str = Field(description="Relativer Pfad innerhalb des eigenen Home-Verzeichnisses")
    target_users: list[str] = Field(default_factory=list, description="Liste von Benutzernamen")
    target_groups: list[str] = Field(default_factory=list, description="Liste von Authentik-Gruppen")
    permission: Literal["read", "read_write"] = "read"


class ShareInfo(BaseModel):
    """Informationen ueber eine aktive Dateifreigabe."""

    share_id: str
    owner: str
    path: str
    target_users: list[str] = Field(default_factory=list)
    target_groups: list[str] = Field(default_factory=list)
    permission: Literal["read", "read_write"] = "read"
    created_at: datetime


class PresignedUrlResponse(BaseModel):
    """Generierte Presigned-URL fuer direkten Download oder Upload."""

    url: str
    expires_in_seconds: int = 3600
    action: Literal["download", "upload"]
