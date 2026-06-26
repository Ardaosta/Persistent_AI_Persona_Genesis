"""The stdio MCP bridge: JSON-RPC plumbing plus a real tool call that lands a
fact in a vault, proving the CLI-delegated dream can write through it."""

from __future__ import annotations

import io
import json

from genesis_core import config as cfgmod
from genesis_core import mcp_server as srv
from genesis_memory import Vault


def _ctx(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"provider": "claude-cli"}))
    cfg = cfgmod.load(tmp_path)
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    return {"cfg": cfg, "vault": Vault(cfg.vault_dir)}


def test_initialize_echoes_protocol_and_names():
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18"}}, ctx={})
    assert r["result"]["protocolVersion"] == "2025-06-18"
    assert r["result"]["serverInfo"]["name"] == "genesis"
    assert "tools" in r["result"]["capabilities"]


def test_initialized_notification_has_no_reply():
    assert srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, ctx={}) is None


def test_tools_list_matches_memory_tools():
    r = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, ctx={})
    names = {t["name"] for t in r["result"]["tools"]}
    assert {"remember", "recall", "capture"} <= names
    for t in r["result"]["tools"]:
        assert "inputSchema" in t and t["description"]


def test_tools_call_remember_writes_to_vault(tmp_path):
    ctx = _ctx(tmp_path)
    r = srv.handle({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "remember", "arguments": {
            "id": "dog-vin", "kind": "user", "description": "an Irish Wolfhound named Vin"}},
    }, ctx)
    assert r["result"]["content"][0]["text"].startswith("saved user/dog-vin")
    assert ctx["vault"].get("dog-vin") is not None


def test_tools_call_recall_reads_back(tmp_path):
    ctx = _ctx(tmp_path)
    srv.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "remember", "arguments": {
                    "id": "fav-book", "kind": "user", "description": "Stormlight Archive"}}}, ctx)
    r = srv.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                    "params": {"name": "recall", "arguments": {"query": "stormlight"}}}, ctx)
    assert "fav-book" in r["result"]["content"][0]["text"]


def test_unknown_method_errors():
    r = srv.handle({"jsonrpc": "2.0", "id": 9, "method": "nope"}, ctx={})
    assert r["error"]["code"] == -32601


def test_serve_loop_over_stdio(tmp_path):
    ctx = _ctx(tmp_path)
    lines = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    ])
    out = io.StringIO()
    srv.serve(stdin=io.StringIO(lines), stdout=out, ctx=ctx)
    replies = [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]
    # two replies (initialize + tools/list); the notification produced none
    assert [r["id"] for r in replies] == [1, 2]
