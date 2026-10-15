from importlib.metadata import EntryPoint

import pytest
from skip_capability_sdk import ENTRY_POINT_GROUP, TransientError

from capability_operator.plugins import (
    enabled_plugins,
    initialize_capability,
    load_capabilities,
)


class DummyCapability:
    def initialize(self):
        pass

    def provision(self, claim):
        raise NotImplementedError

    def cleanup(self, claim):
        raise NotImplementedError


class OtherCapability(DummyCapability):
    pass


def ep(name: str, value: str) -> EntryPoint:
    return EntryPoint(name=name, value=value, group=ENTRY_POINT_GROUP)


DUMMY = f"{__name__}:DummyCapability"
OTHER = f"{__name__}:OtherCapability"


def test_loads_entry_points_by_name():
    registry = load_capabilities([ep("a", DUMMY), ep("b", OTHER)])

    assert isinstance(registry["a"], DummyCapability)
    assert isinstance(registry["b"], OtherCapability)


def test_skips_broken_plugin():
    registry = load_capabilities([ep("broken", "does_not_exist:Nope"), ep("a", DUMMY)])

    assert list(registry) == ["a"]


def test_duplicate_keeps_first():
    registry = load_capabilities([ep("a", DUMMY), ep("a", OTHER)])

    assert type(registry["a"]) is DummyCapability


def test_enabled_filter():
    registry = load_capabilities([ep("a", DUMMY), ep("b", OTHER)], enabled={"b"})

    assert list(registry) == ["b"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), ("", None), (" llm-access , foo,", {"llm-access", "foo"})],
)
def test_enabled_plugins_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("CAPABILITY_PLUGINS", raising=False)
    else:
        monkeypatch.setenv("CAPABILITY_PLUGINS", raw)

    assert enabled_plugins() == expected


def test_installed_litellm_plugin_is_discovered():
    pytest.importorskip("skip_capability_litellm")

    registry = load_capabilities()

    assert type(registry["llm-access"]).__name__ == "LiteLLMCapability"


class FailingCapability(DummyCapability):
    def __init__(self, error: Exception):
        self.error = error

    def initialize(self):
        raise self.error


def test_initialize_capability_succeeds():
    initialize_capability("a", DummyCapability())


@pytest.mark.parametrize("error", [TransientError("down"), RuntimeError("boom")])
def test_initialize_capability_wraps_errors(error):
    with pytest.raises(TransientError, match="'a'"):
        initialize_capability("a", FailingCapability(error))
