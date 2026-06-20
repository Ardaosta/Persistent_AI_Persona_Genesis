"""Guarded shell, file-read, and file-write tools for the install-guide loop.

Security model (v0 — single trusted user on their own box):
- shell_run: deny-list (no sudo, no rm -rf /, no remote-pipe-exec) + non-interactive
  (stdin=DEVNULL) + timeout + append-only audit.  A real OS sandbox (seatbelt /
  bubblewrap) is the named gate before user #2.
- file_read: deny reads inside the secrets dir; allow everything else.
- file_write: path-pinned to vault_dir; writing outside the vault is structurally
  impossible through this tool.

Audit: every call appends a one-line JSON record to $GENESIS_ROOT/tool-audit.log
using O_APPEND (POSIX atomic for short writes).
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from genesis_backend import ToolSpec

# ---------------------------------------------------------------------------
# Deny-list for shell_run (compiled once)
# ---------------------------------------------------------------------------

_SHELL_DENY: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bsudo\b"),
     "sudo is not permitted"),
    # deny rm -rf of / itself, ~ itself, and direct children of / (e.g. /usr /etc /home)
    # but allow deeper paths like /tmp/genesis-xyz (two or more levels deep)
    (re.compile(r"rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/[^/\s]*|~)(\s|$)"),
     "recursive rm at / ~ or a top-level system dir is not permitted"),
    # block both `curl ... | sh` and `/bin/bash -c "$(curl ...)"` (command substitution)
    (re.compile(r"(curl|wget)\b[^|]*\|\s*(ba)?sh\b"),
     "remote pipe-exec is not permitted — install via brew/pip instead"),
    (re.compile(r"\$\(\s*(curl|wget)\b"),
     "remote command substitution is not permitted — install via brew/pip instead"),
    (re.compile(r"\bdd\b.*\bif="),
     "dd is not permitted"),
]

_MAX_OUTPUT = 4096  # truncate shell stdout+stderr to keep context manageable
_MAX_FILE = 8192    # truncate file reads likewise


# ---------------------------------------------------------------------------
# Append-only audit
# ---------------------------------------------------------------------------

def _audit(action: str, detail: str, root: Path) -> None:
    record = json.dumps({"t": datetime.now().isoformat(), "action": action, "d": detail[:300]})
    log = root / "tool-audit.log"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(record + "\n")


# ---------------------------------------------------------------------------
# Guards (raise PermissionError on violation)
# ---------------------------------------------------------------------------

def guard_shell(cmd: str) -> None:
    for pat, msg in _SHELL_DENY:
        if pat.search(cmd):
            raise PermissionError(msg)


def guard_read(path: Path, secrets_dir: Path) -> None:
    try:
        path.resolve().relative_to(secrets_dir.resolve())
    except ValueError:
        return  # not inside secrets_dir, allowed
    raise PermissionError("reading from the secrets directory is not permitted")


def guard_write(path: Path, vault_dir: Path) -> None:
    try:
        path.resolve().relative_to(vault_dir.resolve())
    except ValueError:
        raise PermissionError(
            f"file_write is path-pinned to the vault ({vault_dir}); cannot write to {path}"
        )


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

def run_shell(cmd: str, timeout: int, root: Path) -> str:
    try:
        guard_shell(cmd)
    except PermissionError as e:
        return f"denied: {e}"
    _audit("shell_run", cmd, root)
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=min(timeout, 120),
        )
    except subprocess.TimeoutExpired:
        return f"(timed out after {timeout}s)"
    out = (r.stdout + r.stderr).strip()
    if len(out) > _MAX_OUTPUT:
        out = out[:_MAX_OUTPUT] + f"\n…(truncated; {len(out)} chars total)"
    # Exit code goes AFTER the output so the model reads the content before the verdict.
    # "(exit N)" on non-zero; clean output on success.
    if r.returncode != 0:
        suffix = f"\n(exit {r.returncode})"
        return (out + suffix) if out else f"(exit {r.returncode})"
    return out or "(no output)"


def read_file(path: Path, secrets_dir: Path, root: Path) -> str:
    try:
        guard_read(path, secrets_dir)
    except PermissionError as e:
        return f"denied: {e}"
    _audit("file_read", str(path), root)
    if not path.exists():
        return f"(file not found: {path})"
    if not path.is_file():
        return f"(not a regular file: {path})"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > _MAX_FILE:
        text = text[:_MAX_FILE] + f"\n…(truncated; {len(text)} chars total)"
    return text


def write_file(path: Path, content: str, vault_dir: Path, root: Path) -> str:
    try:
        guard_write(path, vault_dir)
    except PermissionError as e:
        return f"denied: {e}"
    _audit("file_write", str(path), root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


# ---------------------------------------------------------------------------
# ToolSpec objects (imported by agent.py and added to TOOLS)
# ---------------------------------------------------------------------------

SHELL_TOOL = ToolSpec(
    name="shell_run",
    description=(
        "Run a shell command non-interactively (no stdin). Use to check installed "
        "tools, install packages (brew, pip, apt), run git, verify paths, etc. "
        "Returns stdout+stderr, capped at ~4KB. Timeout defaults to 30s (max 120s). "
        "Important: in a semicolon-separated list (a; b; c) the exit code reflects "
        "the LAST command only — read each line of output to see which tools were found."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "cmd": {"type": "string", "description": "the command to run"},
            "timeout": {
                "type": "integer",
                "description": "seconds to wait before giving up; default 30, max 120",
            },
        },
        "required": ["cmd"],
    },
)

FILE_READ_TOOL = ToolSpec(
    name="file_read",
    description=(
        "Read a text file on this computer and return its contents (capped at ~8KB). "
        "Cannot read from the secrets directory."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "absolute path to the file"},
        },
        "required": ["path"],
    },
)

FILE_WRITE_TOOL = ToolSpec(
    name="file_write",
    description=(
        "Write text to a file inside your vault. Creates parent directories as needed. "
        "Path must be inside the vault; use this to set up config files, SOUL.md, etc."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "absolute path (must be inside the vault directory)",
            },
            "content": {"type": "string", "description": "text to write"},
        },
        "required": ["path", "content"],
    },
)
