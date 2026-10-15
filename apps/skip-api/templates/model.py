"""Datenmodell des AppTemplate-Formats (platform.skip.io/v1alpha1).

Ein AppTemplate ist keine CRD: das Backend liest es aus `templates/<name>/template.yaml`
und uebersetzt es beim Deploy in eine Instanz der generischen Application-RGD
(`deploy/crds/application-rgd.yaml`) plus CapabilityClaims.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

API_VERSION = "platform.skip.io/v1alpha1"
KIND = "AppTemplate"

ParameterType = Literal["string", "integer", "number", "boolean", "enum"]


class TemplateMetadata(BaseModel):
    name: str


class DescriptionSpec(BaseModel):
    format: str = "markdown"
    file: str | None = None
    inline: str | None = None


class LogoSpec(BaseModel):
    file: str


class ParameterValue(BaseModel):
    """Ein Enum-Wert. Zusatzfelder (z. B. `image`, `cpu`) sind erlaubt und
    ueber `${parameters.<param>.<feld>}` in Komponenten referenzierbar."""

    model_config = ConfigDict(extra="allow")

    name: str
    displayName: str | None = None
    description: str | None = None

    @property
    def extra(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class Parameter(BaseModel):
    name: str
    displayName: str | None = None
    description: str | None = None
    type: ParameterType = "string"
    default: Any = None
    required: bool = False
    values: list[ParameterValue] = Field(default_factory=list)
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    advanced: bool = False

    @model_validator(mode="after")
    def _check_enum(self) -> "Parameter":
        if self.type == "enum":
            if not self.values:
                raise ValueError(f"parameter '{self.name}': enum needs 'values'")
            names = [value.name for value in self.values]
            if len(set(names)) != len(names):
                raise ValueError(f"parameter '{self.name}': duplicate enum values")
            if self.default is not None and self.default not in names:
                raise ValueError(
                    f"parameter '{self.name}': default '{self.default}' not in values"
                )
        elif self.values:
            raise ValueError(f"parameter '{self.name}': 'values' only allowed for enum")
        return self

    def value(self, name: str) -> ParameterValue | None:
        return next((value for value in self.values if value.name == name), None)


class CapabilitySpec(BaseModel):
    """Angeforderter Plattformdienst; wird beim Deploy als CapabilityClaim angelegt."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    type: str
    class_: str = Field(default="standard", alias="class")
    # Optionaler Ausdruck (z. B. `${parameters.llmAccess}`); ist er falsy,
    # wird die Capability fuer dieses Deployment nicht angefordert.
    when: str | bool | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class PortSpec(BaseModel):
    name: str
    containerPort: int
    protocol: str = "TCP"


class ExposeSpec(BaseModel):
    """Gibt einen Container-Port als Service-Port frei (Name des Ports)."""

    name: str
    type: Literal["http", "tcp"] = "http"
    port: str


class EnvVarSpec(BaseModel):
    name: str
    value: Any


class ResourceAmounts(BaseModel):
    cpu: str | int | float | None = None
    memory: str | None = None


class ResourcesSpec(BaseModel):
    requests: ResourceAmounts | None = None
    limits: ResourceAmounts | None = None


class StorageSpec(BaseModel):
    size: str
    mountPath: str


class BindingEnv(BaseModel):
    endpoint: str | None = None
    credential: str | None = None


class BindingSpec(BaseModel):
    capability: str
    env: BindingEnv = Field(default_factory=BindingEnv)


class ComponentSpec(BaseModel):
    """Ein Container samt Service/Storage; wird zu einer Application-Instanz `<app>-<name>`."""

    name: str
    image: str
    command: list[str] = Field(default_factory=list)
    args: list[str] = Field(default_factory=list)
    ports: list[PortSpec] = Field(default_factory=list)
    expose: list[ExposeSpec] = Field(default_factory=list)
    env: list[EnvVarSpec] = Field(default_factory=list)
    resources: ResourcesSpec | None = None
    storage: StorageSpec | None = None
    bindings: list[BindingSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_refs(self) -> "ComponentSpec":
        if not re.fullmatch(r"[a-z0-9]([-a-z0-9]{0,14}[a-z0-9])?", self.name):
            raise ValueError(
                f"component '{self.name}': name must be lowercase alphanumeric "
                "with hyphens, max 16 characters"
            )
        port_names = [port.name for port in self.ports]
        if len(set(port_names)) != len(port_names):
            raise ValueError(f"component '{self.name}': duplicate port names")
        for expose in self.expose:
            if expose.port not in port_names:
                raise ValueError(
                    f"component '{self.name}': expose '{expose.name}' references "
                    f"unknown port '{expose.port}'"
                )
        return self


class AppTemplateSpec(BaseModel):
    displayName: str
    summary: str | None = None
    version: str
    author: str | None = None

    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    description: DescriptionSpec | None = None
    logo: LogoSpec | None = None

    parameters: list[Parameter] = Field(default_factory=list)
    capabilities: list[CapabilitySpec] = Field(default_factory=list)
    components: list[ComponentSpec] = Field(default_factory=list)

    @field_validator("version", mode="before")
    @classmethod
    def _version_as_string(cls, value: Any) -> str:
        return str(value)

    @field_validator("author", mode="before")
    @classmethod
    def _author_as_string(cls, value: Any) -> str | None:
        # Kompatibel zur frueheren Form `author: {name: ...}`
        if isinstance(value, dict):
            return value.get("name")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> "AppTemplateSpec":
        if not self.components:
            raise ValueError("spec.components must contain at least one component")

        def unique(kind: str, names: list[str]) -> None:
            if len(set(names)) != len(names):
                raise ValueError(f"duplicate {kind} names: {names}")

        unique("parameter", [item.name for item in self.parameters])
        unique("capability", [item.name for item in self.capabilities])
        unique("component", [item.name for item in self.components])

        capability_names = {item.name for item in self.capabilities}
        for component in self.components:
            for binding in component.bindings:
                if binding.capability not in capability_names:
                    raise ValueError(
                        f"component '{component.name}' binds unknown capability "
                        f"'{binding.capability}'"
                    )
        return self

    def parameter(self, name: str) -> Parameter | None:
        return next((item for item in self.parameters if item.name == name), None)


class AppTemplate(BaseModel):
    apiVersion: str
    kind: str
    metadata: TemplateMetadata
    spec: AppTemplateSpec
