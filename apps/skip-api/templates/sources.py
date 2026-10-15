"""Template-Quellen: machen AppTemplates aus lokalen Ordnern oder Git-Repos
als lokales Verzeichnis verfuegbar, das der Template-Service einliest."""

import logging
import os
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, Annotated, Literal, Protocol
from urllib.parse import quote

import httpx
import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .errors import TemplateSourceError

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_GITHUB_TOKEN_ENV = "GITHUB_TEMPLATES_TOKEN"
DEFAULT_CACHE_DIR = Path(tempfile.gettempdir()) / "skip-templates"
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024

_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SOURCE_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"


@dataclass(frozen=True)
class TemplateSnapshot:
    # Lokaler Ordner: entweder ein einzelnes Template oder eine Sammlung
    root: Path
    # Aufgeloester Commit-SHA (None bei lokalen Quellen)
    revision: str | None = None


class TemplateLoader(Protocol):
    source: str

    def fetch(self) -> TemplateSnapshot: ...


# --- Konfiguration --------------------------------------------------------


class _SourceSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(pattern=_SOURCE_NAME_PATTERN, max_length=63)


class LocalSourceSpec(_SourceSpec):
    type: Literal["local"] = "local"
    path: str


class GitHubSourceSpec(_SourceSpec):
    type: Literal["github"]
    repository: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    # Tag oder Commit-SHA empfohlen; ein Branch folgt bei jedem Reload
    ref: str = "HEAD"
    # Unterordner im Repo (leer = Repo-Wurzel)
    path: str = ""
    token_env: str = Field(default=DEFAULT_GITHUB_TOKEN_ENV, alias="tokenEnv")
    api_url: str = Field(default=DEFAULT_GITHUB_API_URL, alias="apiUrl")

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        return normalize_repo_path(value)


TemplateSourceSpec = Annotated[
    LocalSourceSpec | GitHubSourceSpec,
    Field(discriminator="type"),
]


class TemplateSourcesConfig(BaseModel):
    sources: list[TemplateSourceSpec]

    @model_validator(mode="after")
    def _unique_names(self) -> "TemplateSourcesConfig":
        names = [source.name for source in self.sources]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate template source names: {sorted(duplicates)}"
            )
        return self


def normalize_repo_path(value: str) -> str:
    path = PurePosixPath(value.strip().strip("/"))
    if ".." in path.parts:
        raise ValueError(f"Repository path must not contain '..': {value}")
    return "" if str(path) == "." else str(path)


def parse_source_shorthand(value: str) -> LocalSourceSpec | GitHubSourceSpec:
    """Kurzform fuer Env/CLI.

    - ``github:<owner>/<repo>[@<ref>][#<path>]``
    - ``local:<path>`` oder ein einfacher Pfad
    """
    value = value.strip()

    if value.startswith("github:"):
        rest, _, path = value.removeprefix("github:").partition("#")
        repository, _, ref = rest.partition("@")
        name = re.sub(r"[^a-z0-9]+", "-", repository.lower()).strip("-")
        return GitHubSourceSpec(
            name=name[:63].strip("-"),
            type="github",
            repository=repository,
            ref=ref or "HEAD",
            path=path,
        )

    path = value.removeprefix("local:")
    name = re.sub(r"[^a-z0-9]+", "-", Path(path).name.lower()).strip("-")
    return LocalSourceSpec(name=name[:63].strip("-") or "local", path=path)


def load_sources_file(path: Path) -> TemplateSourcesConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return TemplateSourcesConfig.model_validate(raw or {"sources": []})
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise TemplateSourceError(
            f"Invalid template sources file '{path}': {exc}"
        ) from exc


def load_template_loaders_from_env(default_root: Path) -> list[TemplateLoader]:
    """Reihenfolge: TEMPLATE_SOURCES_FILE, TEMPLATE_SOURCES, TEMPLATES_DIR."""
    cache_dir = Path(
        os.environ.get("TEMPLATES_CACHE_DIR", "").strip() or DEFAULT_CACHE_DIR
    )
    sources_file = os.environ.get("TEMPLATE_SOURCES_FILE", "").strip()
    shorthand = os.environ.get("TEMPLATE_SOURCES", "").strip()

    if sources_file:
        specs = load_sources_file(Path(sources_file)).sources
    elif shorthand:
        try:
            specs = TemplateSourcesConfig(
                sources=[
                    parse_source_shorthand(item)
                    for item in shorthand.split(",")
                    if item.strip()
                ]
            ).sources
        except ValidationError as exc:
            raise TemplateSourceError(
                f"Invalid TEMPLATE_SOURCES: {exc}"
            ) from exc
    else:
        root = os.environ.get("TEMPLATES_DIR", "").strip() or str(default_root)
        specs = [LocalSourceSpec(name="local", path=root)]

    return [build_loader(spec, cache_dir) for spec in specs]


def build_loader(
    spec: LocalSourceSpec | GitHubSourceSpec,
    cache_dir: Path,
) -> TemplateLoader:
    if isinstance(spec, LocalSourceSpec):
        return LocalTemplateLoader(spec.name, spec.path)

    return GitHubTemplateLoader(
        spec.name,
        spec.repository,
        ref=spec.ref,
        path=spec.path,
        token=os.environ.get(spec.token_env, "").strip() or None,
        api_url=spec.api_url,
        cache_dir=cache_dir,
    )


