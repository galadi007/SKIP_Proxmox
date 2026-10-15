import pytest

from auth.dtos import AuthenticatedUser
from auth.entitlements import (
    Entitlements,
    EntitlementExceededError,
    StaticEntitlementProvider,
    check_deployment,
    parse_cpu,
    parse_memory,
)
from deploy.errors import InvalidDeploymentError
from deploy.render import AppsUrlSettings, coerce_values, render_application
from templates.model import AppTemplate


def _template(**overrides) -> AppTemplate:
    raw = {
        "apiVersion": "platform.skip.io/v1alpha1",
        "kind": "AppTemplate",
        "metadata": {"name": "demo"},
        "spec": {
            "displayName": "Demo",
            "version": "1.0.0",
            "parameters": [
                {
                    "name": "size",
                    "type": "enum",
                    "default": "s",
                    "values": [
                        {"name": "s", "cpu": "1", "memory": "1Gi"},
                        {"name": "l", "cpu": "4", "memory": "8Gi"},
                    ],
                },
                {"name": "replicasLabel", "type": "integer", "default": 1, "minimum": 1},
                {"name": "debug", "type": "boolean", "default": False},
                {"name": "storage", "type": "string", "pattern": "^[0-9]+Gi$", "default": "1Gi"},
            ],
            "capabilities": [
                {
                    "name": "llm",
                    "type": "llm-access",
                    "when": "${parameters.debug}",
                    "properties": {"models": ["m1"]},
                }
            ],
            "components": [
                {
                    "name": "app",
                    "image": "img:${parameters.size}",
                    "ports": [{"name": "http", "containerPort": 9000}],
                    "env": [
                        {"name": "DEBUG", "value": "${parameters.debug}"},
                        {"name": "SIZE", "value": "size-${parameters.size}-${parameters.size.cpu}"},
                    ],
                    "resources": {"limits": {"cpu": "${parameters.size.cpu}", "memory": "${parameters.size.memory}"}},
                    "storage": {"size": "${parameters.storage}", "mountPath": "/data"},
                    "bindings": [{"capability": "llm", "env": {"credential": "KEY"}}],
                }
            ],
            **overrides,
        },
    }
    return AppTemplate.model_validate(raw)


def test_coerce_values_applies_defaults_and_types() -> None:
    values = coerce_values(_template(), {"replicasLabel": "3", "debug": "on"})
    assert values == {"size": "s", "replicasLabel": 3, "debug": True, "storage": "1Gi"}


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"size": "xl"}, "ungueltiger Wert"),
        ({"replicasLabel": "0"}, "mindestens"),
        ({"storage": "5Mi"}, "Muster"),
        ({"unknown": "x"}, "Unbekannte Parameter"),
        ({"debug": "maybe"}, "true/false"),
    ],
)
def test_coerce_values_rejects_invalid_input(raw: dict, message: str) -> None:
    with pytest.raises(InvalidDeploymentError, match=message):
        coerce_values(_template(), raw)


def test_render_resolves_enum_extra_fields_and_interpolation() -> None:
    rendered = render_application(_template(), "demo-app", {"size": "l"}, namespace="ns")
    [component] = rendered.components
    assert component.instance == "demo-app-app"
    spec = component.spec
    assert spec["app"] == "demo-app" and spec["component"] == "app"
    assert spec["image"] == "img:l"
    assert spec["ports"] == [{"name": "http", "containerPort": 9000, "protocol": "TCP"}]
    assert spec["servicePorts"] == []  # kein expose -> kein Service
    assert spec["resources"] == {"limits": {"cpu": "4", "memory": "8Gi"}}
    env = {item["name"]: item["value"] for item in spec["env"]}
    assert env == {"DEBUG": "false", "SIZE": "size-l-4"}
    # Capability mit when=false: kein Claim, kein Binding
    assert rendered.claims == []


def test_render_optional_capability_when_enabled() -> None:
    rendered = render_application(_template(), "demo-app", {"debug": "true"})
    assert [claim.name for claim in rendered.claims] == ["demo-app-llm"]
    assert rendered.components[0].spec["env"][-1] == {
        "name": "KEY",
        "valueFrom": {"secretKeyRef": {"name": "demo-app-llm-credentials", "key": "api-key"}},
    }


