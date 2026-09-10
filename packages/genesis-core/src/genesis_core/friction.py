"""The CRAFT loop: friction capture with declared economics.

Three loops, three economies. The inward loop (capture -> dream) is a moonshot:
skipping it is safe and the bar is high. The outward loop (sylph) is exploratory.
This one is HOMEWORK: a homework loop done sixty percent of the time is a broken
loop, so it cannot be discretionary. Two things make it hold:

- Enforcement at the boundary, not mid-task. Mid-task the agent is goal-wired,
  the friction IS the obstacle, and the moment it is past it stops feeling like
  friction. Solved problems do not get written down. So the session-close gate
  (`genesis craft-gate`) asks, once, at the boundary.
- "None" is a first-class, non-penalized answer. Inventing filler to satisfy
  the gate is the failure mode. The explicit zero is what proves the loop is
  alive at all.

Each entry carries a trigger ("next time I'm doing X") and a win condition
("I'll have avoided Y") at capture; `won` is scored later, at audit. A loop
that never shows a `won: true` is journaling, and the stats say so out loud.
Like the soul-capture queue this is a local write only, so it is allowed on a
training-tier engine; only the adjudication that feeds the vault is fail-closed.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

KINDS = ("gap", "bug", "tooling")
DESTINATIONS = ("memory", "rule", "tool", "reviewed")  # reviewed = the dream saw it; refine later


def queue_path(root: Path) -> Path:
    return Path(root) / "friction_queue.jsonl"


def _append(root: Path, record: dict) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with queue_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def append_friction(root: Path, text: str, *, kind: str = "gap", mitigation: str = "",
                    trigger: str = "", win: str = "", project: str = "") -> bool:
    """Queue one friction. Returns False on empty text or an unknown kind."""
    text = (text or "").strip()
    if not text or kind not in KINDS:
        return False
    _append(Path(root), {
        "text": text[:800],
        "kind": kind,
        "mitigation": (mitigation or "").strip()[:400],
        "trigger": (trigger or "").strip()[:200],
        "win": (win or "").strip()[:200],
        "project": (project or "").strip()[:80],
        "won": None,
        "when": datetime.now().isoformat(),
    })
    return True


def append_none(root: Path) -> None:
    """Record the explicit zero. It is a healthy answer; the point is that it is RECORDED."""
    _append(Path(root), {"none": True, "when": datetime.now().isoformat()})


def load_queue(root: Path) -> list[dict]:
    p = queue_path(root)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue  # a corrupt line never takes the loop down
    return out


def last_entry_time(root: Path) -> datetime | None:
    """When the queue last received ANY entry (a real one or an explicit none)."""
    q = load_queue(root)
    for r in reversed(q):
        try:
            return datetime.fromisoformat(r["when"])
        except Exception:
            continue
    return None


def pending(root: Path) -> list[dict]:
    """Real frictions not yet routed (no `destination`)."""
    return [r for r in load_queue(root) if not r.get("none") and not r.get("destination")]


def stats(root: Path) -> dict:
    q = load_queue(root)
    real = [r for r in q if not r.get("none")]
    return {
        "entries": len(real),
        "explicit_none": sum(1 for r in q if r.get("none")),
        "with_win": sum(1 for r in real if r.get("win")),
        "won": sum(1 for r in real if r.get("won") is True),
        "routed": sum(1 for r in real if r.get("destination")),
    }


def route(root: Path, index: int, destination: str, note: str = "") -> bool:
    """Mark entry `index` (0-based among ALL queue lines) as routed to one of the
    three homes. Rewrites the queue atomically. The routing IS the adjudication."""
    if destination not in DESTINATIONS:
        return False
    q = load_queue(root)
    if not 0 <= index < len(q) or q[index].get("none"):
        return False
    q[index]["destination"] = destination
    q[index]["routed_at"] = datetime.now().isoformat()
    if note:
        q[index]["route_note"] = note[:300]
    _rewrite(root, q)
    return True


def score(root: Path, index: int, won: bool) -> bool:
    """Record at audit whether the win condition was actually met."""
    q = load_queue(root)
    if not 0 <= index < len(q) or q[index].get("none"):
        return False
    q[index]["won"] = bool(won)
    q[index]["scored_at"] = datetime.now().isoformat()
    _rewrite(root, q)
    return True


def _rewrite(root: Path, records: list[dict]) -> None:
    p = queue_path(root)
    tmp = p.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    tmp.replace(p)


def format_for_dream(records: list[dict]) -> str:
    """Render pending frictions for the dream's routing prompt."""
    lines = []
    for i, r in enumerate(records, 1):
        extra = []
        if r.get("trigger"):
            extra.append(f"trigger: {r['trigger']}")
        if r.get("win"):
            extra.append(f"win: {r['win']}")
        if r.get("mitigation"):
            extra.append(f"mitigation: {r['mitigation']}")
        tail = f"  ({'; '.join(extra)})" if extra else ""
        lines.append(f"{i}. [{r.get('kind', 'gap')}] \"{r['text']}\"{tail}")
    return "\n".join(lines)


def journaling_warning(root: Path, *, min_entries: int = 12) -> str:
    """A loop that never shows a won:true is journaling. Say so once it has enough
    entries for the silence to mean something."""
    s = stats(root)
    if s["entries"] >= min_entries and s["won"] == 0:
        return (f"friction loop has {s['entries']} entries and no scored win; "
                "that is journaling, not learning. Score some (`genesis friction --won N`).")
    return ""
