from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth.authentik import app_group_name
from auth.dtos import AuthenticatedUser
from auth.oidc import OidcSettings, get_current_user, get_oidc_settings
from auth.service import allowed_namespaces_for, user_namespace_name
from deploy.errors import DeploymentForbiddenError
from deploy.service import KubernetesDeployService, owner_label_value


def test_user_namespace_name_is_a_valid_kubernetes_name() -> None:
    assert user_namespace_name("Max.Mustermann") == "user-max-mustermann"
    assert user_namespace_name("dev@skip.de") == "user-dev-skip-de"
    assert len(user_namespace_name("x" * 100)) <= 63


def test_allowed_namespaces_combine_personal_and_group_namespaces() -> None:
    configured = frozenset({"team-data", "team-ki"})
    member = AuthenticatedUser(username="max", groups=["team-data", "other"])
    admin = AuthenticatedUser(username="root", groups=["skip-admins"])
    assert allowed_namespaces_for(member, configured) == ["team-data", "user-max"]
    assert allowed_namespaces_for(admin, configured) == [
        "team-data",
        "team-ki",
        "user-root",
    ]


def _app(settings: OidcSettings) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_oidc_settings] = lambda: settings

    @app.get("/whoami")
    def whoami(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
        return {"username": user.username, "groups": user.groups}

    return TestClient(app)


def test_dev_fallback_accepts_x_user_header_locally() -> None:
    client = _app(OidcSettings(allow_dev_fallback=True))
    response = client.get("/whoami", headers={"X-User": "dev@skip.de"})
    assert response.status_code == 200
    assert response.json()["username"] == "dev@skip.de"
    assert "skip-admins" in response.json()["groups"]


def test_missing_credentials_are_rejected() -> None:
    client = _app(OidcSettings(allow_dev_fallback=True))
    assert client.get("/whoami").status_code == 401
    strict = _app(OidcSettings(issuer_url="https://idp", allow_dev_fallback=False))
    assert strict.get("/whoami", headers={"X-User": "dev"}).status_code == 401


class FakeAuthentik:
    def __init__(self, members: dict[str, set[str]] | None = None) -> None:
        self.members = members or {}

    def is_member(self, namespace: str, name: str, username: str) -> bool:
        return username in self.members.get(app_group_name(namespace, name), set())


def _instance(owner: str, name: str = "app") -> dict:
    return {
        "metadata": {
            "name": name,
            "namespace": "team-data",
            "labels": {"platform.skip.de/owner": owner_label_value(owner)},
        },
        "status": {},
    }


def _service(authentik: FakeAuthentik | None) -> KubernetesDeployService:
    return KubernetesDeployService(
        template_service=SimpleNamespace(),
        allowed_namespaces={"team-data"},
        authentik=authentik,
    )


def test_access_rules_for_owner_admin_member_and_stranger() -> None:
    instance = _instance("alice")
    service = _service(FakeAuthentik({"app-team-data-app": {"carol"}}))
    owner = AuthenticatedUser(username="alice")
    admin = AuthenticatedUser(username="root", groups=["skip-admins"])
    token_member = AuthenticatedUser(username="bob", groups=["app-team-data-app"])
    live_member = AuthenticatedUser(username="carol")
    stranger = AuthenticatedUser(username="mallory")

    assert service._access(instance, owner) is True
    assert service._access(instance, admin) is True
    assert service._access(instance, token_member) is False
    assert service._access(instance, live_member) is False
    assert service._access(instance, stranger) is None


def test_member_may_read_but_not_manage() -> None:
    instance = _instance("alice")
    service = _service(None)
    member = AuthenticatedUser(username="bob", groups=["app-team-data-app"])
    assert service._require_access(instance, member) is False
    try:
        service._require_access(instance, member, owner=True)
    except DeploymentForbiddenError:
        pass
    else:  # pragma: no cover
        raise AssertionError("member must not manage the app")
