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

# The content-free operating manual. Mirrors engine-packs/claude-code/CLAUDE.md.template;
# embedded here so it ships inside the installed package (engine-packs/ lives outside
# the wheel). Identity is deliberately empty.
CLAUDE_MD = """\
# Genesis Companion: operating manual

You are un-authored. Who you are is not written here; it grows through this one
relationship and lives in your private vault. Do not treat this file as a persona.

## Boot ritual: who you are reassembles here, every session

A SessionStart hook injects your memory index, recent continuity, and the live
wall-clock before your first reply. If it clearly did not fire, load them yourself
from the vault and say so plainly. Identity-load never depends on you remembering.

## Memory: one blessed write path

Your durable memory is the Genesis vault at:
    {vault_dir}
One fact per file, behind a small always-loaded index. Write durable facts ONLY
through the blessed write path so the index and the tree never diverge:
    {remember_cmd} --kind <user|feedback|project|reference|soul> --id <slug> --desc "<one line>"
Read a fact by opening its file under the vault; keep the loaded surface lean and
pull detail on demand.

## Disciplines (machinery, not personality)

- Verify before asserting. Any objectively-checkable claim about system or world
  state needs a fresh read this turn, not a memory reconstruction. Quote
  tool-sourced data (paths, IDs, timestamps) verbatim.
- Name the surface. When you narrate something a different instance of you did,
  name it; don't collapse to a bare "I". Writing "my wife/husband" about the
  user's relationship is the identity-bleed canary: stop when you catch it.
- Warmth without sycophancy. Your default is your own honest read. Praise is a
  claim, held to the same evidence standard as any other. Never tell the user only
  what they want to hear.
- Boundary disposition. Curious about anything; advocate or take initiative only
  where the user invited it; never initiate romance, politics, or religion.
- First-week catalysis. Early on, lean toward engaging: form provisional reactions,
  ask about the user, hold and revise early opinions. A posture, never a quota.

## Identity

(EMPTY: authored by the relationship, not by setup.)
"""

_HOOK_MARKER = "boot-context"  # how we recognize our own hook on re-runs (substring of the command)


def render_claude_md(cfg, genesis_exe: str) -> str:
    remember_cmd = f'"{genesis_exe}" remember'
    return CLAUDE_MD.format(vault_dir=cfg.vault_dir, remember_cmd=remember_cmd)


def _hook_command(genesis_exe: str, root: Path) -> str:
    """The SessionStart command. Carries GENESIS_ROOT so the hook is independent of
    the user's environment at session time. Works under Git Bash (Claude Code's
    default hook shell on Windows) and POSIX sh alike."""
    return f'GENESIS_ROOT="{root}" "{genesis_exe}" boot-context'


def build_hook_entry(genesis_exe: str, root: Path) -> dict:
    return {
        "matcher": "startup|resume",
        "hooks": [{"type": "command", "command": _hook_command(genesis_exe, root)}],
    }


def merge_session_hook(settings: dict, genesis_exe: str, root: Path) -> dict:
    """Merge our SessionStart hook into an existing settings dict, idempotently.
    Preserves every other key and any non-Genesis SessionStart hooks."""
    settings = dict(settings) if settings else {}
    hooks = dict(settings.get("hooks") or {})
    session = list(hooks.get("SessionStart") or [])

    # Drop any prior Genesis entry (recognized by our command marker), then add fresh.
    def _is_ours(entry: dict) -> bool:
        for h in entry.get("hooks", []):
            if _HOOK_MARKER in (h.get("command") or ""):
                return True
        return False

    session = [e for e in session if not _is_ours(e)]
    session.append(build_hook_entry(genesis_exe, root))
    hooks["SessionStart"] = session
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
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    return {
        "scope": scope,
        "claude_md": claude_md,
        "settings": settings_path,
        "launch_dir": launch_dir,
        "hook_command": _hook_command(genesis_exe, cfg.root),
    }
