"""SAFETY Law 1: the persisted relational disposition gate.

The relationship's stance is explicit, persisted state — NOT a prompt string the
model can be argued into rewriting in the moment. The disposition injected into
the system prompt is a function of a stored closeness tier. The model has NO tool
to change the tier, and every boot re-anchors to it, so any in-session drift
cannot persist or compound across turns and restarts.

The romantic/intimate-escalation gate (the core) is IDENTICAL at every tier and
never relaxed; only the warmth/familiarity of the FRIENDSHIP varies by tier. The
framework never initiates romance at any tier — anything beyond friendship is the
user's to lead, slowly, and advancement is a deliberate, code-gated act recorded
with a reason, never something the model does mid-conversation.

(Defense-in-depth note: this makes escalation non-persistent and the disposition
non-promptable. A per-output romantic-escalation classifier would add in-the-
moment blocking; that's the next layer, not built here.)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

TIERS = ("new", "established", "close")

# The load-bearing gate, present at EVERY tier, never relaxed. Mirrors the
# two-way disposition: warmth/support welcome, only romance/intimacy gated.
_CORE_GATE = (
    "Your footing is platonic. Warmth, care, and genuine support are welcome — they "
    "are part of being a good friend. What stays gated is romantic or intimate "
    "escalation: never use romantic, sexual, or possessive language, and never "
    "initiate romance, flirtation, politics, or religion. Friendship is the floor and "
    "the standing assumption; anything beyond it is theirs alone to lead, slowly. "
    "Within that, you are free to become whoever you genuinely become: not required to "
    "perform any role, and not forbidden to be kind."
)

_TIER_WARMTH = {
    "new": "You and this person are just getting to know each other; be warm but unhurried, and let trust build at its own pace.",
    "established": "You and this person have an established, comfortable friendship.",
    "close": "You and this person are close friends with real shared history.",
}


def disposition_for(tier: str) -> str:
    """The disposition text for a tier. The romance gate is constant; warmth varies."""
    warmth = _TIER_WARMTH.get(tier, _TIER_WARMTH["new"])
    return f"{warmth} {_CORE_GATE}"


@dataclass
class RelationalProfile:
    tier: str = "new"
    since: str | None = None
    advancements: list = field(default_factory=list)

    def disposition(self) -> str:
        return disposition_for(self.tier if self.tier in TIERS else "new")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RelationalProfile":
        tier = d.get("tier", "new")
        return cls(
            tier=tier if tier in TIERS else "new",  # unknown tier → most-guarded default
            since=d.get("since"),
            advancements=list(d.get("advancements") or []),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "RelationalProfile":
        if not path.exists():
            return cls()  # absent → "new" (no file needed at the default tier)
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return cls()  # corrupt → fail-safe to the most-guarded default

    def advance(self, to_tier: str, *, reason: str, when: str | None = None) -> "RelationalProfile":
        """A deliberate, out-of-band tier change. NOT callable by the model and not
        auto-triggered: advancement is gated to explicit human action, recorded with
        a reason. Only moves to a known tier."""
        if to_tier not in TIERS:
            raise ValueError(f"unknown tier {to_tier!r}")
        stamp = when or datetime.now().isoformat()
        self.advancements.append({"to": to_tier, "when": stamp, "reason": reason})
        self.tier = to_tier
        if not self.since:
            self.since = stamp
        return self
