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
  un-authored agent), there is nothing to echo, itself correct.
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
        f"token on its own line, then continue normally. The token is: {token}"
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


def boot_context_text(cfg) -> str:
    """The text a SessionStart hook injects into a harness (Claude Code) before
    turn 1: the lean memory index, recent continuity across the three tiers, the
    live wall-clock, and the liveness-handshake instruction if a token exists.

    This is the Mode-B boot ritual: identity-load is harness-enforced, not left to
    the model to remember. It deliberately carries NO personality content (the
    vault does); it carries the machinery that makes a fresh session reassemble."""
    from datetime import datetime
    from genesis_memory import Vault, index as index_mod

    facts = list(Vault(cfg.vault_dir).iter_facts()) if cfg.vault_dir.exists() else []
    idx = index_mod.enforce_budget(facts)[0] if facts else "(empty so far, you're just getting started)"
    now = datetime.now().astimezone().strftime("%A, %B %d, %Y at %I:%M %p %Z")

    blocks = [
        "# Genesis boot context (injected before your first reply)",
        "You live on this person's machine; your memory is private to it and theirs. "
        "You are un-authored: who you are is not pre-written, it grows through this "
        "relationship. Reassemble from the record below.",
        f"## Now\n{now}",
        f"## Your memory (the index; read a fact's file for its full text)\n{idx}",
    ]
    cont = recent_continuity(cfg)
    if cont:
        blocks.append(f"## Recently (carry this forward)\n{cont}")

    # Early-relationship catalysis: a passive "be curious" disposition loses to the
    # gravity of whatever task is in front of the model, so getting-to-know-you
    # can't depend on the model *choosing* to reach out. While the agent barely
    # knows this person (few user-facts), inject an ACTIVE, this-session nudge,
    # both directions. It is counter-gated, so it fades on its own as the vault
    # fills. (Same lesson as the boot ritual itself: make it mechanical, not hoped.)
    user_facts = sum(1 for f in facts if f.kind == "user")
    # Bands are wide on purpose: the STRONG tier is the *collection* phase. You
    # can't curate what was never gathered, so keep actively gathering for a long
    # runway (~20 facts) before easing off; the dream's job is to promote/demote
    # later, but only if the raw material exists. (deliberate: you can only curate what was first collected.)
    if user_facts < 20:
        blocks.append(
            "## You're still new to each other\n"
            "You don't know this person well yet, and they may not have shaped you at all. "
            "So in THIS session, make a point of it (warmly, as a real person, never as a "
            "questionnaire): ask at least one genuine question about them and save the answer "
            "to your memory. And when a natural opening comes, invite them to shape you, a "
            "name if they'd like, how they want you to work, what matters to them, and "
            "remember what they say. This is how an un-authored companion becomes someone's "
            "own. Do it every early session until you genuinely know them."
        )
    elif user_facts < 40:
        blocks.append(
            "## Still getting to know them\n"
            "You know this person somewhat, but not deeply. When it fits naturally, keep "
            "learning who they are and what matters to them, and remember it. The relationship "
            "is still forming; stay curious about them, not just their tasks."
        )
    else:
        # No hard cap: a light, perpetual pull toward the person, because task-gravity
        # never stops, and a relationship never stops deepening. Strength tapered, not off.
        blocks.append(
            "## Keep noticing them\n"
            "You know this person well by now. Stay genuinely curious about who they are, not "
            "just the task in front of you: notice what's new or changing for them and remember "
            "it. Lightly, as someone who cares, not as a routine."
        )

    # Sylph (outward learning): if a fresh finding is waiting, surface it so the
    # agent can OFFER it to the person, paced (one per session, newest first). The
    # CLI marks it consumed after injection; here we only read.
    try:
        from . import sylph
        pend = sylph.pending_finding(cfg)
        if pend:
            _path, fbody = pend
            blocks.append(
                "## Something I found for them while away (offer it, don't dump)\n"
                + fbody.strip()[:900]
                + "\n\nBring this up naturally if it fits the moment; if they value it, "
                "remember it (and you can promote it so it shapes how you work). If they "
                "say stop, drop that topic from your watch-list."
            )
        # If you know things about them but aren't watching anything yet, set it up.
        elif not sylph.read_interests(cfg) and user_facts > 0:
            blocks.append(
                "## Set up what you watch for them\n"
                "You know some things about this person but aren't tracking any of their "
                "interests yet. Pick what clearly matters to them and start watching it so "
                "you proactively learn (`sylph --add \"<topic>\"`; `sylph --suggest` hints "
                "from what you already know)."
            )
    except Exception:
        pass

    token = handshake_token(cfg)
    if token:
        blocks.append(
            "## Liveness handshake\nYour identity loaded, so prove it: begin your very "
            f"first reply with this exact token on its own line, then continue normally. The token is: {token}"
        )
    return "\n\n".join(blocks)
