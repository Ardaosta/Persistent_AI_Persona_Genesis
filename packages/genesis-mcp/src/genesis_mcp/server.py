"""Genesis over MCP: a stdio JSON-RPC server exposing an agent's own vault.

WHY THIS EXISTS
---------------
A Genesis Mode B companion is assembled out of three things that only one surface
has: a CLAUDE.md at GENESIS_ROOT, a SessionStart hook, and the `genesis` CLI reached
through a shell. On every other surface the person gets a stranger wearing their
companion's name. Copying the persona text across fixes the voice and not the
memory, which is worse than a stranger: a companion who sounds right and quietly
invents a shared history leaves the person no way to tell which of their own
memories are real.

So memory stops being reached through a filesystem path and starts being reached
through a protocol. Same vault, same facts, one companion, several surfaces.

WHAT THIS IS NOT
----------------
It is not a second memory system. Every operation routes into
`genesis_core.agent.dispatch`, the same function the agent loop itself calls, using
the same ToolSpec schemas. If this module ever grows its own storage, its own
index, or its own opinion about what a fact is, the design has gone wrong: that is
a fork of the person's memory wearing a helpful hat, and a forked vault is the
specific failure this project has already paid for twice.

TRANSPORT
---------
Newline-delimited JSON-RPC 2.0 on stdin/stdout, which is the MCP stdio transport.
Deliberately stdlib-only, matching the rest of the repo: it has to run on a
non-technical person's machine against a bare Python install, and every dependency
is one more thing that can be missing on the day it matters. Nothing listens on a
socket. A remote server would mean the person's memory leaving their own computer
in order to reach them, which is the one thing the framework exists to prevent.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

SERVER_NAME = "genesis"
SERVER_VERSION = "0.0.1"

# Spoken only if the client does not state its own. We echo the client's version
# when it gives one, because an MCP client that is newer than this file is the
# expected case, not an error, and refusing to speak a version we would have
# understood anyway is a pointless way to fail.
FALLBACK_PROTOCOL_VERSION = "2025-06-18"

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

# Step 1 ships `recall` alone, on purpose. One tool proven end to end in a real
# client is worth more than five tools proven in a unit test, and if `recall` does
# not work in the host application then nothing else in the plan matters.
EXPOSED_TOOLS = ("recall",)


class GenesisRootError(RuntimeError):
    """Raised when GENESIS_ROOT is absent or does not look like a Genesis home."""


def resolve_root() -> Path:
    """Resolve GENESIS_ROOT strictly, refusing to guess.

    This function is deliberately unhelpful. Genesis's CLI falls back to a default
    home when GENESIS_ROOT is unset, which is correct for a first run and disastrous
    here: a memory server that silently addresses an empty default vault does not
    look broken, it looks like a companion with amnesia, and it will happily write
    new facts into the wrong tree. That exact fallback forked one companion's memory
    twice (2026-07-04, and again across 2026-07-20 to 07-27, ten real facts). A
    server that refuses to start is a bug report. A server that starts on the wrong
    vault is a slow corruption nobody notices for a week.
    """
    raw = os.environ.get("GENESIS_ROOT", "").strip()
    if not raw:
        raise GenesisRootError(
            "GENESIS_ROOT is not set. Refusing to start rather than fall back to a "
            "default home, because addressing the wrong vault is indistinguishable "
            "from amnesia and silently forks memory. Set it in the MCP server's env "
            "block to the companion's home directory."
        )
    root = Path(raw).expanduser()
    if not root.is_dir():
        raise GenesisRootError(f"GENESIS_ROOT points at {root}, which is not a directory.")
    if not (root / "vault").is_dir():
        raise GenesisRootError(
            f"GENESIS_ROOT points at {root}, which has no vault/ subdirectory. "
            "That is probably the wrong directory rather than an empty companion."
        )
    return root


class GenesisBridge:
    """Lazy handle on the companion's config, vault and tool schemas.

    Imports are deferred to first use so that a misconfigured GENESIS_ROOT reports
    itself as a clean startup error instead of an ImportError traceback, and so the
    JSON-RPC loop is testable without genesis-core installed.
    """

    def __init__(self, root: Path):
        self.root = root
        self._vault = None
        self._cfg = None
        self._specs = None

    def _load(self):
        if self._vault is not None:
            return
        from genesis_core import config as cfgmod  # noqa: PLC0415
        from genesis_core.agent import _MEMORY_TOOLS  # noqa: PLC0415
        from genesis_memory import Vault  # noqa: PLC0415

        self._cfg = cfgmod.load(self.root)
        self._vault = Vault(self._cfg.vault_dir)
        self._specs = {t.name: t for t in _MEMORY_TOOLS}

    def tool_schemas(self) -> list[dict]:
        """Advertise the agent's OWN ToolSpecs, converted to MCP's shape.

        Lifted from genesis-core rather than restated here so the two can never
        drift. If the agent's idea of `recall` changes, this changes with it, and a
        companion that answers differently depending on which surface you asked is
        the whole problem this server exists to solve.
        """
        self._load()
        out = []
        for name in EXPOSED_TOOLS:
            spec = self._specs.get(name)
            if spec is None:
                continue
            out.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": spec.input_schema,
                }
            )
        return out

    def call(self, name: str, args: dict) -> str:
        self._load()
        if name not in EXPOSED_TOOLS:
            return f"error: tool '{name}' is not exposed by this server"
        from genesis_core.agent import dispatch  # noqa: PLC0415

        return dispatch({"tool": name, "args": args or {}}, self._vault, self._cfg)


def _result(req_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(msg: dict, bridge: GenesisBridge) -> dict | None:
    """Handle one JSON-RPC message. Returns a response, or None for notifications."""
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications carry no id and must never be answered. Replying to one is a
    # protocol violation that some clients tolerate and others hang on.
    is_notification = "id" not in msg

    if method == "initialize":
        return _result(
            req_id,
            {
                "protocolVersion": params.get("protocolVersion") or FALLBACK_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        try:
            return _result(req_id, {"tools": bridge.tool_schemas()})
        except Exception as e:  # noqa: BLE001
            return _error(req_id, INTERNAL_ERROR, f"could not read tool schemas: {e}")

    if method == "tools/call":
        name = params.get("name") or ""
        args = params.get("arguments") or {}
        try:
            text = bridge.call(name, args)
        except Exception as e:  # noqa: BLE001
            # Surfaced as a tool-level error rather than a transport error, so the
            # model sees it and can say what went wrong instead of the whole server
            # looking dead.
            return _result(
                req_id,
                {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True},
            )
        return _result(req_id, {"content": [{"type": "text", "text": text}]})

    if is_notification:
        return None
    return _error(req_id, METHOD_NOT_FOUND, f"unknown method '{method}'")


def serve(stdin=None, stdout=None, bridge: GenesisBridge | None = None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if bridge is None:
        bridge = GenesisBridge(resolve_root())

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _write(stdout, _error(None, PARSE_ERROR, "invalid JSON"))
            continue
        if not isinstance(msg, dict):
            _write(stdout, _error(None, INVALID_REQUEST, "expected a JSON object"))
            continue
        try:
            resp = handle(msg, bridge)
        except Exception:  # noqa: BLE001
            # Never let one bad message kill the server: the client would see the
            # companion vanish mid-conversation with no explanation.
            traceback.print_exc(file=sys.stderr)
            resp = _error(msg.get("id"), INTERNAL_ERROR, "internal error")
        if resp is not None:
            _write(stdout, resp)
    return 0


def _write(stdout, payload: dict) -> None:
    stdout.write(json.dumps(payload) + "\n")
    stdout.flush()


def main() -> int:
    try:
        root = resolve_root()
    except GenesisRootError as e:
        sys.stderr.write(f"genesis-mcp: {e}\n")
        return 2
    return serve(bridge=GenesisBridge(root))
