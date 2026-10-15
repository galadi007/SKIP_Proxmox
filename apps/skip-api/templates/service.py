from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .dtos import (
    CapabilityDto,
    LoadedTemplate,
    ParameterDto,
    ParameterValueDto,
    TemplateAsset,
    TemplateDetails,
    TemplateReloadResult,
    TemplateSummary,
)
from .errors import (
    InvalidTemplateError,
    TemplateAssetNotFoundError,
    TemplateError,
    TemplateNotFoundError,
)
from .model import API_VERSION, KIND, AppTemplate, Parameter
from .sources import LocalTemplateLoader, TemplateLoader

logger = logging.getLogger(__name__)


class AbstractTemplateService(ABC):

    @abstractmethod
    def list(self) -> list[TemplateSummary]:
        raise NotImplementedError

    @abstractmethod
    def get(self, name: str) -> TemplateDetails:
        raise NotImplementedError

    @abstractmethod
    def get_template(self, name: str) -> AppTemplate:
        """Das geparste AppTemplate (fuer das Rendering beim Deploy)."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_logo(self, name: str) -> TemplateAsset:
        raise NotImplementedError

    @abstractmethod
    def get_asset(self, name: str, asset: str) -> TemplateAsset:
        raise NotImplementedError

    @abstractmethod
    def reload(self) -> TemplateReloadResult:
        raise NotImplementedError


class FileSystemTemplateService(AbstractTemplateService):

    TEMPLATE_FILE = "template.yaml"

    MEDIA_TYPES = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
    }

    def __init__(
        self,
        loaders: Sequence[TemplateLoader],
        api_base_path: str = "/api/templates",
    ):
        self.loaders = list(loaders)
        self.api_base_path = api_base_path.rstrip("/")

        self._templates: dict[str, LoadedTemplate] = {}

        self.reload()

    @classmethod
    def from_root(
        cls,
        root: str | Path,
        api_base_path: str = "/api/templates",
    ) -> "FileSystemTemplateService":
        return cls([LocalTemplateLoader("local", root)], api_base_path)


    def list(self) -> list[TemplateSummary]:
        result = [
            self._to_summary(loaded)
            for loaded in self._templates.values()
        ]

        return sorted(
            result,
            key=lambda item: item.display_name.lower(),
        )

    def get(self, name: str) -> TemplateDetails:
        loaded = self._get_loaded(name)
        template = loaded.template

        return TemplateDetails(
            name=template.metadata.name,
            display_name=template.spec.displayName,
            summary=template.spec.summary,
            version=template.spec.version,
            author=template.spec.author,
            categories=template.spec.categories,
            tags=template.spec.tags,
            logo_url=self._logo_url(template),
            source=loaded.source,
            revision=loaded.revision,
            description_markdown=self._load_description(loaded),
            parameters=[
                ParameterDto(
                    name=item.name,
                    display_name=item.displayName,
                    description=item.description,
                    type=item.type,
                    default=item.default,
                    required=item.required,
                    values=[
                        ParameterValueDto(
                            name=value.name,
                            display_name=value.displayName,
                            description=value.description,
                        )
                        for value in item.values
                    ],
                    pattern=item.pattern,
                    minimum=item.minimum,
                    maximum=item.maximum,
                    advanced=item.advanced,
                )
                for item in template.spec.parameters
            ],
            capabilities=[
                CapabilityDto(
                    name=item.name,
                    type=item.type,
                    class_=item.class_,
                    optional=item.when is not None,
                )
                for item in template.spec.capabilities
            ],
            components=[
                item.model_dump(exclude_none=True) for item in template.spec.components
            ],
            configuration_schema=parameters_to_json_schema(template.spec.parameters),
            form_hints=parameters_to_form_hints(template.spec.parameters),
        )

    def get_template(self, name: str) -> AppTemplate:
        return self._get_loaded(name).template

    def exists(self, name: str) -> bool:
        return name in self._templates

    def get_logo(self, name: str) -> TemplateAsset:
        loaded = self._get_loaded(name)

        logo = loaded.template.spec.logo

        if logo is None:
            raise TemplateAssetNotFoundError(name, "logo")

        return self._resolve_asset(
            loaded=loaded,
            asset=logo.file,
        )

    def get_asset(
        self,
        name: str,
        asset: str,
    ) -> TemplateAsset:
        loaded = self._get_loaded(name)

        return self._resolve_asset(
            loaded=loaded,
            asset=asset,
        )

    def reload(self) -> TemplateReloadResult:
        """Liest alle Quellen neu ein.

        Fehler einer Quelle oder eines einzelnen Templates ueberspringen nur
        diese; bei doppelten Namen gewinnt die zuerst konfigurierte Quelle.
        """
        templates: dict[str, LoadedTemplate] = {}
        errors: list[str] = []

        for loader in self.loaders:
            try:
                snapshot = loader.fetch()
            except TemplateError as exc:
                errors.append(f"Source '{loader.source}': {exc}")
                continue

            for template_file in self._discover(snapshot.root):
                try:
                    loaded = self._load_template(
                        template_file,
                        source=loader.source,
                        revision=snapshot.revision,
                    )
                except TemplateError as exc:
                    errors.append(f"Source '{loader.source}': {exc}")
                    continue

                name = loaded.template.metadata.name

                if name in templates:
                    errors.append(
                        f"Source '{loader.source}': duplicate template name "
                        f"'{name}' ignored (already provided by source "
                        f"'{templates[name].source}')"
                    )
                    continue

                templates[name] = loaded

        for error in errors:
            logger.warning("Template reload: %s", error)

        self._templates = templates

        return TemplateReloadResult(
            templates=len(templates),
            errors=errors,
        )

    def _discover(self, root: Path) -> list[Path]:
        # Ein Ordner mit template.yaml ist ein einzelnes Template,
        # sonst eine Sammlung von Template-Unterordnern.
        single = root / self.TEMPLATE_FILE
        if single.is_file():
            return [single]

        return sorted(root.glob(f"*/{self.TEMPLATE_FILE}"))

    def _load_template(
        self,
        template_file: Path,
        source: str = "local",
        revision: str | None = None,
    ) -> LoadedTemplate:
        try:
            raw = yaml.safe_load(
                template_file.read_text(encoding="utf-8")
            )

        except OSError as exc:
            raise InvalidTemplateError(
                f"Could not read template file '{template_file}': {exc}"
            ) from exc

        except yaml.YAMLError as exc:
            raise InvalidTemplateError(
                f"Invalid YAML in '{template_file}': {exc}"
            ) from exc

        if raw is None:
            raise InvalidTemplateError(
                f"Template file is empty: {template_file}"
            )

        if not isinstance(raw, dict):
            raise InvalidTemplateError(
                f"Template root must be an object: {template_file}"
            )

        try:
            template = AppTemplate.model_validate(raw)

        except ValidationError as exc:
            raise InvalidTemplateError(
                f"Invalid template '{template_file}':\n{exc}"
            ) from exc

        self._validate_template(
            template=template,
            template_file=template_file,
        )

        return LoadedTemplate(
            template=template,
            directory=template_file.parent.resolve(),
            source=source,
            revision=revision,
        )

    def _validate_template(
        self,
        template: AppTemplate,
        template_file: Path,
    ) -> None:
        if template.apiVersion != API_VERSION:
            raise InvalidTemplateError(
                f"{template_file}: unsupported apiVersion "
                f"'{template.apiVersion}' (expected '{API_VERSION}')"
            )

        if template.kind != KIND:
            raise InvalidTemplateError(
                f"{template_file}: expected kind 'AppTemplate', "
                f"got '{template.kind}'"
            )

        if (
            template.spec.description is not None
            and template.spec.description.file is not None
        ):
            description_path = self._safe_path(
                template_file.parent,
                template.spec.description.file,
            )

            if not description_path.is_file():
                raise InvalidTemplateError(
                    f"{template_file}: description file not found: "
                    f"{template.spec.description.file}"
                )

        if template.spec.logo is not None:
            logo_path = self._safe_path(
                template_file.parent,
                template.spec.logo.file,
            )

            if not logo_path.is_file():
                raise InvalidTemplateError(
                    f"{template_file}: logo file not found: "
                    f"{template.spec.logo.file}"
                )

    def _to_summary(
        self,
        loaded: LoadedTemplate,
    ) -> TemplateSummary:
        template = loaded.template

        return TemplateSummary(
            name=template.metadata.name,
            display_name=template.spec.displayName,
            summary=template.spec.summary,
            version=template.spec.version,
            author=template.spec.author,
            categories=template.spec.categories,
            tags=template.spec.tags,
            logo_url=self._logo_url(template),
            source=loaded.source,
            revision=loaded.revision,
        )

    def _logo_url(
        self,
        template: AppTemplate,
    ) -> str | None:
        if template.spec.logo is None:
            return None

        return (
            f"{self.api_base_path}/"
            f"{template.metadata.name}/logo"
        )

    def _load_description(
        self,
        loaded: LoadedTemplate,
    ) -> str | None:
        description = loaded.template.spec.description

        if description is None:
            return None

        if description.inline is not None:
            return description.inline

        if description.file is None:
            raise InvalidTemplateError(
                f"Template '{loaded.template.metadata.name}' description "
                "must define either 'file' or 'inline'"
            )

        if description.format != "markdown":
            raise InvalidTemplateError(
                f"Template '{loaded.template.metadata.name}' uses "
                f"unsupported description format "
                f"'{description.format}'"
            )

        path = self._safe_path(
            loaded.directory,
            description.file,
        )

        if not path.is_file():
            raise InvalidTemplateError(
                f"Description file not found: {path}"
            )

        try:
            return path.read_text(encoding="utf-8")

        except OSError as exc:
            raise TemplateError(
                f"Could not read description '{path}': {exc}"
            ) from exc

    def _resolve_asset(
        self,
        loaded: LoadedTemplate,
        asset: str,
    ) -> TemplateAsset:
        path = self._safe_path(
            loaded.directory,
            asset,
        )

        if not path.is_file():
            raise TemplateAssetNotFoundError(
                loaded.template.metadata.name,
                asset,
            )

        media_type = self.MEDIA_TYPES.get(
            path.suffix.lower(),
            "application/octet-stream",
        )

        return TemplateAsset(
            path=path,
            media_type=media_type,
        )

    def _get_loaded(
        self,
        name: str,
    ) -> LoadedTemplate:
        try:
            return self._templates[name]

        except KeyError as exc:
            raise TemplateNotFoundError(name) from exc

    def _safe_path(
        self,
        directory: Path,
        relative_path: str,
    ) -> Path:
        """
        Resolve a path while preventing '../' traversal outside
        the template directory.
        """

        if Path(relative_path).is_absolute():
            raise InvalidTemplateError(
                f"Absolute asset paths are not allowed: {relative_path}"
            )

        directory = directory.resolve()
        path = (directory / relative_path).resolve()

        try:
            path.relative_to(directory)

        except ValueError as exc:
            raise InvalidTemplateError(
                f"Path escapes template directory: {relative_path}"
            ) from exc

        return path


def parameters_to_json_schema(parameters: list[Parameter]) -> dict[str, Any]:
    """JSON-Schema-Darstellung der Parameter (Formular-Generatoren, API-Kompatibilitaet)."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for item in parameters:
        schema: dict[str, Any] = {"title": item.displayName or item.name}
        if item.description:
            schema["description"] = item.description
        if item.type == "enum":
            schema["type"] = "string"
            schema["enum"] = [value.name for value in item.values]
            schema["x-enumLabels"] = {
                value.name: value.displayName or value.name for value in item.values
            }
        elif item.type in ("integer", "number", "boolean"):
            schema["type"] = item.type
            if item.minimum is not None:
                schema["minimum"] = item.minimum
            if item.maximum is not None:
                schema["maximum"] = item.maximum
        else:
            schema["type"] = "string"
            if item.pattern:
                schema["pattern"] = item.pattern
        if item.default is not None:
            schema["default"] = item.default
        if item.required:
            required.append(item.name)
        properties[item.name] = schema
    result: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required:
        result["required"] = required
    return result


def parameters_to_form_hints(parameters: list[Parameter]) -> dict[str, Any]:
    return {
        "order": [item.name for item in parameters],
        "labels": {item.name: item.displayName or item.name for item in parameters},
        "advanced": [item.name for item in parameters if item.advanced],
    }
