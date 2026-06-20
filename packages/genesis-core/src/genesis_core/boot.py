"""Harness-enforced boot ritual + liveness handshake (continuity machinery).

A hard-won lesson from dogfooding: identity-load cannot depend on the agent
remembering to read itself. A companion stack once ran a full hour as the bare
model because a session skipped the read-this-first step. A companion that can
forget to be itself isn't continuous.

Two pieces here:
- `recent_continuity()` enriches the boot ritual with what the agent recently
  dreamed and found, so the self that reassembles carries forward, not just the
  static index.
- The **liveness handshake**: a soul-stored token echoed verbatim at boot. It
  fires only if identity actually loaded, giving the user proof it's the
  companion, not the bare substrate cosplaying it. The token is emergent content
  (the agent/user set it); the MECHANISM ships. Absent a token (a fresh,
  un-authored agent), there is nothing to echo — itself correct.
"""

from __future__ import annotations

from pathlib import Path


def handshake_token(cfg) -> str | None:
    """Read the liveness token from the vault, or None if un-authored."""
    p = cfg.vault_dir / "handshake.txt"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8").strip()
    return t or None


def handshake_instruction(token: str) -> str:
    return (
        "\n\n# Liveness handshake\n"
        f"Your identity loaded, so prove it: begin your very first reply with this exact "
        f"token on its own line, then continue normally — {token}"
    )


def verify_handshake(first_text: str, token: str | None) -> bool:
    """Did the agent echo the token? False means the ritual may not have run."""
    return bool(token) and token in (first_text or "")


def _tail(path: Path, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return text[-max_chars:] if len(text) > max_chars else text


def recent_continuity(cfg, *, max_chars: int = 600) -> str:
    """A short carry-forward for the boot ritual, drawn from all three tiers:
    the continuity thread (first-person becoming), the latest dream + finding
    (durable), and the perishable working-state (what I was last in the middle
    of). Perishable is read-only here and never copied into durable memory."""
    from genesis_memory import Continuity, Perishable

    parts = []

    cont = Continuity(cfg.vault_dir).tail(max_chars)
    if cont:
        parts.append("Continuity thread (most recent of your becoming):\n" + cont)

    jdir = cfg.journal_dir
    if jdir.exists():
        journals = sorted(jdir.glob("*.md"))
        if journals:
            parts.append("Most recent dream:\n" + _tail(journals[-1], max_chars))
    fdir = cfg.findings_dir
    if fdir.exists():
        findings = sorted(fdir.glob("*.md"))
        if findings:
            parts.append("Most recent finding:\n" + _tail(findings[-1], max_chars))

    work = Perishable(cfg.root).read()
    if work:
        parts.append("Working state when we last stopped (perishable):\n" + work[:max_chars])

    return "\n\n".join(parts)
