"""Router schemas + JSON parsing tests."""
import pytest

from openmolclaw.harness.router import Router, parse_router_json_content
from openmolclaw.harness.schemas import GoalPolicy, RouterDecision


def test_parse_plain_and_duplicated_json():
    assert parse_router_json_content('{"a": 1}') == {"a": 1}
    # duplicated object on two lines -> first only
    assert parse_router_json_content('{"a": 1}\n{"a": 1}') == {"a": 1}


def test_parse_fenced_json():
    assert parse_router_json_content('```json\n{"a": 2}\n```') == {"a": 2}


def test_router_decision_defaults():
    d = RouterDecision(intent="action", tool_name="render_molecule")
    assert d.tool_args == {}
    assert d.conversational is False


def test_goal_policy_has_no_billing_fields():
    gp = GoalPolicy()
    # commercial billing fields must not be present in the public schema
    assert not hasattr(gp, "estimated_ai_actions")
    assert "estimated_steps" in GoalPolicy.model_fields


def test_decision_from_payload_conversational_when_no_tool():
    d = Router.decision_from_payload({"tool_name": "", "intent": "question"})
    assert d.conversational is True
    d2 = Router.decision_from_payload({"tool_name": "validate_smiles"})
    assert d2.conversational is False and d2.tool_name == "validate_smiles"
