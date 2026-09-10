"""Mode B, second door: wire OpenAI Codex (the CLI / desktop app) as a Genesis frontend.

Same shape as claude_wire, different file names, verified against the Codex docs
2026-09-10 (learn.chatgpt.com/docs/hooks and /docs/config-file/config-reference):

  AGENTS.md          Codex's project instructions file. Discovered from the
                     project root (walking up from cwd); a global fallback lives
                     at ~/.codex/AGENTS.md. Capped by `project_doc_max_bytes`
                     (32 KiB default), which our manual sits well under.
  .codex/hooks.json  Lifecycle hooks, discovered next to the active config layer.
                     Same JSON shape as Claude Code's: event -> [{matcher, hooks:
                     [{type: "command", command}]}]. For SessionStart and
                     UserPromptSubmit, plain text on stdout is added as developer
                     context; Stop reads exit 2 + stderr as a blocking reason.
                     Codex caps injected context (~2,500 tokens by default) and
                     accepts `additionalContextLimit` to raise it; the boot
                     context can run past the default, so we set it.
  ~/.codex/config.toml
                     Project-level config and hooks load ONLY for a trusted
                     project, and trust is recorded in the USER config under
                     `[projects.'<path>'] trust_level = "trusted"`. We merge one
                     marked block, idempotently, and touch nothing else.

Hooks shipped as enabled-by-default in the current Codex; older builds gated
them behind `[features] codex_hooks = true`. We do not write feature flags: an
unknown key is a worse failure than a missing hook, and `genesis doctor` can
tell the person whether the boot block actually arrived.

Everything here is idempotent: re-running updates in place and never duplicates a
hook or clobbers unrelated settings. Identity stays EMPTY (the empty-shipping
invariant holds; the manual is machinery only).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import manual

_HOOK_MARKERS = ("boot-context", "reanchor", "craft-gate")
_BLOCK_START = "# >>> genesis (managed block, rewritten by `genesis wire-codex`; edits here are lost) >>>"
_BLOCK_END = "# <<< genesis <<<"
CONTEXT_LIMIT = 12000  # tokens; the boot context on a mature vault exceeds Codex's ~2,500 default


def _posix(p) -> str:
    return str(p).replace("\\", "/")


def render_agents_md(cfg, genesis_exe: str) -> str:
    return manual.render(cfg, genesis_exe, harness="codex")


def _cmd(genesis_exe: str, root: Path, verb: str) -> str:
    return f'GENESIS_ROOT="{_posix(root)}" "{_posix(genesis_exe)}" {verb} --hook'


def hook_entries(genesis_exe: str, root: Path) -> dict:
    """Our three hooks, keyed by Codex event name."""
    return {
        "SessionStart": {
            "hooks": [{
                "type": "command",
                "command": _cmd(genesis_exe, root, "boot-context"),
                "additionalContextLimit": CONTEXT_LIMIT,
            }],
        },
        "UserPromptSubmit": {
            "hooks": [{
                "type": "command",
                "command": _cmd(genesis_exe, root, "reanchor"),
            }],
        },
        "Stop": {
            "hooks": [{
                "type": "command",
                "command": _cmd(genesis_exe, root, "craft-gate"),
            }],
        },
    }


def _is_ours(entry: dict) -> bool:
    for h in entry.get("hooks", []):
        cmd = h.get("command") or ""
        if any(m in cmd for m in _HOOK_MARKERS):
            return True
    return False


def merge_hooks(hooks_json: dict, genesis_exe: str, root: Path) -> dict:
    """Merge our hooks into an existing hooks.json dict, idempotently. Preserves
    every foreign hook and every other key."""
    doc = dict(hooks_json) if hooks_json else {}
    hooks = dict(doc.get("hooks") or {})
    for event, entry in hook_entries(genesis_exe, root).items():
        existing = [e for e in (hooks.get(event) or []) if not _is_ours(e)]
        existing.append(entry)
        hooks[event] = existing
    doc["hooks"] = hooks
    return doc


def trust_block(home: Path) -> str:
    # A TOML literal-string key needs no escaping, so a Windows path with
    # backslashes survives verbatim.
    return "\n".join([
        _BLOCK_START,
        f"[projects.'{home}']",
        'trust_level = "trusted"',
        _BLOCK_END,
        "",
    ])


def merge_trust(config_text: str, home: Path) -> str:
    """Replace or append our marked block in the user's config.toml text."""
    text = config_text or ""
    block = trust_block(home)
    if _BLOCK_START in text and _BLOCK_END in text:
        start = text.index(_BLOCK_START)
        end = text.index(_BLOCK_END) + len(_BLOCK_END)
        # swallow one trailing newline so re-runs do not grow the file
        if end < len(text) and text[end] == "\n":
            end += 1
        return text[:start] + block + text[end:]
    if text and not text.endswith("\n"):
        text += "\n"
    return text + ("\n" if text else "") + block


def _read_json(path: Path) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def wire(cfg, genesis_exe: str, *, home_dir: Path | None = None,
         codex_home: Path | None = None) -> dict:
    """Write AGENTS.md + .codex/hooks.json into the AI's home, and the trust entry
    into the user's Codex config. Returns what was written, for the caller to report."""
    home = Path(home_dir) if home_dir else cfg.root
    agents_md = home / "AGENTS.md"
    hooks_path = home / ".codex" / "hooks.json"
    codex_home = Path(codex_home) if codex_home else Path.home() / ".codex"
    config_toml = codex_home / "config.toml"

    agents_md.parent.mkdir(parents=True, exist_ok=True)
    agents_md.write_text(render_agents_md(cfg, genesis_exe), encoding="utf-8")

    hooks = merge_hooks(_read_json(hooks_path), genesis_exe, cfg.root)
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps(hooks, indent=2) + "\n", encoding="utf-8")

    config_toml.parent.mkdir(parents=True, exist_ok=True)
    existing = config_toml.read_text(encoding="utf-8") if config_toml.is_file() else ""
    config_toml.write_text(merge_trust(existing, home), encoding="utf-8")

    return {
        "agents_md": agents_md,
        "hooks": hooks_path,
        "config_toml": config_toml,
        "launch_dir": home,
        "hook_command": _cmd(genesis_exe, cfg.root, "boot-context"),
    }
