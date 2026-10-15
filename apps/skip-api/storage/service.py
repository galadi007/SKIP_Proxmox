from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from auth.dtos import AuthenticatedUser
from auth.service import is_admin
from storage.dtos import FileInfo, PresignedUrlResponse, ShareInfo, ShareRequest, StorageOverview
from storage.errors import (
    ShareNotFoundError,
    StorageAccessDeniedError,
)

logger = logging.getLogger(__name__)

SHARED_PREFIX = "_shares/"


class StorageService:
    """Service zur Verwaltung von Benutzer-Home-Verzeichnissen und Dateifreigaben."""

    def __init__(
        self,
        endpoint_url: str = "",
        public_endpoint_url: str = "",
        access_key: str = "",
        secret_key: str = "",
        bucket_name: str = "skip-storage",
        region_name: str = "us-east-1",
        s3_client: Any | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.public_endpoint_url = public_endpoint_url or endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region_name = region_name
        self._client = s3_client
        self._presigned_client: Any | None = None

    @classmethod
    def from_env(cls) -> StorageService:
        endpoint = os.environ.get("S3_ENDPOINT_URL", "").strip()
        public_endpoint = os.environ.get("S3_PUBLIC_ENDPOINT_URL", "").strip()
        access_key = os.environ.get("S3_ACCESS_KEY", "").strip()
        secret_key = os.environ.get("S3_SECRET_KEY", "").strip()
        bucket = os.environ.get("S3_BUCKET_NAME", "skip-storage").strip()
        region = os.environ.get("S3_REGION", "us-east-1").strip()
        return cls(
            endpoint_url=endpoint,
            public_endpoint_url=public_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket_name=bucket,
            region_name=region,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint_url and self.access_key and self.secret_key) or self._client is not None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            config=Config(signature_version="s3v4"),
        )
        return self._client

    def _get_presigned_client(self) -> Any:
        if not self.public_endpoint_url or self.public_endpoint_url == self.endpoint_url:
            return self._get_client()
        if self._presigned_client is not None:
            return self._presigned_client
        import boto3
        from botocore.config import Config

        self._presigned_client = boto3.client(
            "s3",
            endpoint_url=self.public_endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            config=Config(signature_version="s3v4"),
        )
        return self._presigned_client

    def ensure_bucket(self) -> None:
        """Stellt sicher, dass das zentrale Storage-Bucket existiert."""
        if not self.is_configured:
            return
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                client.create_bucket(Bucket=self.bucket_name)
                logger.info("Storage-Bucket '%s' erstellt.", self.bucket_name)
            except Exception as exc:
                logger.warning("Bucket '%s' konnte nicht geprueft/erstellt werden: %s", self.bucket_name, exc)

    def home_prefix(self, username: str) -> str:
        return f"home/{username}/"

    def ensure_user_home(self, username: str) -> None:
        """Stellt sicher, dass das Home-Verzeichnis im S3-Bucket als Ordner sichtbar ist."""
        if not self.is_configured:
            return
        client = self._get_client()
        keep_key = f"{self.home_prefix(username)}.keep"
        try:
            client.head_object(Bucket=self.bucket_name, Key=keep_key)
        except Exception:
            try:
                client.put_object(
                    Bucket=self.bucket_name,
                    Key=keep_key,
                    Body=b"",
                    ContentType="application/octet-stream",
                )
                logger.info("Home-Prefix fuer %s initialisiert.", username)
            except Exception as exc:
                logger.warning("Konnte .keep fuer %s nicht erstellen: %s", username, exc)

    def get_overview(self, user: AuthenticatedUser) -> StorageOverview:
        self.ensure_user_home(user.username)
        prefix = self.home_prefix(user.username)
        total_size = 0
        total_count = 0
        if self.is_configured:
            client = self._get_client()
            try:
                res = client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
                for item in res.get("Contents", []):
                    k = item.get("Key", "")
                    if k == prefix or k.endswith("/") or k.endswith("/.keep") or k.endswith(".keep"):
                        continue
                    total_size += item.get("Size", 0)
                    total_count += 1
            except Exception as exc:
                logger.error("Fehler beim Berechnen der Speicherbelegung fuer %s: %s", user.username, exc)

        return StorageOverview(
            username=user.username,
            bucket=self.bucket_name,
            home_prefix=prefix,
            total_files=total_count,
            total_size_bytes=total_size,
            endpoint=self.public_endpoint_url or self.endpoint_url or "http://s3.localhost:8080",
        )

    def list_user_files(self, user: AuthenticatedUser, folder: str = "") -> list[FileInfo]:
        """Listet Dateien im isolierten Home-Verzeichnis des Benutzers auf."""
        if not self.is_configured:
            return []
        client = self._get_client()
        base_prefix = self.home_prefix(user.username)
        search_prefix = f"{base_prefix}{folder.lstrip('/')}"
        if search_prefix and not search_prefix.endswith("/"):
            search_prefix += "/"

        try:
            res = client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=search_prefix,
                Delimiter="/",
            )
        except Exception as exc:
            logger.error("Fehler beim Auflisten der S3-Dateien fuer %s: %s", user.username, exc)
            return []

        results: list[FileInfo] = []

        # Unterverzeichnisse (CommonPrefixes)
        for cp in res.get("CommonPrefixes", []):
            dir_prefix = cp.get("Prefix", "")
            name = dir_prefix.rstrip("/").split("/")[-1]
            rel_key = dir_prefix[len(base_prefix):].rstrip("/")
            results.append(
                FileInfo(
                    key=rel_key,
                    name=name,
                    size_bytes=0,
                    is_dir=True,
                )
            )

        # Dateien
        for item in res.get("Contents", []):
            key = item.get("Key", "")
            if key == search_prefix or key.endswith("/") or key.endswith("/.keep") or key.endswith(".keep"):
                continue
            name = key.split("/")[-1]
            rel_key = key[len(base_prefix):]
            results.append(
                FileInfo(
                    key=rel_key,
                    name=name,
                    size_bytes=item.get("Size", 0),
                    last_modified=item.get("LastModified"),
                    is_dir=False,
                )
            )

        return sorted(results, key=lambda x: (not x.is_dir, x.name.lower()))

    def upload_user_file(
        self, user: AuthenticatedUser, filename: str, content: bytes, folder: str = ""
    ) -> FileInfo:
        """Speichert eine hochgeladene Datei im Home-Verzeichnis des Benutzers."""
        if not self.is_configured:
            raise StorageAccessDeniedError("Storage ist nicht konfiguriert")
        base_prefix = self.home_prefix(user.username)
        clean_folder = folder.strip("/")
        if clean_folder:
            rel_key = f"{clean_folder}/{filename}"
        else:
            rel_key = filename
        full_key = f"{base_prefix}{rel_key}"

        client = self._get_client()
        client.put_object(
            Bucket=self.bucket_name,
            Key=full_key,
            Body=content,
        )
        logger.info("Datei '%s' fuer Benutzer %s gespeichert (%d Bytes).", full_key, user.username, len(content))
        return FileInfo(
            key=rel_key,
            name=filename,
            size_bytes=len(content),
            last_modified=datetime.now(timezone.utc),
            is_dir=False,
        )

    def create_user_folder(
        self, user: AuthenticatedUser, folder_name: str, parent: str = ""
    ) -> FileInfo:
        """Erstellt einen neuen Ordner im Home-Verzeichnis durch Anlegen eines .keep-Markers."""
        if not self.is_configured:
            raise StorageAccessDeniedError("Storage ist nicht konfiguriert")
        base_prefix = self.home_prefix(user.username)
        clean_name = folder_name.strip("/").replace("..", "")
        clean_parent = parent.strip("/").replace("..", "")
        rel_folder = f"{clean_parent}/{clean_name}" if clean_parent else clean_name
        full_key = f"{base_prefix}{rel_folder}/.keep"

        client = self._get_client()
        client.put_object(
            Bucket=self.bucket_name,
            Key=full_key,
            Body=b"",
            ContentType="application/octet-stream",
        )
        logger.info("Ordner '%s' fuer Benutzer %s erstellt.", rel_folder, user.username)
        return FileInfo(
            key=rel_folder,
            name=clean_name,
            size_bytes=0,
            last_modified=datetime.now(timezone.utc),
            is_dir=True,
        )

    def delete_user_file(self, user: AuthenticatedUser, path: str) -> bool:
        """Loescht eine Datei oder einen Ordner im Home-Verzeichnis des Benutzers."""
        if not self.is_configured:
            raise StorageAccessDeniedError("Storage ist nicht konfiguriert")
        clean_path = path.strip("/")
        if clean_path.startswith("home/"):
            parts = clean_path.split("/", 2)
            if len(parts) >= 2 and parts[1] != user.username and not is_admin(user):
                raise StorageAccessDeniedError("Keine Berechtigung zum Loeschen dieser Datei")
            full_key = clean_path
        else:
            full_key = f"{self.home_prefix(user.username)}{clean_path}"

        client = self._get_client()
        folder_prefix = full_key if full_key.endswith("/") else f"{full_key}/"
        res = client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_prefix)
        objects_to_delete = [
            {"Key": item["Key"]}
            for item in res.get("Contents", [])
            if item.get("Key", "").startswith(folder_prefix)
        ]
        if objects_to_delete:
            client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": objects_to_delete},
            )
            # Auch den Ordner-Key selbst loeschen, falls vorhanden
            try:
                client.delete_object(Bucket=self.bucket_name, Key=full_key)
            except Exception:
                pass
            logger.info("Ordner '%s' mit %d Objekten geloescht durch %s.", full_key, len(objects_to_delete), user.username)
        else:
            client.delete_object(Bucket=self.bucket_name, Key=full_key)
            logger.info("Datei '%s' geloescht durch %s.", full_key, user.username)
        return True

    # ------------------------------------------------------------------
    # Sharing (Freigaben an andere Nutzer & Gruppen)
    # ------------------------------------------------------------------

    def create_share(self, user: AuthenticatedUser, req: ShareRequest) -> ShareInfo:
        """Gibt eine Datei oder einen Ordner fuer bestimmte Benutzer/Gruppen frei."""
        clean_path = req.path.strip("/")
        share = ShareInfo(
            share_id=str(uuid.uuid4())[:8],
            owner=user.username,
            path=clean_path,
            target_users=req.target_users,
            target_groups=req.target_groups,
            permission=req.permission,
            created_at=datetime.now(timezone.utc),
        )

        if self.is_configured:
            client = self._get_client()
            share_key = f"{SHARED_PREFIX}{share.share_id}.json"
            client.put_object(
                Bucket=self.bucket_name,
                Key=share_key,
                Body=share.model_dump_json(),
                ContentType="application/json",
            )
            logger.info("Freigabe %s fuer Pfad '%s' durch %s erstellt.", share.share_id, clean_path, user.username)

        return share

    def list_all_shares(self) -> list[ShareInfo]:
        if not self.is_configured:
            return []
        client = self._get_client()
        shares: list[ShareInfo] = []
        try:
            res = client.list_objects_v2(Bucket=self.bucket_name, Prefix=SHARED_PREFIX)
            for item in res.get("Contents", []):
                key = item.get("Key", "")
                if key.endswith(".json"):
                    obj = client.get_object(Bucket=self.bucket_name, Key=key)
                    data = json.loads(obj["Body"].read().decode("utf-8"))
                    shares.append(ShareInfo(**data))
        except Exception as exc:
            logger.warning("Konnte Freigaben nicht aus S3 laden: %s", exc)
        return shares

    def list_my_shares(self, user: AuthenticatedUser) -> list[ShareInfo]:
        """Listet alle Freigaben auf, die der Benutzer selbst erstellt hat."""
        return [s for s in self.list_all_shares() if s.owner == user.username]

    def list_shared_with_me(self, user: AuthenticatedUser) -> list[ShareInfo]:
        """Listet alle Freigaben auf, fuer die der Benutzer oder seine Gruppen berechtigt sind."""
        shares = self.list_all_shares()
        user_groups = set(user.groups)
        results: list[ShareInfo] = []
        for s in shares:
            if s.owner == user.username:
                continue
            if user.username in s.target_users:
                results.append(s)
            elif any(g in user_groups for g in s.target_groups):
                results.append(s)
        return results

    def delete_share(self, user: AuthenticatedUser, share_id: str) -> bool:
        """Widerruft eine Freigabe (nur Owner oder Admin)."""
        shares = self.list_all_shares()
        target_share = next((s for s in shares if s.share_id == share_id), None)
        if not target_share:
            raise ShareNotFoundError(f"Freigabe '{share_id}' nicht gefunden")

        if target_share.owner != user.username and not is_admin(user):
            raise StorageAccessDeniedError("Nur der Besitzer oder Admin kann diese Freigabe widerrufen")

        if self.is_configured:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket_name, Key=f"{SHARED_PREFIX}{share_id}.json")
            logger.info("Freigabe %s widerrufen.", share_id)
        return True

    # ------------------------------------------------------------------
    # Autorisierung & Presigned URLs
    # ------------------------------------------------------------------

    def check_access(self, user: AuthenticatedUser, path: str, require_write: bool = False) -> str:
        """Prueft Zugriffsrecht auf den vollstaendigen S3-Key und liefert den S3-Pfad zurueck."""
        clean_path = path.lstrip("/")
        my_home_prefix = self.home_prefix(user.username)

        # 1. Zugriff auf das eigene Home-Verzeichnis (immer erlaubt)
        if clean_path.startswith(my_home_prefix):
            return clean_path

        # Wenn der Pfad relativ angegeben wurde (ohne "home/<user>/"):
        if not clean_path.startswith("home/"):
            return f"{my_home_prefix}{clean_path}"

        # 2. Administrator hat Vollzugriff
        if is_admin(user):
            return clean_path

        # 3. Pruefung gegen Freigaben (Sharing)
        # z.B. clean_path = "home/alice/data/file.csv"
        parts = clean_path.split("/", 2)
        if len(parts) >= 2 and parts[0] == "home":
            owner = parts[1]
            rel_file = parts[2] if len(parts) > 2 else ""
            shares = self.list_all_shares()
            for s in shares:
                if s.owner == owner:
                    # Pruefen, ob user oder gruppe berechtigt
                    is_targeted = user.username in s.target_users or any(g in s.target_groups for g in user.groups)
                    if is_targeted:
                        # Pfad-Uebereinstimmung (Datei selbst oder Unterordner)
                        if rel_file == s.path or rel_file.startswith(f"{s.path.rstrip('/')}/"):
                            if require_write and s.permission != "read_write":
                                raise StorageAccessDeniedError("Diese Freigabe erlaubt nur Lesezugriff")
                            return clean_path

        raise StorageAccessDeniedError(f"Kein Zugriff auf Pfad '{path}'")

    def get_presigned_url(
        self, user: AuthenticatedUser, path: str, action: str = "download", expires_in: int = 3600
    ) -> PresignedUrlResponse:
        """Erzeugt eine signierte Einmal-URL fuer Download oder Upload."""
        require_write = action == "upload"
        s3_key = self.check_access(user, path, require_write=require_write)

        if not self.is_configured:
            # Dev-Dummy falls S3 nicht erreichbar ist
            endpoint = self.public_endpoint_url or "http://localhost:9000"
            return PresignedUrlResponse(
                url=f"{endpoint}/{self.bucket_name}/{s3_key}?dummy_token=1",
                expires_in_seconds=expires_in,
                action="upload" if require_write else "download",
            )

        client = self._get_presigned_client()
        client_method = "put_object" if require_write else "get_object"
        params: dict[str, Any] = {"Bucket": self.bucket_name, "Key": s3_key}
        filename = s3_key.rstrip("/").split("/")[-1]
        if not require_write and filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        url = client.generate_presigned_url(
            ClientMethod=client_method,
            Params=params,
            ExpiresIn=expires_in,
        )

        return PresignedUrlResponse(
            url=url,
            expires_in_seconds=expires_in,
            action="upload" if require_write else "download",
        )


@lru_cache
def get_storage_service() -> StorageService:
    svc = StorageService.from_env()
    svc.ensure_bucket()
    return svc
