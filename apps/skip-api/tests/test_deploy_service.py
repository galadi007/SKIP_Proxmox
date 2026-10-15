from pathlib import Path
from types import SimpleNamespace

from auth.dtos import AuthenticatedUser
from deploy.dtos import DeployRequest
from deploy.render import AppsUrlSettings
from deploy.service import KubernetesDeployService
from templates.service import FileSystemTemplateService


TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
DEVELOPER = AuthenticatedUser(username="developer@skip.de", groups=["team-data"])


class CustomObjects:
    """Zeichnet create-Aufrufe (Application-Instanzen und CapabilityClaims) auf."""

    def __init__(self) -> None:
        self.created: list[tuple[str, str, dict, str | None]] = []
        self.deleted: list[str] = []

    def create_namespaced_custom_object(
        self, group, version, namespace, plural, body, dry_run=None
    ):
        self.created.append((group, plural, body, dry_run))
        result = dict(body)
        result["metadata"] = dict(body["metadata"], uid=f"uid-{body['metadata']['name']}")
        return result

    def list_namespaced_custom_object(self, group, version, namespace, plural, label_selector=None):
        app = label_selector.split("=", 1)[1]
        return {"items": [b for b in self.applications()
                          if b["metadata"]["labels"]["platform.skip.de/app"] == app]}

    def list_cluster_custom_object(self, group, version, plural):
        return {"items": self.applications()}

    def delete_namespaced_custom_object(self, group, version, namespace, plural, name):
        self.deleted.append(name)

    def applications(self) -> list[dict]:
        return [body for group, plural, body, dry in self.created
                if plural == "applications" and dry is None]

    def claims(self) -> list[dict]:
        return [body for group, plural, body, dry in self.created
                if plural == "capabilityclaims"]


def _service(objects: CustomObjects) -> KubernetesDeployService:
    crd = SimpleNamespace(
        spec=SimpleNamespace(
            group="kro.run",
            names=SimpleNamespace(kind="Application", plural="applications"),
            versions=[SimpleNamespace(name="v1alpha1", served=True)],
        )
    )
    extensions = SimpleNamespace(
        list_custom_resource_definition=lambda: SimpleNamespace(items=[crd])
    )
    return KubernetesDeployService(
        template_service=FileSystemTemplateService.from_root(TEMPLATES),
        allowed_namespaces={"team-data"},
        urls=AppsUrlSettings(domain="apps.localhost", port="8080"),
        custom_objects=lambda: objects,
        extensions=lambda: extensions,
    )


def test_deploy_renders_jupyter_from_enum_parameters() -> None:
    objects = CustomObjects()
    result = _service(objects).deploy(
        DeployRequest(
            template="jupyter-notebook",
            name="my-notebook",
            namespace="team-data",
            values={"variant": "scipy", "size": "medium", "storageSize": "10Gi"},
        ),
        DEVELOPER,
    )

    assert result.name == "my-notebook" and result.is_owner
    assert [c.instance for c in result.components] == ["my-notebook-jupyter"]
    assert result.url == "http://my-notebook.team-data.apps.localhost:8080"
    dry_runs = [d for _, _, _, d in objects.created if d == "All"]
    assert dry_runs == ["All"]
    [manifest] = objects.applications()
    assert manifest["kind"] == "Application"
    assert manifest["metadata"]["name"] == "my-notebook-jupyter"
    assert manifest["metadata"]["labels"] == {
        "platform.skip.de/owner": "developer_skip.de",
        "platform.skip.de/template": "jupyter-notebook",
        "platform.skip.de/app": "my-notebook",
        "platform.skip.de/component": "jupyter",
    }
    spec = manifest["spec"]
    assert spec["image"] == "quay.io/jupyter/scipy-notebook"
    assert spec["ports"] == [{"name": "http", "containerPort": 8888, "protocol": "TCP"}]
    assert spec["servicePorts"] == [{"name": "notebook", "port": 8888, "targetPort": "http"}]
    assert spec["resources"]["limits"] == {"cpu": "2", "memory": "4Gi"}
    assert spec["storage"] == {"enabled": True, "size": "10Gi"}
    assert spec["volumes"] == [
        {"name": "data", "persistentVolumeClaim": {"claimName": "my-notebook-jupyter"}}
    ]
    assert spec["volumeMounts"] == [{"name": "data", "mountPath": "/home/jovyan/work"}]
    assert spec["ingress"] == {
        "enabled": True,
        "host": "my-notebook.team-data.apps.localhost",
        "className": "traefik",
        "portName": "notebook",
    }
    # LLM-Zugang ist bei Jupyter optional und standardmaessig aus
    assert spec["env"] == [{"name": "JUPYTER_TOKEN", "value": "skip"}]
    assert objects.claims() == []


