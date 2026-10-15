"""Uebersetzt ein AppTemplate plus Nutzerparameter in Application-Instanzen.

Pipeline: AppTemplate (templates/<name>/template.yaml)
       -> Parameter des Benutzers (Formular)
       -> je Komponente eine Application-Instanz `<app>-<komponente>`
          (deploy/crds/application-rgd.yaml) + CapabilityClaims fuer die App
       -> KRO erzeugt Deployment/Service/PVC, der capability-operator die Bindings.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from templates.model import AppTemplate, ComponentSpec, Parameter

from .errors import InvalidDeploymentError

REFERENCE_RE = re.compile(r"\$\{\s*([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*}")
INSTANCE_NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")

# Konventionen des capability-operators (apps/capability-operator/capabilities/litellm)
CLAIM_API_VERSION = "platform.skip.io/v1alpha1"
CLAIM_KIND = "CapabilityClaim"
CLAIM_PLURAL = "capabilityclaims"
CLAIM_SECRET_KEY = "api-key"
CLAIM_ENDPOINT_KEY = "endpoint"

DATA_VOLUME = "data"
TRUE_VALUES = {"true", "1", "yes", "on"}
FALSE_VALUES = {"false", "0", "no", "off", ""}


def instance_name(app_name: str, component_name: str) -> str:
    """Name der Application-Instanz und damit des Service (DNS) einer Komponente."""
    return f"{app_name}-{component_name}"


def claim_name(app_name: str, capability_name: str) -> str:
    return f"{app_name}-{capability_name}"


def claim_secret_name(name: str) -> str:
    return f"{name}-credentials"


@dataclass(frozen=True)
class ClaimPlan:
    name: str
    capability: str
    type: str
    class_: str
    properties: dict[str, Any] = field(default_factory=dict)

    def manifest(self, namespace: str) -> dict[str, Any]:
        return {
            "apiVersion": CLAIM_API_VERSION,
            "kind": CLAIM_KIND,
            "metadata": {"name": self.name, "namespace": namespace},
            "spec": {"type": self.type, "properties": dict(self.properties)},
        }


@dataclass(frozen=True)
class AppsUrlSettings:
    """Wie Apps von aussen erreichbar sind (Ingress-Host und daraus die URL)."""

    domain: str = "apps.localhost"
    ingress_class: str = "traefik"
    scheme: str = "http"
    port: str = "8080"  # leer = Standardport des Schemas

    @classmethod
    def from_env(cls) -> "AppsUrlSettings":
        return cls(
            domain=os.environ.get("APPS_DOMAIN", "apps.localhost").strip(),
            ingress_class=os.environ.get("APPS_INGRESS_CLASS", "traefik").strip(),
            scheme=os.environ.get("APPS_SCHEME", "http").strip() or "http",
            port=os.environ.get("APPS_PUBLIC_PORT", "8080").strip(),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.domain)

    def host(self, app_name: str, namespace: str, component: str | None = None) -> str:
        """`<app>.<namespace>.<domain>`; weitere HTTP-Komponenten `<app>-<komponente>.…`."""
        prefix = app_name if component is None else f"{app_name}-{component}"
        return f"{prefix}.{namespace}.{self.domain}"

    def url(self, host: str) -> str:
        port = f":{self.port}" if self.port else ""
        return f"{self.scheme}://{host}{port}"


@lru_cache
def get_apps_url_settings() -> AppsUrlSettings:
    return AppsUrlSettings.from_env()


@dataclass(frozen=True)
class ComponentPlan:
    name: str
    instance: str
    spec: dict[str, Any]
    url: str | None = None


@dataclass(frozen=True)
class RenderedApplication:
    components: list[ComponentPlan]
    claims: list[ClaimPlan]
    values: dict[str, Any]


# ---------------------------------------------------------------------------
# Parameter
# ---------------------------------------------------------------------------


def coerce_values(template: AppTemplate, raw: dict[str, Any]) -> dict[str, Any]:
    """Validiert die Formulareingaben gegen die Parameter und wandelt Typen um."""
    known = {item.name for item in template.spec.parameters}
    unknown = set(raw) - known
    if unknown:
        raise InvalidDeploymentError(
            f"Unbekannte Parameter: {', '.join(sorted(unknown))}"
        )

    values: dict[str, Any] = {}
    for item in template.spec.parameters:
        provided = raw.get(item.name)
        if provided is None or provided == "":
            if item.default is not None:
                values[item.name] = _coerce(item, item.default)
            elif item.required:
                raise InvalidDeploymentError(f"Parameter '{item.name}' fehlt")
            else:
                values[item.name] = None
            continue
        values[item.name] = _coerce(item, provided)
    return values


def _coerce(item: Parameter, value: Any) -> Any:
    label = item.displayName or item.name
    if item.type == "enum":
        if item.value(str(value)) is None:
            raise InvalidDeploymentError(
                f"'{label}': ungueltiger Wert '{value}' "
                f"(erlaubt: {', '.join(v.name for v in item.values)})"
            )
        return str(value)
    if item.type == "boolean":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in TRUE_VALUES:
            return True
        if text in FALSE_VALUES:
            return False
        raise InvalidDeploymentError(f"'{label}': erwartet true/false")
    if item.type in ("integer", "number"):
        try:
            number = int(value) if item.type == "integer" else float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidDeploymentError(f"'{label}': erwartet eine Zahl") from exc
        if item.minimum is not None and number < item.minimum:
            raise InvalidDeploymentError(f"'{label}': mindestens {item.minimum}")
        if item.maximum is not None and number > item.maximum:
            raise InvalidDeploymentError(f"'{label}': hoechstens {item.maximum}")
        return number
    text = str(value)
    if item.pattern and not re.fullmatch(item.pattern, text):
        raise InvalidDeploymentError(
            f"'{label}': '{text}' entspricht nicht dem Muster {item.pattern}"
        )
    return text


# ---------------------------------------------------------------------------
# Referenzen: ${parameters.x[.feld]}, ${app.name|namespace},
#             ${components.<name>.host}, ${components.<name>.ports.<port>}
# ---------------------------------------------------------------------------


class Renderer:
    def __init__(
        self,
        template: AppTemplate,
        values: dict[str, Any],
        app_name: str,
        namespace: str,
    ) -> None:
        self.template = template
        self.values = values
        self.app_name = app_name
        self.namespace = namespace

    def resolve(self, path: str) -> Any:
        root, _, rest = path.partition(".")
        if root == "parameters":
            return self._resolve_parameter(rest, path)
        if root == "app":
            if rest == "name":
                return self.app_name
            if rest == "namespace":
                return self.namespace
            raise InvalidDeploymentError(f"Unbekannte Referenz '${{{path}}}'")
        if root == "components":
            return self._resolve_component(rest, path)
        raise InvalidDeploymentError(f"Unbekannte Referenz '${{{path}}}'")

    def _resolve_parameter(self, rest: str, path: str) -> Any:
        name, _, field_path = rest.partition(".")
        parameter = self.template.spec.parameter(name)
        if parameter is None:
            raise InvalidDeploymentError(
                f"Template referenziert unbekannten Parameter '{name}'"
            )
        value = self.values.get(name)
        if not field_path:
            return value
        if parameter.type != "enum":
            raise InvalidDeploymentError(
                f"'${{{path}}}': nur Enum-Parameter haben Zusatzfelder"
            )
        selected = parameter.value(str(value))
        current: Any = selected.extra if selected else {}
        for part in field_path.split("."):
            if not isinstance(current, dict) or part not in current:
                raise InvalidDeploymentError(
                    f"'${{{path}}}': Feld '{part}' fehlt am Wert '{value}'"
                )
            current = current[part]
        return current

    def _resolve_component(self, rest: str, path: str) -> Any:
        name, _, attribute = rest.partition(".")
        component = next(
            (item for item in self.template.spec.components if item.name == name),
            None,
        )
        if component is None:
            raise InvalidDeploymentError(
                f"Template referenziert unbekannte Komponente '{name}'"
            )
        if attribute == "host":
            return instance_name(self.app_name, name)
        if attribute.startswith("ports."):
            port_name = attribute.removeprefix("ports.")
            port = next((p for p in component.ports if p.name == port_name), None)
            if port is None:
                raise InvalidDeploymentError(
                    f"'${{{path}}}': Komponente '{name}' hat keinen Port '{port_name}'"
                )
            return port.containerPort
        raise InvalidDeploymentError(f"Unbekannte Referenz '${{{path}}}'")

    def render(self, value: Any) -> Any:
        if isinstance(value, str):
            match = REFERENCE_RE.fullmatch(value.strip())
            if match:
                return self.resolve(match.group(1))
            return REFERENCE_RE.sub(lambda m: str(self.resolve(m.group(1))), value)
        if isinstance(value, list):
            return [self.render(item) for item in value]
        if isinstance(value, dict):
            return {key: self.render(item) for key, item in value.items()}
        return value

    def truthy(self, expression: str | bool | None) -> bool:
        if expression is None:
            return True
        rendered = self.render(expression) if isinstance(expression, str) else expression
        if isinstance(rendered, str):
            return rendered.strip().lower() in TRUE_VALUES
        return bool(rendered)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_application(
    template: AppTemplate,
    app_name: str,
    raw_values: dict[str, Any],
    namespace: str = "",
    urls: AppsUrlSettings | None = None,
) -> RenderedApplication:
    """Erzeugt die Application-Instanzen (eine je Komponente) und die CapabilityClaims."""
    values = coerce_values(template, raw_values)
    urls = urls if urls is not None else AppsUrlSettings()
    renderer = Renderer(template, values, app_name, namespace)
    spec = template.spec

    declared = {item.name for item in spec.capabilities}
    claims: list[ClaimPlan] = []
    for capability in spec.capabilities:
        if not renderer.truthy(capability.when):
            continue
        claims.append(
            ClaimPlan(
                name=claim_name(app_name, capability.name),
                capability=capability.name,
                type=capability.type,
                class_=capability.class_,
                properties=renderer.render(capability.properties),
            )
        )
    active = {plan.capability: plan for plan in claims}

    # Die erste HTTP-Komponente bekommt den App-Host, weitere `<app>-<komponente>`.
    primary = next(
        (c.name for c in spec.components if any(e.type == "http" for e in c.expose)),
        None,
    )
    components = [
        _render_component(component, renderer, app_name, active, declared)
        for component in spec.components
    ]
    if urls.enabled and namespace:
        components = [
            _with_ingress(plan, component, app_name, namespace, urls, primary)
            for plan, component in zip(components, spec.components)
        ]
    return RenderedApplication(components=components, claims=claims, values=values)


def _with_ingress(
    plan: ComponentPlan,
    component: ComponentSpec,
    app_name: str,
    namespace: str,
    urls: AppsUrlSettings,
    primary: str | None,
) -> ComponentPlan:
    expose = next((e for e in component.expose if e.type == "http"), None)
    if expose is None:
        return plan
    host = urls.host(
        app_name, namespace, None if component.name == primary else component.name
    )
    spec = dict(plan.spec)
    spec["ingress"] = {
        "enabled": True,
        "host": host,
        "className": urls.ingress_class,
        "portName": expose.name,
    }
    return ComponentPlan(name=plan.name, instance=plan.instance, spec=spec, url=urls.url(host))


def _render_component(
    component: ComponentSpec,
    renderer: Renderer,
    app_name: str,
    active: dict[str, ClaimPlan],
    declared: set[str],
) -> ComponentPlan:
    name = instance_name(app_name, component.name)
    if not INSTANCE_NAME_RE.fullmatch(name):
        raise InvalidDeploymentError(
            f"Instanzname '{name}' ungueltig (App-Name plus Komponente, max. 63 Zeichen)"
        )

    env: list[dict[str, Any]] = [
        {"name": item.name, "value": _as_env_string(renderer.render(item.value))}
        for item in component.env
    ]
    for binding in component.bindings:
        plan = active.get(binding.capability)
        if plan is None:
            if binding.capability in declared:
                continue  # Capability fuer dieses Deployment nicht angefordert
            raise InvalidDeploymentError(
                f"Binding auf unbekannte Capability '{binding.capability}'"
            )
        secret = claim_secret_name(plan.name)
        if binding.env.endpoint:
            env.append(_secret_env(binding.env.endpoint, secret, CLAIM_ENDPOINT_KEY))
        if binding.env.credential:
            env.append(_secret_env(binding.env.credential, secret, CLAIM_SECRET_KEY))

    ports_by_name = {port.name: port for port in component.ports}
    spec: dict[str, Any] = {
        "app": app_name,
        "component": component.name,
        "image": str(renderer.render(component.image)),
        "command": [str(renderer.render(item)) for item in component.command],
        "args": [str(renderer.render(item)) for item in component.args],
        "ports": [
            {
                "name": port.name,
                "containerPort": port.containerPort,
                "protocol": port.protocol,
            }
            for port in component.ports
        ],
        "servicePorts": [
            {
                "name": expose.name,
                "port": ports_by_name[expose.port].containerPort,
                "targetPort": expose.port,
            }
            for expose in component.expose
        ],
        "env": env,
        "storage": {"enabled": False},
        "volumes": [],
        "volumeMounts": [],
        "ingress": {"enabled": False},
    }
    if component.resources is not None:
        resources = renderer.render(component.resources.model_dump(exclude_none=True))
        spec["resources"] = {
            key: {field: str(amount) for field, amount in amounts.items()}
            for key, amounts in resources.items()
        }
    if component.storage is not None:
        spec["storage"] = {
            "enabled": True,
            "size": str(renderer.render(component.storage.size)),
        }
        spec["volumes"] = [
            {"name": DATA_VOLUME, "persistentVolumeClaim": {"claimName": name}}
        ]
        spec["volumeMounts"] = [
            {
                "name": DATA_VOLUME,
                "mountPath": str(renderer.render(component.storage.mountPath)),
            }
        ]
    return ComponentPlan(name=component.name, instance=name, spec=spec)


def _secret_env(name: str, secret: str, key: str) -> dict[str, Any]:
    return {"name": name, "valueFrom": {"secretKeyRef": {"name": secret, "key": key}}}


def _as_env_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
