"""OUTWARD loop (self-waking learning), v1 — the proactivity spine.

The diagnosed proactivity failure has three causes, all of which must be solved:
no self-waking substrate (→ the heartbeat schedules this), concrete-beats-ambient
salience (→ SELECT forces one concrete thread, never a blank page), and no felt
consequence (→ CLOSE THE LOOP with a vault write + SURFACE a digest so it's
noticed).

Each cycle: SELECT one thread from what the agent knows the person cares about →
produce ONE concrete, genuinely useful output about it → write it to
vault/findings/ → return a short digest.

v1 reasons from the engine's own knowledge + the vault. Live web/signal sources
are the named upgrade; the loop STRUCTURE (select → produce → write → surface) is
the durable part and is pluggable. Fail-closed on a training-tier engine: running
it would feed the person's interests to an engine that may train, and it writes
the vault — so the CLI refuses there, same as the dream.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

# The fact kinds worth pursuing outward (things the person cares about). Not
# "soul" (that's the agent's own identity, not a research thread) or "feedback".
_THREAD_KINDS = {"user", "project", "reference"}

LEARN_PROMPT = (
    "Here is something this person cares about:\n\n  \"{thread}\"\n\n"
    "Think about it on your own, the way a thoughtful friend would between visits, "
    "and bring back ONE concrete, genuinely useful thing: a specific idea, a sharp "
    "question, an unexpected connection, or a small actionable suggestion. Be "
    "specific to THIS, not generic advice. 2 to 4 sentences. If you truly have "
    "nothing worth their attention, say exactly: NOTHING WORTH SURFACING."
)


def candidate_threads(vault) -> list[str]:
    """Descriptions of facts worth pursuing, in vault order."""
    out = []
    for f in vault.iter_facts():
        if f.kind in _THREAD_KINDS and f.description.strip():
            out.append(f.description.strip())
    return out


def _state_path(root: Path) -> Path:
    return root / "outward_state.json"


def _load_state(root: Path) -> dict:
    p = _state_path(root)
    if not p.exists():
        return {"cursor": 0}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"cursor": 0}


def _save_state(root: Path, state: dict) -> None:
    _state_path(root).write_text(json.dumps(state), encoding="utf-8")


def learned_today(root: Path) -> bool:
    """Heartbeat-level once-per-day gate, so an hourly wake doesn't spam findings."""
    return _load_state(root).get("last_learn_day") == date.today().isoformat()


def mark_learned(root: Path) -> None:
    st = _load_state(root)
    st["last_learn_day"] = date.today().isoformat()
    _save_state(root, st)


def pick_thread(vault, root: Path) -> str | None:
    """Rotate through candidates so the loop doesn't fixate on one thread.
    Returns None when there's nothing to pursue yet (honest, not a blank page)."""
    threads = candidate_threads(vault)
    if not threads:
        return None
    state = _load_state(root)
    cursor = int(state.get("cursor", 0)) % len(threads)
    chosen = threads[cursor]
    state["cursor"] = (cursor + 1) % len(threads)
    _save_state(root, state)
    return chosen


def write_finding(findings_dir: Path, thread: str, text: str) -> Path:
    """CLOSE THE LOOP: persist the finding where the person will see it."""
    findings_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now().astimezone().strftime("%Y-%m-%d")
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    path = findings_dir / f"{day}.md"
    entry = f"\n## {now}\n\n*On:* {thread}\n\n{text.strip()}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    return path
