"""A tiny stdio MCP server exposing Genesis's vault tools to a `claude` CLI agent.

This is the bridge that lets the agentic loop (the inward dream, and chat) run on
a Claude *subscription* via `claude -p` instead of the pay-as-you-go API: the CLI
runs its own loop and calls these tools over MCP, and every call routes to the
same `dispatch()` the API path uses, writing to the same vault. Zero third-party
deps: MCP is plain JSON-RPC 2.0 over newline-delimited stdio, hand-rolled here.

Run as:  python -m genesis_core.mcp_server   (reads GENESIS_ROOT from the env)
"""

from __future__ import annotations

import json
import sys

PROTOCOL_VERSION = "2025-06-18"


def tools_payload() -> list[dict]:
    """MCP tool descriptors derived from the agent's memory tools, so the two
    never drift: one source of truth for name/description/schema."""
    from genesis_core.agent import _MEMORY_TOOLS

    return [
        {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
        for t in _MEMORY_TOOLS
    ]


def _ok(rid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(req: dict, ctx: dict) -> dict | None:
    """Map one JSON-RPC request to a response dict, or None for a notification."""
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        client_ver = (req.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        return _ok(rid, {
            "protocolVersion": client_ver,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "genesis", "version": "0.1.0"},
        })
    if method in ("notifications/initialized", "initialized"):
        return None  # notification: no reply
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": tools_payload()})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            from genesis_core.agent import dispatch

            text = dispatch({"tool": name, "args": arguments}, ctx["vault"], ctx["cfg"])
        except Exception as e:  # never let a tool error kill the server
            return _ok(rid, {
                "content": [{"type": "text", "text": f"error: {e}"}],
                "isError": True,
            })
        return _ok(rid, {"content": [{"type": "text", "text": str(text)}]})

    if rid is not None:
        return _err(rid, -32601, f"method not found: {method}")
    return None


def build_context() -> dict:
    from genesis_core import config as cfgmod
    from genesis_memory import Vault

    cfg = cfgmod.load()
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    return {"cfg": cfg, "vault": Vault(cfg.vault_dir)}


def serve(stdin=None, stdout=None, ctx: dict | None = None) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    if ctx is None:
        ctx = build_context()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        resp = handle(req, ctx)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
