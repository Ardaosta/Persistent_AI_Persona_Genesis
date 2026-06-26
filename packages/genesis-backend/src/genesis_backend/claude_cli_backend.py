"""Claude CLI adapter: run on a Claude *subscription* via the `claude` CLI, no API key.

Two modes, both shelling the installed `claude` binary in `--print` mode:

- `complete()` is a pure one-shot completion (`--allowedTools ""`), used by the
  outward `learn` cycle and the health check.
- `run_turn()` delegates the WHOLE agentic loop to the CLI and exposes the
  caller's tools as an MCP server (genesis_core.mcp_server), so the model can call
  them mid-loop. The CLI runs its own loop, executes the tools (which write to the
  vault through the same `dispatch()` the API path uses), and returns final text.
  We hand back that text with NO pending tool_calls, so the caller's loop ends in
  a single delegated step. This is the bridge that puts the inward dream on the sub.

Auth: ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN are stripped from the child so the
CLI authenticates with the subscription, either keychain OAuth (interactive boxes)
or a durable CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token` (scheduled/headless
boxes). That token is deliberately kept. No key is needed to construct this backend.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .seam import (
    BackendCaps,
    BackendError,
    Completion,
    Message,
    ToolSpec,
    TurnResult,
)

# Empty default => let the CLI/subscription choose its own default model.
DEFAULT_MODEL = ""
_DEFAULT_TIMEOUT = 300


def _claude_bin() -> str:
    for name in ("claude", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    for cand in (
        os.path.expanduser("~/.local/bin/claude"),
        os.path.expanduser("~/.local/bin/claude.exe"),
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
    ):
        if os.path.isfile(cand):
            return cand
    raise BackendError("claude CLI not found (install it, or use an API-key engine)")


def _child_env() -> dict:
    # Strip API auth so the CLI bills the SUBSCRIPTION, never the pay-as-you-go key.
    # Keep CLAUDE_CODE_OAUTH_TOKEN: it's the durable subscription auth for headless runs.
    return {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }


def _messages_to_prompt(messages: list[Message]) -> str:
    return "\n\n".join(m.content for m in messages if m.content)


def _history_to_prompt(history: list[dict]) -> str:
    """Flatten neutral history into one prompt. In delegated mode the caller's
    loop ends in one step, so this is normally just the single user turn; prior
    assistant/tool rows are rendered for completeness if a caller passes them."""
    parts: list[str] = []
    for h in history:
        role = h.get("role")
        if role == "user" and h.get("text"):
            parts.append(h["text"])
        elif role == "assistant" and h.get("text"):
            parts.append(h["text"])
        elif role == "tool":
            for r in h.get("results", []):
                parts.append(f"(tool result: {r.get('content', '')})")
    return "\n\n".join(p for p in parts if p)


def _parse_print_json(stdout: str) -> tuple[str, dict]:
    data = json.loads(stdout or "{}")
    if data.get("is_error") or (data.get("subtype") and data.get("subtype") != "success"):
        raise BackendError(f"claude -p error: {str(data)[:400]}")
    text = (data.get("result") or "").strip()
    return text, (data.get("usage") or {})


class ClaudeCLIBackend:
    def __init__(self, *, root: Path | str | None = None, model: str = DEFAULT_MODEL,
                 timeout: int = _DEFAULT_TIMEOUT):
        self._root = Path(root).expanduser() if root else None
        self._model = model or ""
        self._timeout = timeout

    def caps(self) -> BackendCaps:
        return BackendCaps(
            provider="claude-cli",
            default_model=self._model or "(subscription default)",
            supports_tools=True,
            supports_streaming=False,
        )

    def _run(self, args: list[str], prompt: str) -> tuple[str, dict]:
        try:
            proc = subprocess.run(
                args, input=prompt, capture_output=True, text=True,
                env=_child_env(), timeout=self._timeout,
            )
        except FileNotFoundError as e:
            raise BackendError(f"claude CLI not runnable: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise BackendError(f"claude -p timed out after {self._timeout}s") from e
        if proc.returncode != 0:
            raise BackendError(
                f"claude -p exited {proc.returncode}: {(proc.stderr or proc.stdout)[:500]}"
            )
        return _parse_print_json(proc.stdout)

    def complete(
        self,
        messages: list[Message],
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> Completion:
        args = [_claude_bin(), "--print", "--output-format", "json", "--allowedTools", ""]
        mname = model or self._model
        if mname:
            args += ["--model", mname]
        if system:
            args += ["--append-system-prompt", system]
        text, usage = self._run(args, _messages_to_prompt(messages))
        return Completion(
            text=text,
            model=mname or "(subscription default)",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

    def run_turn(
        self,
        history: list[dict],
        *,
        system: str = "",
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> TurnResult:
        tools = tools or []
        args = [_claude_bin(), "--print", "--output-format", "json"]
        mname = model or self._model
        if mname:
            args += ["--model", mname]
        if system:
            args += ["--append-system-prompt", system]

        mcp_file: str | None = None
        try:
            if tools and self._root is not None:
                mcp_cfg = {
                    "mcpServers": {
                        "genesis": {
                            "command": sys.executable,
                            "args": ["-m", "genesis_core.mcp_server"],
                            "env": {
                                "GENESIS_ROOT": str(self._root),
                                "PYTHONPATH": os.pathsep.join(sys.path),
                            },
                        }
                    }
                }
                fd, mcp_file = tempfile.mkstemp(suffix=".json", prefix="genesis-mcp-")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(mcp_cfg, fh)
                tool_names = [f"mcp__genesis__{t.name}" for t in tools]
                # Allowlist ONLY the genesis tools (no Bash/Write/etc.), no prompts for
                # those, and load no MCP server but ours. Deliberately NOT
                # --permission-mode bypassPermissions: that would re-grant every
                # built-in tool. An out-of-allowlist call is denied, not run.
                args += ["--strict-mcp-config", "--mcp-config", mcp_file,
                         "--allowedTools", *tool_names]
            else:
                args += ["--allowedTools", ""]
            text, usage = self._run(args, _history_to_prompt(history))
        finally:
            if mcp_file and os.path.exists(mcp_file):
                os.unlink(mcp_file)

        # The CLI already executed the tools via MCP; nothing pends back to the caller.
        return TurnResult(
            text=text,
            tool_calls=[],
            stop_reason="end_turn",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
