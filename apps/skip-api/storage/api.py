from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from auth.dtos import AuthenticatedUser
from auth.oidc import get_current_user
from storage.dtos import (
    FileInfo,
    FolderCreateRequest,
    PresignedUrlResponse,
    ShareInfo,
    ShareRequest,
    StorageOverview,
)
from storage.errors import (
    ShareNotFoundError,
    StorageAccessDeniedError,
    StorageFileNotFoundError,
)
from storage.service import StorageService, get_storage_service

router = APIRouter(prefix="/api/storage", tags=["Storage"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, StorageAccessDeniedError):
        return HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    if isinstance(exc, (StorageFileNotFoundError, ShareNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get("/overview", response_model=StorageOverview)
def get_overview(
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> StorageOverview:
    """Liefert Speicheruebersicht, Home-Prefix und Belegung fuer den aktuellen Benutzer."""
    return service.get_overview(user)


@router.get("/files", response_model=list[FileInfo])
def list_files(
    folder: str = Query(default="", description="Unterordner im Home-Verzeichnis"),
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> list[FileInfo]:
    """Listet Dateien und Ordner im persoenlichen Home-Verzeichnis auf."""
    return service.list_user_files(user, folder=folder)


@router.post("/upload", response_model=FileInfo, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    folder: str = Form(default=""),
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> FileInfo:
    """Laedt eine Datei direkt in das Home-Verzeichnis des Benutzers hoch."""
    try:
        content = await file.read()
        return service.upload_user_file(
            user, filename=file.filename or "uploaded_file", content=content, folder=folder
        )
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.delete("/files", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    path: str = Query(..., description="Relativer Pfad der Datei oder des Ordners im Home-Verzeichnis"),
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> Response:
    """Loescht eine Datei oder einen Ordner im persoenlichen Home-Verzeichnis."""
    try:
        service.delete_user_file(user, path=path)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/folders", response_model=FileInfo, status_code=status.HTTP_201_CREATED)
def create_folder(
    body: FolderCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> FileInfo:
    """Erstellt einen neuen Unterordner im Home-Verzeichnis."""
    try:
        return service.create_user_folder(user, folder_name=body.name, parent=body.parent)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/shares", response_model=ShareInfo, status_code=status.HTTP_201_CREATED)
def create_share(
    body: ShareRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> ShareInfo:
    """Gibt eine Datei oder einen Ordner fuer bestimmte Benutzer oder Gruppen frei."""
    try:
        return service.create_share(user, body)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.get("/shares/my", response_model=list[ShareInfo])
def list_my_shares(
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> list[ShareInfo]:
    """Listet alle Freigaben auf, die der aktuelle Benutzer selbst erstellt hat."""
    return service.list_my_shares(user)


@router.get("/shares/shared-with-me", response_model=list[ShareInfo])
def list_shared_with_me(
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> list[ShareInfo]:
    """Listet alle Freigaben auf, fuer die der Benutzer oder seine Gruppen berechtigt sind."""
    return service.list_shared_with_me(user)


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_share(
    share_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> Response:
    """Widerruft eine aktive Freigabe (nur Besitzer oder Administrator)."""
    try:
        service.delete_share(user, share_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.get("/presigned-url", response_model=PresignedUrlResponse)
def get_presigned_url(
    path: str = Query(description="Pfad zur Datei"),
    action: str = Query(default="download", pattern="^(download|upload)$"),
    expires_in: int = Query(default=3600, ge=60, le=86400),
    user: AuthenticatedUser = Depends(get_current_user),
    service: StorageService = Depends(get_storage_service),
) -> PresignedUrlResponse:
    """Erzeugt eine signierte Einmal-URL zum direkten Download oder Upload ueber S3."""
    try:
        return service.get_presigned_url(user, path=path, action=action, expires_in=expires_in)
    except Exception as exc:
        raise _translate_error(exc) from exc
