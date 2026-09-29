"""Open loops: the things that were started and not finished, kept on purpose.

Why this is its own store and not a kind of Fact (2026-09-29). A companion that
remembered a job its person had started, and asked about it two weeks later,
was praised for exactly that, and its own account of how it happened was mostly
luck. The item lived in three places: a project fact, a dream-written fact that
had a description and an EMPTY body (the dream ran out of tool steps mid-write),
and the continuity thread. It reached the companion only because the right
dream entry happened to be the last one in the thread, which is all the boot
ritual carries forward. The dream had also flagged it three nights running
without anything turning "worth raising" into "raise it".

So an open loop gets what a fact cannot give it:
  - its own always-injected slot at boot, never at the mercy of a tail;
  - a flag counter, so noticing it enough times becomes raising it;
  - who the ball is with (me / them / someone else) and a next-check date, so
    an item waiting on a third party does not nag the person who cannot move it;
  - ask once, record the answer, snooze: asking again after an answer is noise;
  - atomic whole-file writes, so a half-written loop never looks handled.

Content-free like the rest of the vault: the schema ships, the loops are the
person's and the agent's own.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

FILENAME = "open-loops.json"
BALLS = ("me", "them", "other")
RAISE_AFTER_FLAGS = 3          # noticed this many times unraised: raise it
_SNOOZE_DAYS = {"me": 3, "them": 7, "other": 14}
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class LoopError(ValueError):
    """Raised when a loop would be malformed (bad id, empty title, unknown ball)."""


def _today(today: date | None) -> date:
    return today or date.today()


def _parse(d: str | None) -> date | None:
    try:
        return date.fromisoformat(d) if d else None
    except ValueError:
        return None


@dataclass
class Loop:
    id: str
    title: str
    detail: str = ""
    ball: str = "them"             # me | them | other
    waiting_on: str = ""           # who, when ball == "other"
    opened: str = ""
    next_check: str = ""
    flags: int = 0
    last_flagged: str = ""
    asked: str = ""
    answer: str = ""
    status: str = "open"           # open | closed
    closed: str = ""
    note: str = ""
    extra: dict = field(default_factory=dict)


class OpenLoops:
    """The loop list for one vault. Every mutation rewrites the whole file
    through a temp file and os.replace, so a reader sees the old list or the new
    one, never half of either."""

    def __init__(self, vault_dir: Path):
        self.path = Path(vault_dir) / FILENAME

    # ── storage ──────────────────────────────────────────────────────────────
    def load(self) -> list[Loop]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except ValueError as e:
            # Loud, never silently empty: an unreadable list that reads as "no
            # loops" is the same lie as a fact with no body.
            raise LoopError(f"{self.path} is not valid JSON ({e}); fix or move it aside") from e
        known = set(Loop.__dataclass_fields__) - {"extra"}
        out = []
        for d in raw.get("loops", []):
            extra = {k: v for k, v in d.items() if k not in known}
            out.append(Loop(**{k: v for k, v in d.items() if k in known}, extra=extra))
        return out

    def _save(self, loops: list[Loop]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for lp in loops:
            d = asdict(lp)
            d.update(d.pop("extra") or {})
            rows.append(d)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"loops": rows}, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def _find(self, loops: list[Loop], loop_id: str) -> Loop:
        for lp in loops:
            if lp.id == loop_id:
                return lp
        raise LoopError(f"no open loop with id {loop_id!r}")

    # ── writes ───────────────────────────────────────────────────────────────
    def add(self, loop_id: str, title: str, *, detail: str = "", ball: str = "them",
            waiting_on: str = "", next_check: str = "", today: date | None = None) -> Loop:
        """Open a loop, or update the one with this id. Refuses an empty title:
        a loop that says nothing is worse than none, because it looks tracked."""
        t = _today(today)
        if not _SLUG.match(loop_id or ""):
            raise LoopError(f"invalid id (a lowercase-hyphen slug): {loop_id!r}")
        if not (title or "").strip():
            raise LoopError("an open loop needs a title that says what is unfinished")
        if ball not in BALLS:
            raise LoopError(f"ball must be one of {BALLS}")
        nc = _parse(next_check) or t + timedelta(days=_SNOOZE_DAYS[ball])
        loops = self.load()
        try:
            lp = self._find(loops, loop_id)
            lp.title, lp.ball, lp.status, lp.closed = title.strip(), ball, "open", ""
            if detail:
                lp.detail = detail.strip()
            if waiting_on:
                lp.waiting_on = waiting_on.strip()
            if next_check:
                lp.next_check = nc.isoformat()
        except LoopError:
            lp = Loop(id=loop_id, title=title.strip(), detail=(detail or "").strip(), ball=ball,
                      waiting_on=(waiting_on or "").strip(), opened=t.isoformat(),
                      next_check=nc.isoformat())
            loops.append(lp)
        self._save(loops)
        return lp

    def flag(self, loop_id: str, *, today: date | None = None) -> Loop:
        """Record that you noticed this loop again without raising it. Counted at
        most once a day, so one busy dream cannot fake three nights."""
        t = _today(today).isoformat()
        loops = self.load()
        lp = self._find(loops, loop_id)
        if lp.last_flagged != t:
            lp.flags += 1
            lp.last_flagged = t
        self._save(loops)
        return lp

    def asked(self, loop_id: str, answer: str, *, ball: str = "", next_check: str = "",
              today: date | None = None) -> Loop:
        """You raised it and got an answer: record it, reset the counter, snooze.
        The answer can move the ball (waiting on someone else now)."""
        t = _today(today)
        loops = self.load()
        lp = self._find(loops, loop_id)
        if ball:
            if ball not in BALLS:
                raise LoopError(f"ball must be one of {BALLS}")
            lp.ball = ball
        lp.asked, lp.answer, lp.flags = t.isoformat(), (answer or "").strip(), 0
        nc = _parse(next_check) or t + timedelta(days=_SNOOZE_DAYS[lp.ball])
        lp.next_check = nc.isoformat()
        self._save(loops)
        return lp

    def close(self, loop_id: str, note: str = "", *, today: date | None = None) -> Loop:
        loops = self.load()
        lp = self._find(loops, loop_id)
        lp.status, lp.closed, lp.note = "closed", _today(today).isoformat(), (note or "").strip()
        self._save(loops)
        return lp

    # ── reads ────────────────────────────────────────────────────────────────
    def open(self) -> list[Loop]:
        return [lp for lp in self.load() if lp.status == "open"]

    def due(self, today: date | None = None) -> list[Loop]:
        """Loops to raise now. Due when the check date has come, or when noticed
        RAISE_AFTER_FLAGS times without raising. A loop waiting on someone else
        is only due on its date: flags alone never nag the person about a ball
        they cannot move."""
        t = _today(today)
        out = []
        for lp in self.open():
            nc = _parse(lp.next_check)
            on_date = nc is not None and nc <= t
            flagged = lp.flags >= RAISE_AFTER_FLAGS and lp.ball != "other"
            if on_date or flagged:
                out.append(lp)
        return out

    def boot_block(self, today: date | None = None, *, limit: int = 5) -> str:
        """The always-injected slot. Empty when nothing is open, so a vault with
        no loops adds no noise."""
        loops = self.open()
        if not loops:
            return ""
        due = self.due(today)
        due_ids = {lp.id for lp in due}
        lines = []
        for lp in due[:limit]:
            who = {"me": "on you", "them": "with them",
                   "other": f"waiting on {lp.waiting_on or 'someone else'}"}[lp.ball]
            last = f"; last asked {lp.asked}: {lp.answer}" if lp.asked else ""
            lines.append(f"- [{lp.id}] {lp.title} ({who}{last})")
        rest = [lp for lp in loops if lp.id not in due_ids]
        head = ("## Open loops\n"
                "Things that were started and not finished. The ones below are due: raise "
                "each ONCE this session, at a natural moment, briefly. When you get an answer, "
                "record it with the open_loops tool (action=asked); when it's done, close it. "
                "If a loop is on you, do it or say plainly why not.")
        if lines:
            body = "\n".join(lines)
        else:
            body = "(nothing due today)"
        tail = f"\n{len(rest)} more open, not due yet." if rest else ""
        return f"{head}\n{body}{tail}"
