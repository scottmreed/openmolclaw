"""Executor + router-with-fake-provider tests (no network)."""
from openmolclaw.harness.executor import ToolExecutor
from openmolclaw.harness.interfaces import GateResult
from openmolclaw.harness.router import Router
from openmolclaw.harness.tool_registry import ToolRegistry


class DenyGate:
    def check(self, tool_name, context):
        return GateResult.deny("nope")


class FakeProvider:
    def __init__(self, content):
        self._content = content

    def complete_with_tools(self, messages, tools, tool_choice=None):
        return {"choices": [{"message": {"content": self._content}}]}


def _registry():
    reg = ToolRegistry()
    reg.register("add", lambda a, b: a + b, description="add")
    return reg


def test_execute_success():
    ex = ToolExecutor(_registry())
    r = ex.execute("add", {"a": 2, "b": 3})
    assert r.ok and r.result == 5
    assert ex.trace.entries[-1]["ok"] is True


def test_execute_unknown_tool():
    ex = ToolExecutor(_registry())
    r = ex.execute("missing")
    assert not r.ok and r.error_type == "unknown_tool"


def test_execute_gate_denied():
    ex = ToolExecutor(_registry(), tool_gate=DenyGate())
    r = ex.execute("add", {"a": 1, "b": 1})
    assert not r.ok and r.error_type == "gate_denied"


def test_execute_bad_args():
    ex = ToolExecutor(_registry())
    r = ex.execute("add", {"a": 1})  # missing b
    assert not r.ok and r.error_type == "bad_arguments"


def test_router_with_fake_provider_and_execute():
    reg = _registry()
    provider = FakeProvider('{"intent":"action","tool_name":"add","tool_args":{"a":4,"b":5},"confidence":0.9}')
    decision = Router(provider).route("add four and five", reg.specs())
    assert decision.tool_name == "add"
    result = ToolExecutor(reg).execute_decision(decision)
    assert result.ok and result.result == 9
