"""Mode B: wire Claude Code to run as a Genesis frontend.

Claude Code brings the muscle (real tool sandbox, subagents, file/shell editing);
Genesis supplies the persistent self (the vault, the boot ritual, continuity). This
module lays down the two pieces of config that turn a stock Claude Code into a
persistent companion, into the locations the *current* Claude Code reads (verified
against the docs 2026-06: SessionStart hook shape, settings.json scopes, CLAUDE.md
locations):

  CLAUDE.md          operating disciplines + boot ritual + the blessed write path.
                     Identity stays EMPTY (the empty-shipping invariant holds).
  settings.json      a SessionStart hook whose command prints the boot context to
                     stdout; Claude Code injects that before turn 1.

Scope:
  project (default)  writes into a companion home directory (<dir>/CLAUDE.md and
                     <dir>/.claude/settings.json). Non-invasive: the user's other
                     Claude Code projects are untouched. They launch `claude` there.
  user               writes ~/.claude/CLAUDE.md and merges ~/.claude/settings.json
                     (the companion everywhere, like the reference setup).

Everything here is idempotent: re-running updates in place and never duplicates the
hook or clobbers unrelated settings.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import manual

# Back-compat: the manual text used to live here as CLAUDE_MD. It is now rendered
# by manual.py for BOTH harnesses (Claude Code reads CLAUDE.md, Codex reads
# AGENTS.md) so the two doors can never drift apart.
CLAUDE_MD = manual.MANUAL

_HOOK_MARKERS = ("boot-context", "reanchor", "craft-gate")


def _posix(p) -> str:
    """Forward-slash a path. Claude Code runs hooks (and the agent's shell tool)
    through Git Bash on Windows, where backslashes are escape characters and a
    `C:\\Users\\...` path mangles to a not-found (exit 127). Forward slashes work
    in Git Bash, in cmd, and when invoking a .exe, so we always emit them."""
    return str(p).replace("\\", "/")


def render_claude_md(cfg, genesis_exe: str) -> str:
    return manual.render(cfg, genesis_exe, harness="claude-code")


def _hook_command(genesis_exe: str, root: Path, verb: str = "boot-context") -> str:
    """A hook command. Carries GENESIS_ROOT so the hook is independent of the
    user's environment at session time. Uses forward-slash paths so it works
    under Git Bash (Claude Code's default hook shell on Windows) and POSIX sh."""
    return f'GENESIS_ROOT="{_posix(root)}" "{_posix(genesis_exe)}" {verb} --hook'


def build_hook_entry(genesis_exe: str, root: Path) -> dict:
    return {
        "matcher": "startup|resume",
        "hooks": [{"type": "command", "command": _hook_command(genesis_exe, root)}],
    }


def _is_ours(entry: dict) -> bool:
    for h in entry.get("hooks", []):
        cmd = h.get("command") or ""
        if any(m in cmd for m in _HOOK_MARKERS):
            return True
    return False


def build_reanchor_entry(genesis_exe: str, root: Path) -> dict:
    """UserPromptSubmit: re-deliver the register every N prompts (reanchor.py)."""
    return {"hooks": [{"type": "command", "command": _hook_command(genesis_exe, root, "reanchor")}]}


def build_craft_gate_entry(genesis_exe: str, root: Path) -> dict:
    """Stop: the friction loop's boundary gate (friction.py). Exit 2 + stderr once
    per session if nothing was captured, so the ask cannot be skipped by habit."""
    return {"hooks": [{"type": "command", "command": _hook_command(genesis_exe, root, "craft-gate")}]}


def merge_session_hook(settings: dict, genesis_exe: str, root: Path) -> dict:
    """Merge our hooks into an existing settings dict, idempotently: SessionStart
    (boot ritual), UserPromptSubmit (register re-anchor), Stop (craft gate).
    Preserves every other key and any non-Genesis hooks on those events."""
    settings = dict(settings) if settings else {}
    hooks = dict(settings.get("hooks") or {})
    for event, entry in (
        ("SessionStart", build_hook_entry(genesis_exe, root)),
        ("UserPromptSubmit", build_reanchor_entry(genesis_exe, root)),
        ("Stop", build_craft_gate_entry(genesis_exe, root)),
    ):
        existing = [e for e in (hooks.get(event) or []) if not _is_ours(e)]
        existing.append(entry)
        hooks[event] = existing
    settings["hooks"] = hooks
    return settings


def _read_json(path: Path) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def wire(cfg, genesis_exe: str, *, scope: str = "project", home_dir: Path | None = None) -> dict:
    """Write CLAUDE.md + the SessionStart hook for the chosen scope. Returns a dict
    describing what was written (paths) for the caller to report."""
    if scope == "user":
        base = Path.home() / ".claude"
        claude_md = base / "CLAUDE.md"
        settings_path = base / "settings.json"
        launch_dir = None
    else:  # project scope: a self-contained companion home
        home = Path(home_dir) if home_dir else cfg.root
        claude_md = home / "CLAUDE.md"
        settings_path = home / ".claude" / "settings.json"
        launch_dir = home

    claude_md.parent.mkdir(parents=True, exist_ok=True)
    claude_md.write_text(render_claude_md(cfg, genesis_exe), encoding="utf-8")

    settings = _read_json(settings_path)
    settings = merge_session_hook(settings, genesis_exe, cfg.root)
    # The Genesis vault is the single source of truth; turn off Claude Code's own
    # auto-memory so two memory systems don't diverge in this companion's home.
    settings["autoMemoryEnabled"] = False
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    mcp_path = None
    if launch_dir is not None:
        mcp_path = write_capability_mcp(cfg, launch_dir)

    return {
        "scope": scope,
        "claude_md": claude_md,
        "settings": settings_path,
        "launch_dir": launch_dir,
        "hook_command": _hook_command(genesis_exe, cfg.root),
        "mcp": mcp_path,
    }


# Remote MCP servers a capability can pre-wire into the companion home's
# project-scoped `.mcp.json` (verified 2026-09-21 against code.claude.com/docs/en/mcp:
# project scope + native `type: http`, no Node needed; Claude Code asks the person
# to approve project servers on first use, which is the consent step we want).
# Only hosted servers with a browser sign-in belong here: no keys, no headers, so
# nothing secret is ever written to disk by this function.
CAPABILITY_MCP = {
    "website": {
        "wix": {"type": "http", "url": "https://mcp.wix.com/mcp"},
    },
}


def write_capability_mcp(cfg, home: Path) -> "Path | None":
    """Merge the MCP servers implied by the configured capabilities into
    `<home>/.mcp.json`, idempotently, preserving any other servers the person or
    the AI added. Returns the path when something was written, else None."""
    wanted: dict = {}
    for slug in (getattr(cfg, "capabilities", None) or []):
        wanted.update(CAPABILITY_MCP.get(slug, {}))
    if not wanted:
        return None
    path = Path(home) / ".mcp.json"
    data = _read_json(path)
    servers = dict(data.get("mcpServers") or {})
    servers.update(wanted)
    data["mcpServers"] = servers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path
