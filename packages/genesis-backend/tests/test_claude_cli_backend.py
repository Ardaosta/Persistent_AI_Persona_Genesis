"""ClaudeCLIBackend: shells `claude -p` for sub-billed completion and delegated
agentic turns. We never invoke the real CLI here; subprocess.run is stubbed so
the tests are deterministic and assert the command we build."""

from __future__ import annotations

import json
from types import SimpleNamespace

import genesis_backend.claude_cli_backend as cli
from genesis_backend import ClaudeCLIBackend
from genesis_backend.seam import Message, ToolSpec


def _stub_run(monkeypatch, result_obj, capture):
    monkeypatch.setattr(cli, "_claude_bin", lambda: "claude")

    def fake_run(args, **kwargs):
        capture["args"] = args
        capture["input"] = kwargs.get("input")
        capture["env"] = kwargs.get("env")
        return SimpleNamespace(returncode=0, stdout=json.dumps(result_obj), stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)


def test_caps_no_key_needed():
    be = ClaudeCLIBackend()  # constructs with no key at all
    caps = be.caps()
    assert caps.provider == "claude-cli"
    assert caps.supports_tools is True


def test_complete_is_toolless(monkeypatch):
    cap = {}
    _stub_run(monkeypatch, {"result": "ok", "subtype": "success",
                            "usage": {"input_tokens": 3, "output_tokens": 1}}, cap)
    be = ClaudeCLIBackend(model="claude-sonnet-4-6")
    c = be.complete([Message("user", "hi")], system="be brief")
    assert c.text == "ok"
    assert c.input_tokens == 3 and c.output_tokens == 1
    a = cap["args"]
    assert "--print" in a and "--output-format" in a
    # pure completion: tools explicitly disabled
    assert a[a.index("--allowedTools") + 1] == ""
    assert "--append-system-prompt" in a
    assert "--mcp-config" not in a


def test_run_turn_delegates_with_mcp_tools(monkeypatch, tmp_path):
    cap = {}
    _stub_run(monkeypatch, {"result": "reflected", "subtype": "success", "usage": {}}, cap)
    be = ClaudeCLIBackend(root=tmp_path)
    tools = [ToolSpec("remember", "save", {"type": "object"}),
             ToolSpec("recall", "look up", {"type": "object"})]
    r = be.run_turn([{"role": "user", "text": "(dream cycle)"}], system="you are dreaming", tools=tools)
    assert r.text == "reflected"
    assert r.tool_calls == []  # CLI ran the loop; nothing pends back
    a = cap["args"]
    assert "--strict-mcp-config" in a and "--mcp-config" in a
    assert "mcp__genesis__remember" in a and "mcp__genesis__recall" in a
    # never silently re-grant built-ins
    assert "--permission-mode" not in a or "bypassPermissions" not in a
    assert cap["input"] == "(dream cycle)"


def test_run_turn_without_tools_is_toolless(monkeypatch):
    cap = {}
    _stub_run(monkeypatch, {"result": "x", "subtype": "success", "usage": {}}, cap)
    be = ClaudeCLIBackend()  # no root, no tools
    be.run_turn([{"role": "user", "text": "hello"}])
    a = cap["args"]
    assert a[a.index("--allowedTools") + 1] == ""
    assert "--mcp-config" not in a


def test_child_env_strips_api_key_keeps_oauth(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat-keepme")
    env = cli._child_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat-keepme"


def test_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr(cli, "_claude_bin", lambda: "claude")
    monkeypatch.setattr(cli.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"))
    be = ClaudeCLIBackend()
    try:
        be.complete([Message("user", "hi")])
    except cli.BackendError as e:
        assert "boom" in str(e)
    else:
        raise AssertionError("expected BackendError on nonzero exit")
