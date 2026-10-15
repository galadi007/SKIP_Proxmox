from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .model import AppTemplate


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TemplateSummary(ApiModel):
    name: str
    display_name: str
    summary: str | None = None
    version: str
    author: str | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    logo_url: str | None = None
    # Herkunft: Name der Template-Quelle und ggf. Commit-SHA
    source: str | None = None
    revision: str | None = None


class TemplateReloadResult(ApiModel):
    templates: int
    errors: list[str] = Field(default_factory=list)


class ParameterValueDto(ApiModel):
    name: str
    display_name: str | None = None
    description: str | None = None


class ParameterDto(ApiModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    type: str
    default: Any = None
    required: bool = False
    values: list[ParameterValueDto] = Field(default_factory=list)
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    advanced: bool = False


class CapabilityDto(ApiModel):
    name: str
    type: str
    class_: str = Field(default="standard", serialization_alias="class")
    optional: bool = False


class TemplateDetails(TemplateSummary):
    description_markdown: str | None = None
    parameters: list[ParameterDto] = Field(default_factory=list)
    capabilities: list[CapabilityDto] = Field(default_factory=list)
    components: list[dict[str, Any]] = Field(default_factory=list)
    # JSON-Schema-Sicht auf die Parameter (fuer Formular-Generatoren)
    configuration_schema: dict[str, Any] = Field(default_factory=dict)
    form_hints: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class TemplateAsset:
    path: Path
    media_type: str


@dataclass(frozen=True)
class LoadedTemplate:
    template: AppTemplate
    directory: Path
    source: str = "local"
    revision: str | None = None