# --- Loader ---------------------------------------------------------------


class LocalTemplateLoader:

    def __init__(self, source: str, path: str | Path) -> None:
        self.source = source
        self.path = Path(path).resolve()

    def fetch(self) -> TemplateSnapshot:
        if not self.path.is_dir():
            raise TemplateSourceError(
                f"Template directory does not exist: {self.path}"
            )
        return TemplateSnapshot(root=self.path)


class GitHubTemplateLoader:
    """Laedt einen (Unter-)Ordner eines GitHub-Repos als Tarball.

    Pro Quelle liegt je Commit-SHA ein entpackter Snapshot im Cache. Ist
    GitHub nicht erreichbar, wird der letzte Snapshot weiterverwendet.
    """

    def __init__(
        self,
        source: str,
        repository: str,
        *,
        ref: str = "HEAD",
        path: str = "",
        token: str | None = None,
        api_url: str = DEFAULT_GITHUB_API_URL,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        max_archive_bytes: int = MAX_ARCHIVE_BYTES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.source = source
        self.repository = repository
        self.ref = ref
        self.path = normalize_repo_path(path)
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.cache_root = Path(cache_dir) / source
        self.max_archive_bytes = max_archive_bytes
        self._transport = transport

    def fetch(self) -> TemplateSnapshot:
        try:
            with self._client() as client:
                sha = self._resolve_ref(client)
                target = self.cache_root / sha
                if not target.is_dir():
                    self._download(client, sha, target)
            self._prune(keep=sha)

        except (
            httpx.HTTPError,
            tarfile.TarError,
            OSError,
            TemplateSourceError,
        ) as exc:
            target = self._latest_snapshot()
            if target is None:
                raise TemplateSourceError(
                    f"Could not fetch {self._label()}: {exc}"
                ) from exc
            logger.warning(
                "Could not fetch %s, using cached snapshot %s: %s",
                self._label(),
                target.name,
                exc,
            )

        root = target / self.path if self.path else target
        if not root.is_dir():
            raise TemplateSourceError(
                f"Path '{self.path}' not found in {self._label()} "
                f"(commit {target.name})"
            )
        return TemplateSnapshot(root=root, revision=target.name)

    def _client(self) -> httpx.Client:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return httpx.Client(
            base_url=self.api_url,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
            transport=self._transport,
        )

    def _resolve_ref(self, client: httpx.Client) -> str:
        response = client.get(
            f"/repos/{self.repository}/commits/{quote(self.ref, safe='/')}",
            headers={"Accept": "application/vnd.github.sha"},
        )
        response.raise_for_status()
        sha = response.text.strip()
        if not _SHA_PATTERN.match(sha):
            raise TemplateSourceError(
                f"Unexpected commit SHA for {self._label()}: {sha[:80]!r}"
            )
        return sha

    def _download(self, client: httpx.Client, sha: str, target: Path) -> None:
        with (
            client.stream("GET", f"/repos/{self.repository}/tarball/{sha}")
            as response,
            tempfile.TemporaryFile() as buffer,
        ):
            response.raise_for_status()
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > self.max_archive_bytes:
                    raise TemplateSourceError(
                        f"Archive of {self._label()} exceeds "
                        f"{self.max_archive_bytes} bytes"
                    )
                buffer.write(chunk)
            buffer.seek(0)
            self._extract(buffer, target)

    def _extract(self, fileobj: IO[bytes], target: Path) -> None:
        tmp = target.with_name(f"{target.name}.tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        prefix = PurePosixPath(self.path) if self.path else None

        try:
            with tarfile.open(fileobj=fileobj, mode="r:gz") as archive:
                for member in archive:
                    # GitHub-Tarballs haben den Wurzelordner <owner>-<repo>-<sha>/
                    parts = PurePosixPath(member.name).parts
                    if len(parts) < 2:
                        continue
                    relative = PurePosixPath(*parts[1:])
                    if prefix is not None and not (
                        relative == prefix or prefix in relative.parents
                    ):
                        continue
                    if member.islnk():
                        logger.warning(
                            "Skipping hard link '%s' in %s",
                            relative,
                            self._label(),
                        )
                        continue
                    archive.extract(
                        member.replace(name=str(relative), deep=False),
                        tmp,
                        filter="data",
                    )
            tmp.rename(target)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise

    def _latest_snapshot(self) -> Path | None:
        if not self.cache_root.is_dir():
            return None
        snapshots = [
            item
            for item in self.cache_root.iterdir()
            if item.is_dir() and _SHA_PATTERN.match(item.name)
        ]
        return max(snapshots, key=lambda item: item.stat().st_mtime, default=None)

    def _prune(self, keep: str) -> None:
        for item in self.cache_root.iterdir():
            if item.name != keep:
                shutil.rmtree(item, ignore_errors=True)

    def _label(self) -> str:
        label = f"github:{self.repository}@{self.ref}"
        return f"{label}#{self.path}" if self.path else label
