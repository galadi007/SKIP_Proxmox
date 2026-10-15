from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dtos import AuthenticatedUser
from storage.api import router
from storage.dtos import FileInfo, StorageOverview
from storage.service import StorageService, get_storage_service


def _create_test_app() -> tuple[FastAPI, MagicMock]:
    app = FastAPI()
    app.include_router(router)

    mock_service = MagicMock(spec=StorageService)
    app.dependency_overrides[get_storage_service] = lambda: mock_service
    return app, mock_service


def test_storage_api_overview() -> None:
    app, mock_service = _create_test_app()
    mock_service.get_overview.return_value = StorageOverview(
        username="alice",
        home_prefix="home/alice/",
        total_files=3,
        total_size_bytes=2048,
        bucket="skip-storage",
        endpoint="http://s3.localhost:8080",
    )

    client = TestClient(app)
    headers = {"X-User": "alice"}
    resp = client.get("/api/storage/overview", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"
    assert data["home_prefix"] == "home/alice/"
    assert data["total_files"] == 3
    assert data["total_size_bytes"] == 2048


def test_storage_api_list_files() -> None:
    app, mock_service = _create_test_app()
    mock_service.list_user_files.return_value = [
        FileInfo(key="docs", name="docs", size_bytes=0, is_dir=True),
        FileInfo(key="readme.txt", name="readme.txt", size_bytes=100, is_dir=False),
    ]

    client = TestClient(app)
    headers = {"X-User": "alice"}
    resp = client.get("/api/storage/files?folder=test", headers=headers)

    assert resp.status_code == 200
    files = resp.json()
    assert len(files) == 2
    assert files[0]["is_dir"] is True
    assert files[1]["name"] == "readme.txt"
    mock_service.list_user_files.assert_called_once()


def test_storage_api_create_folder() -> None:
    app, mock_service = _create_test_app()
    mock_service.create_user_folder.return_value = FileInfo(
        key="subfolder/new_dir",
        name="new_dir",
        size_bytes=0,
        is_dir=True,
    )

    client = TestClient(app)
    headers = {"X-User": "alice"}
    payload = {"name": "new_dir", "parent": "subfolder"}
    resp = client.post("/api/storage/folders", json=payload, headers=headers)

    assert resp.status_code == 201
    folder = resp.json()
    assert folder["name"] == "new_dir"
    assert folder["is_dir"] is True
    mock_service.create_user_folder.assert_called_once()


def test_storage_api_upload_file() -> None:
    app, mock_service = _create_test_app()
    mock_service.upload_user_file.return_value = FileInfo(
        key="data.csv",
        name="data.csv",
        size_bytes=12,
        is_dir=False,
    )

    client = TestClient(app)
    headers = {"X-User": "alice"}
    files = {"file": ("data.csv", b"col1,col2\n1,2", "text/csv")}
    data = {"folder": ""}
    resp = client.post("/api/storage/upload", files=files, data=data, headers=headers)

    assert resp.status_code == 201
    uploaded = resp.json()
    assert uploaded["name"] == "data.csv"
    assert uploaded["size_bytes"] == 12


def test_storage_api_delete_file() -> None:
    app, mock_service = _create_test_app()
    mock_service.delete_user_file.return_value = True

    client = TestClient(app)
    headers = {"X-User": "alice"}
    resp = client.delete("/api/storage/files?path=old_file.txt", headers=headers)

    assert resp.status_code == 204
    mock_service.delete_user_file.assert_called_once()