def test_render_multiple_components_with_cross_references() -> None:
    template = _template(components=[
        {
            "name": "web",
            "image": "web:1",
            "ports": [{"name": "http", "containerPort": 80}],
            "expose": [{"name": "web", "port": "http"}],
            "env": [
                {"name": "DB", "value": "postgres://${components.db.host}:${components.db.ports.pg}/x"},
                {"name": "APP", "value": "${app.name}@${app.namespace}"},
            ],
        },
        {
            "name": "db",
            "image": "postgres:16",
            "command": ["postgres"],
            "args": ["-c", "max_connections=${parameters.replicasLabel}"],
            "ports": [{"name": "pg", "containerPort": 5432}],
            "expose": [{"name": "pg", "type": "tcp", "port": "pg"}],
            "storage": {"size": "2Gi", "mountPath": "/var/lib/postgresql/data"},
        },
    ])
    rendered = render_application(
        template, "shop", {"replicasLabel": 50}, namespace="team-data",
        urls=AppsUrlSettings(domain="apps.example.org", scheme="https", port="", ingress_class="nginx"),
    )
    web, db = rendered.components
    assert (web.instance, db.instance) == ("shop-web", "shop-db")
    assert web.url == "https://shop.team-data.apps.example.org" and db.url is None
    assert web.spec["ingress"] == {
        "enabled": True, "host": "shop.team-data.apps.example.org",
        "className": "nginx", "portName": "web",
    }
    env = {item["name"]: item["value"] for item in web.spec["env"]}
    assert env["DB"] == "postgres://shop-db:5432/x"
    assert env["APP"] == "shop@team-data"
    assert web.spec["storage"] == {"enabled": False} and web.spec["volumes"] == []
    assert db.spec["command"] == ["postgres"]
    assert db.spec["args"] == ["-c", "max_connections=50"]
    assert db.spec["servicePorts"] == [{"name": "pg", "port": 5432, "targetPort": "pg"}]
    assert db.spec["storage"] == {"enabled": True, "size": "2Gi"}
    assert db.spec["volumes"][0]["persistentVolumeClaim"]["claimName"] == "shop-db"


def test_render_rejects_unknown_references() -> None:
    template = _template(components=[
        {"name": "a", "image": "x", "env": [{"name": "X", "value": "${components.nope.host}"}]},
    ])
    with pytest.raises(InvalidDeploymentError, match="unbekannte Komponente"):
        render_application(template, "demo", {})
    template = _template(components=[
        {"name": "a", "image": "x", "env": [{"name": "X", "value": "${secrets.x}"}]},
    ])
    with pytest.raises(InvalidDeploymentError, match="Unbekannte Referenz"):
        render_application(template, "demo", {})


def test_quantities_and_entitlement_checks() -> None:
    assert parse_cpu("500m") == 500 and parse_cpu("2") == 2000
    assert parse_memory("1Gi") == 2**30 and parse_memory("500M") == 500_000_000

    limited = Entitlements(max_apps=1, max_cpu_per_app="2", max_memory_per_app="4Gi",
                           capability_classes=frozenset({"standard"}))
    check_deployment(limited, owned_apps=0, resources={"limits": {"cpu": "2", "memory": "4Gi"}},
                     capability_classes={"standard"})
    with pytest.raises(EntitlementExceededError, match="Maximale Anzahl"):
        check_deployment(limited, owned_apps=1, resources=None, capability_classes=set())
    with pytest.raises(EntitlementExceededError, match="CPU-Limit"):
        check_deployment(limited, owned_apps=0, resources={"limits": {"cpu": "4"}},
                         capability_classes=set())
    with pytest.raises(EntitlementExceededError, match="Capability-Klasse"):
        check_deployment(limited, owned_apps=0, resources=None, capability_classes={"premium"})

    provider = StaticEntitlementProvider(limited)
    assert provider.for_user(AuthenticatedUser(username="root", groups=["skip-admins"])).max_apps is None
    assert provider.for_user(AuthenticatedUser(username="max")).max_apps == 1


def test_render_second_http_component_gets_prefixed_host() -> None:
    template = _template(components=[
        {"name": "web", "image": "w", "ports": [{"name": "http", "containerPort": 80}],
         "expose": [{"name": "web", "port": "http"}]},
        {"name": "admin", "image": "a", "ports": [{"name": "http", "containerPort": 81}],
         "expose": [{"name": "ui", "port": "http"}]},
    ])
    rendered = render_application(template, "shop", {}, namespace="ns", urls=AppsUrlSettings())
    assert [c.url for c in rendered.components] == [
        "http://shop.ns.apps.localhost:8080",
        "http://shop-admin.ns.apps.localhost:8080",
    ]