def test_deploy_open_webui_renders_two_components_and_shared_claim() -> None:
    objects = CustomObjects()
    result = _service(objects).deploy(
        DeployRequest(
            template="open-webui",
            name="my-webui",
            namespace="team-data",
            values={"storageSize": "2Gi"},
        ),
        DEVELOPER,
    )
    assert [c.instance for c in result.components] == ["my-webui-open-webui", "my-webui-postgres"]
    # Nur die HTTP-Komponente bekommt eine URL; die Datenbank (tcp) nicht
    assert [c.url for c in result.components] == [
        "http://my-webui.team-data.apps.localhost:8080",
        None,
    ]

    web, db = objects.applications()
    assert db["spec"]["ingress"] == {"enabled": False}
    env = {item["name"]: item for item in web["spec"]["env"]}
    assert env["ENABLE_OLLAMA_API"]["value"] == "false"
    # Referenz auf die Datenbank-Komponente: Service-DNS + Port
    assert env["DATABASE_URL"]["value"] == "postgresql://webui:webui@my-webui-postgres:5432/webui"
    assert env["OPENAI_API_BASE_URL"]["valueFrom"]["secretKeyRef"] == {
        "name": "my-webui-llm-credentials",
        "key": "endpoint",
    }
    assert env["OPENAI_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "my-webui-llm-credentials",
        "key": "api-key",
    }
    assert db["spec"]["image"].startswith("docker.io/library/postgres:")
    assert db["spec"]["servicePorts"] == [{"name": "db", "port": 5432, "targetPort": "postgres"}]
    assert db["spec"]["storage"]["enabled"] is True

    [claim] = objects.claims()
    assert claim["metadata"]["name"] == "my-webui-llm"
    assert claim["spec"] == {
        "type": "llm-access",
        "properties": {"models": ["mistral-small", "mistral-large"]},
    }
    # Der Claim gehoert allen Komponenten-Instanzen der App
    assert [ref["name"] for ref in claim["metadata"]["ownerReferences"]] == [
        "my-webui-open-webui",
        "my-webui-postgres",
    ]


def test_deploy_jupyter_with_llm_access_binds_optional_capability() -> None:
    objects = CustomObjects()
    _service(objects).deploy(
        DeployRequest(
            template="jupyter-notebook",
            name="ai-notebook",
            namespace="team-data",
            values={"llmAccess": "true"},
        ),
        DEVELOPER,
    )
    [spec] = [m["spec"] for m in objects.applications()]
    names = [item["name"] for item in spec["env"]]
    assert names == ["JUPYTER_TOKEN", "OPENAI_BASE_URL", "OPENAI_API_KEY"]
    assert objects.claims()[0]["metadata"]["name"] == "ai-notebook-llm"


def test_deploy_marimo_uses_size_defaults_and_list_groups_components() -> None:
    objects = CustomObjects()
    service = _service(objects)
    service.deploy(
        DeployRequest(template="marimo", name="my-marimo", namespace="team-data"),
        DEVELOPER,
    )
    [spec] = [m["spec"] for m in objects.applications()]
    assert spec["image"] == "marimo:0.1.0"
    assert spec["resources"] == {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": "500m", "memory": "1Gi"},
    }
    assert spec["storage"] == {"enabled": True, "size": "1Gi"}

    [listed] = service.list(DEVELOPER)
    assert listed.name == "my-marimo" and listed.template == "marimo"
    assert listed.url == "http://my-marimo.team-data.apps.localhost:8080"
    assert listed.phase == "Deploying"
    assert [c.name for c in listed.components] == ["marimo"]

    service.delete("marimo", "team-data", "my-marimo", DEVELOPER)
    assert objects.deleted == ["my-marimo-marimo"]


def test_deploy_rejects_duplicate_app_name() -> None:
    import pytest

    from deploy.errors import DeploymentConflictError

    objects = CustomObjects()
    service = _service(objects)
    request = DeployRequest(template="marimo", name="twice", namespace="team-data")
    service.deploy(request, DEVELOPER)
    with pytest.raises(DeploymentConflictError):
        service.deploy(request, DEVELOPER)
