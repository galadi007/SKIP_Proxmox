from pathlib import Path

import yaml
from skip_capability_sdk import Claim

from capability_operator.conditions import ready_condition

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "llm-access-claim.yaml"


def test_claim_from_example_body():
    body = yaml.safe_load(EXAMPLE.read_text())
    body["metadata"]["uid"] = "0000-uid"

    claim = Claim.from_body(body)

    assert claim.type == "llm-access"
    assert claim.namespace == "cap-test"


def test_ready_condition_has_required_fields():
    condition = ready_condition(status="True", reason="Provisioned", message="ok")

    assert condition["type"] == "Ready"
    assert condition["status"] == "True"
    assert condition["reason"] == "Provisioned"
    assert condition["lastTransitionTime"].endswith("Z")
