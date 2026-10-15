from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from auth.dtos import AuthenticatedUser
from storage.dtos import ShareRequest
from storage.errors import StorageAccessDeniedError
from storage.service import StorageService


@pytest.fixture
def mock_s3():
    client = MagicMock()
    # Mock list_objects_v2 default response
    client.list_objects_v2.return_value = {
        "CommonPrefixes": [{"Prefix": "home/alice/subfolder/"}],
        "Contents": [
            {
                "Key": "home/alice/test.txt",
                "Size": 1024,
                "LastModified": datetime.now(timezone.utc),
            }
        ],
    }
    return client


@pytest.fixture
def storage_service(mock_s3):
    return StorageService(
        endpoint_url="http://localhost:9000",
        public_endpoint_url="http://s3.localhost:8080",
        access_key="test-key",
        secret_key="test-secret",
        bucket_name="skip-storage",
        s3_client=mock_s3,
    )


def test_home_prefix_and_overview(storage_service):
    alice = AuthenticatedUser(username="alice", groups=[])
    overview = storage_service.get_overview(alice)

    assert overview.username == "alice"
    assert overview.home_prefix == "home/alice/"
    assert overview.total_files == 1
    assert overview.total_size_bytes == 1024
    assert overview.bucket == "skip-storage"


def test_list_user_files(storage_service):
    alice = AuthenticatedUser(username="alice", groups=[])
    files = storage_service.list_user_files(alice)

    assert len(files) == 2
    dir_entry = next(f for f in files if f.is_dir)
    assert dir_entry.name == "subfolder"
    assert dir_entry.key == "subfolder"

    file_entry = next(f for f in files if not f.is_dir)
    assert file_entry.name == "test.txt"
    assert file_entry.size_bytes == 1024


def test_access_denied_for_other_user_home(storage_service):
    bob = AuthenticatedUser(username="bob", groups=[])
    # Bob tries to access Alice's private home file without a share
    with pytest.raises(StorageAccessDeniedError):
        storage_service.check_access(bob, "home/alice/secret.txt")


def test_admin_can_access_any_home(storage_service):
    admin = AuthenticatedUser(username="admin", groups=["skip-admins"])
    path = storage_service.check_access(admin, "home/alice/secret.txt")
    assert path == "home/alice/secret.txt"


def test_sharing_and_access_grant(storage_service, monkeypatch):
    alice = AuthenticatedUser(username="alice", groups=[])
    bob = AuthenticatedUser(username="bob", groups=[])
    charlie = AuthenticatedUser(username="charlie", groups=[])

    # Alice shares a file with Bob
    req = ShareRequest(
        path="datasets/data.csv",
        target_users=["bob"],
        permission="read",
    )
    share = storage_service.create_share(alice, req)

    # Mock list_all_shares to return Alice's share
    monkeypatch.setattr(storage_service, "list_all_shares", lambda: [share])

    # 1. Bob should see it in shared-with-me
    bobs_shares = storage_service.list_shared_with_me(bob)
    assert len(bobs_shares) == 1
    assert bobs_shares[0].path == "datasets/data.csv"
    assert bobs_shares[0].owner == "alice"

    # 2. Charlie should NOT see it
    charlie_shares = storage_service.list_shared_with_me(charlie)
    assert len(charlie_shares) == 0

    # 3. Bob can access the shared file
    target_key = "home/alice/datasets/data.csv"
    allowed_path = storage_service.check_access(bob, target_key)
    assert allowed_path == target_key

    # 4. Bob cannot write if only read was granted
    with pytest.raises(StorageAccessDeniedError):
        storage_service.check_access(bob, target_key, require_write=True)

    # 5. Charlie cannot access it
    with pytest.raises(StorageAccessDeniedError):
        storage_service.check_access(charlie, target_key)


def test_group_sharing(storage_service, monkeypatch):
    alice = AuthenticatedUser(username="alice", groups=[])
    team_member = AuthenticatedUser(username="david", groups=["team-data"])
    other_user = AuthenticatedUser(username="eve", groups=["other-group"])

    req = ShareRequest(
        path="team-folder",
        target_groups=["team-data"],
        permission="read_write",
    )
    share = storage_service.create_share(alice, req)
    monkeypatch.setattr(storage_service, "list_all_shares", lambda: [share])

    # David has team-data group, so he has access to files inside team-folder
    target_key = "home/alice/team-folder/notes.md"
    allowed = storage_service.check_access(team_member, target_key, require_write=True)
    assert allowed == target_key

    # Eve is not in team-data
    with pytest.raises(StorageAccessDeniedError):
        storage_service.check_access(other_user, target_key)


def test_upload_and_delete_user_file(storage_service, mock_s3):
    alice = AuthenticatedUser(username="alice", groups=[])
    file_info = storage_service.upload_user_file(alice, filename="report.pdf", content=b"PDFDATA")

    assert file_info.name == "report.pdf"
    assert file_info.key == "report.pdf"
    assert file_info.size_bytes == 7
    mock_s3.put_object.assert_called_with(
        Bucket="skip-storage",
        Key="home/alice/report.pdf",
        Body=b"PDFDATA",
    )

    deleted = storage_service.delete_user_file(alice, "report.pdf")
    assert deleted is True
    mock_s3.delete_object.assert_called_with(
        Bucket="skip-storage",
        Key="home/alice/report.pdf",
    )


def test_create_user_folder(storage_service, mock_s3):
    alice = AuthenticatedUser(username="alice", groups=[])
    folder_info = storage_service.create_user_folder(alice, folder_name="experiments", parent="project-a")

    assert folder_info.name == "experiments"
    assert folder_info.key == "project-a/experiments"
    assert folder_info.is_dir is True
    mock_s3.put_object.assert_called_with(
        Bucket="skip-storage",
        Key="home/alice/project-a/experiments/.keep",
        Body=b"",
        ContentType="application/octet-stream",
    )


def test_delete_user_folder_recursively(storage_service, mock_s3):
    alice = AuthenticatedUser(username="alice", groups=[])
    # Mock list_objects_v2 to return nested folder files
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "home/alice/project-a/file1.csv"},
            {"Key": "home/alice/project-a/sub/file2.csv"},
            {"Key": "home/alice/project-a/.keep"},
        ]
    }

    deleted = storage_service.delete_user_file(alice, "project-a")
    assert deleted is True
    mock_s3.delete_objects.assert_called_with(
        Bucket="skip-storage",
        Delete={
            "Objects": [
                {"Key": "home/alice/project-a/file1.csv"},
                {"Key": "home/alice/project-a/sub/file2.csv"},
                {"Key": "home/alice/project-a/.keep"},
            ]
        },
    )

