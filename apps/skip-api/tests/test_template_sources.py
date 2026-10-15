import io
import tarfile
from pathlib import Path

import httpx
import pytest

from templates.errors import TemplateSourceError
from templates.service import FileSystemTemplateService
from templates.sources import (
    GitHubSourceSpec,
    GitHubTemplateLoader,
    LocalSourceSpec,
    LocalTemplateLoader,
    TemplateSnapshot,
    load_template_loaders_from_env,
    parse_source_shorthand,
)


SHA_1 = "1" * 40
SHA_2 = "2" * 40

TEMPLATE_YAML = """\
apiVersion: platform.skip.io/v1alpha1
kind: AppTemplate
metadata:
  name: {name}
spec:
  displayName: {name}
  version: "1"
  components:
    - name: app
      image: nginx
"""


def _tarball(files: dict[str, str], sha: str = SHA_1, links=()) -> bytes:
    """GitHub-artiger Tarball mit Wurzelordner <owner>-<repo>-<sha>/."""
    buffer = io.BytesIO()
    top = f"org-repo-{sha[:7]}"
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        directory = tarfile.TarInfo(top)
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        for name, target in links:
            info = tarfile.TarInfo(f"{top}/{name}")
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)
    return buffer.getvalue()


class FakeGitHub:
    def __init__(self, sha: str, tarball: bytes) -> None:
        self.sha = sha
        self.tarball = tarball
        self.fail = False
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            raise httpx.ConnectError("offline", request=request)
        path = request.url.path
        if path.startswith("/repos/org/repo/commits/"):
            return httpx.Response(200, text=self.sha)
        if path == f"/repos/org/repo/tarball/{self.sha}":
            return httpx.Response(200, content=self.tarball)
        return httpx.Response(404)

    def downloads(self) -> int:
        return sum("/tarball/" in r.url.path for r in self.requests)


def _loader(fake: FakeGitHub, cache: Path, **kwargs) -> GitHubTemplateLoader:
    return GitHubTemplateLoader(
        "org",
        "org/repo",
        cache_dir=cache,
        transport=httpx.MockTransport(fake),
        **kwargs,
    )


REPO_FILES = {
    "README.md": "# repo",
    "templates/alpha/template.yaml": TEMPLATE_YAML.format(name="alpha"),
    "templates/beta/template.yaml": TEMPLATE_YAML.format(name="beta"),
    "apps/gamma/deploy/template.yaml": TEMPLATE_YAML.format(name="gamma"),
}


def test_github_loader_extracts_only_subfolder(tmp_path: Path) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES))
    loader = _loader(fake, tmp_path, ref="v1.0", path="templates")

    snapshot = loader.fetch()

    assert snapshot.revision == SHA_1
    assert snapshot.root == tmp_path / "org" / SHA_1 / "templates"
    assert (snapshot.root / "alpha" / "template.yaml").is_file()
    assert not (tmp_path / "org" / SHA_1 / "README.md").exists()
    assert fake.requests[0].url.path == "/repos/org/repo/commits/v1.0"


def test_github_loader_sends_token(tmp_path: Path) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES))
    _loader(fake, tmp_path, token="secret").fetch()
    assert fake.requests[0].headers["Authorization"] == "Bearer secret"


def test_github_loader_reuses_cache_and_prunes_old_revisions(
    tmp_path: Path,
) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES))
    loader = _loader(fake, tmp_path, path="templates")

    loader.fetch()
    loader.fetch()
    assert fake.downloads() == 1

    fake.sha = SHA_2
    fake.tarball = _tarball(REPO_FILES, sha=SHA_2)
    assert loader.fetch().revision == SHA_2
    assert fake.downloads() == 2
    assert not (tmp_path / "org" / SHA_1).exists()


def test_github_loader_falls_back_to_cached_snapshot(tmp_path: Path) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES))
    loader = _loader(fake, tmp_path, path="templates")
    loader.fetch()

    fake.fail = True
    snapshot = loader.fetch()
    assert snapshot.revision == SHA_1
    assert (snapshot.root / "beta" / "template.yaml").is_file()


def test_github_loader_without_cache_raises(tmp_path: Path) -> None:
    fake = FakeGitHub(SHA_1, b"")
    fake.fail = True
    with pytest.raises(TemplateSourceError):
        _loader(fake, tmp_path).fetch()


def test_github_loader_missing_path_raises(tmp_path: Path) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES))
    with pytest.raises(TemplateSourceError, match="not found"):
        _loader(fake, tmp_path, path="does/not/exist").fetch()


