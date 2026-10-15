import pytest
import requests

from skip_capability_litellm import LiteLLMCapability, LiteLLMError
from skip_capability_sdk import Claim, InvalidClaimError, TransientError


def make_claim(properties) -> Claim:
    return Claim(
        name="my-llm",
        namespace="cap-test",
        uid="0000-uid",
        api_version="platform.skip.io/v1alpha1",
        kind="CapabilityClaim",
        spec={"type": "llm-access", "properties": properties},
    )


def test_desired_key_from_claim():
    desired = LiteLLMCapability._desired_key(make_claim({"models": ["mistral-small"]}))

    assert desired.alias == "skip-cap-test-my-llm"
    assert desired.models == ("mistral-small",)
    assert desired.secret_name == "my-llm-credentials"


@pytest.mark.parametrize("models", [None, [], "mistral-small", ["ok", 1]])
def test_desired_key_rejects_invalid_models(models):
    with pytest.raises(InvalidClaimError):
        LiteLLMCapability._desired_key(make_claim({"models": models}))


class FakeLiteLLM:
    base_url = "http://litellm.test:4000"

    def __init__(self, error: Exception | None = None):
        self.error = error

    def check_connection(self):
        if self.error:
            raise self.error


def test_initialize_checks_connection():
    LiteLLMCapability(litellm=FakeLiteLLM()).initialize()  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "error",
    [LiteLLMError("HTTP 401"), requests.ConnectionError("refused")],
)
def test_initialize_reports_unreachable_litellm(error):
    capability = LiteLLMCapability(litellm=FakeLiteLLM(error))  # type: ignore[arg-type]

    with pytest.raises(TransientError, match="Cannot connect to LiteLLM"):
        capability.initialize()


def test_initialize_without_master_key(monkeypatch):
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)

    with pytest.raises(TransientError, match="LITELLM_MASTER_KEY"):
        LiteLLMCapability().initialize()
