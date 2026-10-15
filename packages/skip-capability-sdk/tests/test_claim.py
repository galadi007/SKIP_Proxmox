from skip_capability_sdk import Binding, Claim, SecretRef

BODY = {
    "apiVersion": "platform.skip.io/v1alpha1",
    "kind": "CapabilityClaim",
    "metadata": {"name": "my-llm", "namespace": "cap-test", "uid": "0000-uid"},
    "spec": {"type": "llm-access", "properties": {"models": ["mistral-small"]}},
}


def test_claim_from_body():
    claim = Claim.from_body(BODY)

    assert claim.type == "llm-access"
    assert claim.name == "my-llm"
    assert claim.namespace == "cap-test"
    assert claim.properties["models"] == ["mistral-small"]
    assert claim.kind == "CapabilityClaim"


def test_claim_without_spec():
    claim = Claim.from_body({**BODY, "spec": None})

    assert claim.type == ""
    assert claim.properties == {}


def test_binding_to_status():
    binding = Binding(endpoint="http://x", secret_ref=SecretRef(name="s", key="k"))

    assert binding.to_status() == {
        "endpoint": "http://x",
        "secretRef": {"name": "s", "key": "k"},
    }