def test_github_loader_enforces_archive_size(tmp_path: Path) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES))
    with pytest.raises(TemplateSourceError, match="exceeds"):
        _loader(fake, tmp_path, max_archive_bytes=10).fetch()


@pytest.mark.parametrize(
    "links",
    [
        [("templates/evil", "/etc/passwd")],
        [("templates/evil", "../../../outside")],
    ],
)
def test_github_loader_rejects_escaping_links(
    tmp_path: Path, links: list[tuple[str, str]]
) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES, links=links))
    with pytest.raises(TemplateSourceError):
        _loader(fake, tmp_path / "cache", path="templates").fetch()
    assert not list((tmp_path / "cache" / "org").iterdir())


def test_service_discovers_single_template_and_collections(
    tmp_path: Path,
) -> None:
    fake = FakeGitHub(SHA_1, _tarball(REPO_FILES))
    service = FileSystemTemplateService(
        [
            _loader(fake, tmp_path / "a", path="templates"),
            _loader(fake, tmp_path / "b", path="apps/gamma/deploy"),
        ]
    )

    names = {item.name for item in service.list()}
    assert names == {"alpha", "beta", "gamma"}
    assert service.get("gamma").revision == SHA_1
    assert service.get("gamma").source == "org"


class _StaticLoader:
    def __init__(self, source: str, root: Path) -> None:
        self.source = source
        self.root = root

    def fetch(self) -> TemplateSnapshot:
        return TemplateSnapshot(root=self.root, revision=None)


def _write_template(root: Path, folder: str, name: str) -> None:
    (root / folder).mkdir(parents=True)
    (root / folder / "template.yaml").write_text(TEMPLATE_YAML.format(name=name))


def test_service_first_source_wins_and_errors_are_isolated(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_template(first, "a", "shared")
    _write_template(second, "a", "shared")
    _write_template(second, "b", "only-second")
    (second / "broken").mkdir()
    (second / "broken" / "template.yaml").write_text("kind: [")

    service = FileSystemTemplateService(
        [
            _StaticLoader("first", first),
            _StaticLoader("second", second),
            LocalTemplateLoader("missing", tmp_path / "missing"),
        ]
    )
    result = service.reload()

    assert {item.name for item in service.list()} == {"shared", "only-second"}
    assert service.get("shared").source == "first"
    assert result.templates == 2
    assert len(result.errors) == 3
    assert any("duplicate template name 'shared'" in e for e in result.errors)
    assert any("Source 'missing'" in e for e in result.errors)


def test_parse_source_shorthand() -> None:
    spec = parse_source_shorthand("github:fhswf/skip-templates@v1.3.0#templates/")
    assert isinstance(spec, GitHubSourceSpec)
    assert spec.name == "fhswf-skip-templates"
    assert spec.repository == "fhswf/skip-templates"
    assert spec.ref == "v1.3.0"
    assert spec.path == "templates"

    default = parse_source_shorthand("github:org/repo")
    assert isinstance(default, GitHubSourceSpec)
    assert (default.ref, default.path) == ("HEAD", "")

    local = parse_source_shorthand("/srv/templates")
    assert isinstance(local, LocalSourceSpec)
    assert local.path == "/srv/templates"

    with pytest.raises(ValueError):
        parse_source_shorthand("github:org/repo#../etc")


def test_loaders_from_sources_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - name: builtin
    type: local
    path: /templates
  - name: fhswf
    type: github
    repository: fhswf/skip-templates
    ref: v1.3.0
    path: templates
    tokenEnv: MY_TOKEN
"""
    )
    monkeypatch.setenv("TEMPLATE_SOURCES_FILE", str(config))
    monkeypatch.setenv("TEMPLATES_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MY_TOKEN", "abc")

    local, github = load_template_loaders_from_env(tmp_path)

    assert isinstance(local, LocalTemplateLoader)
    assert isinstance(github, GitHubTemplateLoader)
    assert (github.repository, github.ref, github.path) == (
        "fhswf/skip-templates",
        "v1.3.0",
        "templates",
    )
    assert github.token == "abc"
    assert github.cache_root == tmp_path / "cache" / "fhswf"


def test_loaders_fall_back_to_templates_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("TEMPLATE_SOURCES_FILE", "TEMPLATE_SOURCES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TEMPLATES_DIR", str(tmp_path))

    (loader,) = load_template_loaders_from_env(Path("/unused"))
    assert isinstance(loader, LocalTemplateLoader)
    assert loader.path == tmp_path.resolve()
