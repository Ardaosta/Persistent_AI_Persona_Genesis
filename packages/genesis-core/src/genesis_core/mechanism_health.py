"""One snapshot of every loop that maintains this AI, and whether it is firing.

A framework like this is a pile of scheduled loops the person cannot watch:
dream, learn, capture, hygiene, the heartbeat under all of them. Every one can
die into a silence that is indistinguishable from health, because a loop that
never runs produces exactly what a loop with nothing to say produces. Nothing.

The rule this module exists to enforce, learned by an audit that found four
mechanisms green by their own account and dead by their logs:

    A mechanism's `last_fired` comes from PRIMARY EVIDENCE, never from the
    mechanism's own status output.

The distinction is the whole design. `genesis dream` writes a daykey when it
finishes, and `genesis status` reads that daykey to tell you when it last
dreamed. But the daykey is the loop's own note about itself: if the reflection
came back empty, or the journal write failed, the daykey still lands and status
still says "last dream: today". The journal ENTRY is the artifact the work
produced, so the journal is the evidence and the daykey is a claim.

Which means the two disagreeing is itself the most valuable finding here. A
fresh self-report sitting on top of stale evidence is not a loop running late,
it is a loop reporting success it did not have.

STATUSES
  ok            evidence of firing inside this mechanism's freshness window
  stale         evidence exists, older than the window
  failed        positive evidence of breakage, including a self-report that
                contradicts its own evidence
  never_fired   wired, readable, and nothing has happened yet (normal on a
                fresh install, and NOT a problem)
  unreachable   this vantage point cannot see the evidence at all

`never_fired` and `unreachable` are kept apart on purpose. The first is a fact
about the mechanism; the second is a fact about where you are standing, and
collapsing them turns "I cannot see" into "it is not there", which is the same
error as reading a null search result as an empty world.

Windows are PER MECHANISM. One global freshness number cannot be right for both
an hourly heartbeat and a capture queue where ten quiet days is healthy, and a
single number tuned for either one lies about the other.
"""

from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

SCHEMA = "mechanism_health v1"

STATUSES = ("ok", "stale", "failed", "never_fired", "unreachable")

# A snapshot older than this is itself a finding: a consumer reading a two-day-old
# health file is reading history and can easily mistake it for the present.
SNAPSHOT_STALE_HOURS = 48

# Per-mechanism freshness, in hours. Each number is an argument, not a default.
WINDOWS = {
    "heartbeat": 2,        # hourly wake; one miss is noise, two is a signal
    "dream": 26,           # once a day, with slack for a late wake
    "learn": 26,           # same cadence as the dream
    "graph_hygiene": 26,   # runs inside the dream
    "capture": 240,        # 10 days. Sparse capture is HEALTHY: a loop with a
                           # high bar should be quiet, and a window tight enough
                           # to flag honest silence teaches people to ignore it.
}


def _age_hours(path: Path):
    """Hours since path was last written, or None if it cannot be read.

    None means UNREACHABLE, never zero and never "old". Returning a number here
    on failure is how a vantage-point problem gets recorded as a mechanism fact.
    """
    try:
        return (time.time() - path.stat().st_mtime) / 3600.0
    except OSError:
        return None


def _iso(path: Path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return None


def _newest(directory: Path, pattern: str = "*"):
    """The most recently modified file in a directory, or None.

    Returns (path, None) when the directory is readable but empty, which is
    never_fired, and (None, "unreachable") when it cannot be read at all.
    """
    try:
        if not directory.is_dir():
            return None, "absent"
        # os.scandir, NOT glob. On a directory the caller cannot read, glob
        # returns an empty list rather than raising, so the unreadable case
        # arrives looking exactly like the empty case and gets reported as
        # never_fired. That is the one conflation this module exists to refuse:
        # "I cannot see" quietly becoming "it is not there". scandir raises.
        with os.scandir(directory) as it:
            names = [e.name for e in it]
        files = [q for q in (directory / n for n in names)
                 if q.is_file() and fnmatch(q.name, pattern)]
    except OSError:
        return None, "unreachable"
    if not files:
        return None, "empty"
    return max(files, key=lambda p: p.stat().st_mtime), None


def _entry(name, status, last_fired, evidence, note=""):
    e = {
        "mechanism": name,
        "status": status,
        "last_fired": last_fired,
        "evidence_path": str(evidence),
    }
    if note:
        e["note"] = note
    return e


def _from_dir(name, directory: Path, pattern="*", note="", expected: Path = None):
    """Status for a mechanism whose firing leaves a file behind.

    `expected` names the artifact to point a reader at when nothing exists yet.
    Without it a never_fired entry points at a directory, and "go look in this
    folder" is a worse instruction than "this file should be here and is not".
    """
    newest, why = _newest(directory, pattern)
    window = WINDOWS.get(name, 26)
    absent_evidence = expected or directory
    if why == "unreachable":
        return _entry(name, "unreachable", None, absent_evidence,
                      "cannot read this from here, which is a fact about this "
                      "vantage point and not about the mechanism")
    if why in ("absent", "empty") or newest is None:
        return _entry(name, "never_fired", None, absent_evidence,
                      note or "wired, with nothing written yet")
    age = _age_hours(newest)
    if age is None:
        return _entry(name, "unreachable", None, newest)
    status = "ok" if age < window else "stale"
    return _entry(name, status, _iso(newest), newest, note)


def _dream_entry(cfg):
    """The dream, with its self-report cross-checked against its own output.

    This is the pattern the whole module is built around, so it is spelled out
    rather than folded into the generic helper. The daykey is what `genesis
    status` reads and it is the loop's note about itself; the journal entry is
    what the loop actually produced. When the note is fresh and the product is
    stale, the loop is reporting a success it did not have, and that is `failed`
    rather than `stale`: nothing is running late, something is lying.
    """
    e = _from_dir("dream", cfg.journal_dir, "*.md",
                  "the journal entry is the evidence; the daykey is only a claim")

    daykeys, why = _newest(cfg.root / "daykeys", "*.txt")
    if why or daykeys is None:
        return e
    claim_age = _age_hours(daykeys)
    if claim_age is None:
        return e
    e["self_reported"] = _iso(daykeys)

    if claim_age < WINDOWS["dream"] and e["status"] in ("stale", "never_fired"):
        e["status"] = "failed"
        e["note"] = (
            f"the daykey says it ran {claim_age:.0f}h ago, but the journal it should "
            f"have written is {'absent' if e['last_fired'] is None else 'older than that'}. "
            "A fresh self-report on stale evidence is not a late loop, it is a loop "
            "claiming a success it did not have."
        )
    return e


def _learn_entry(cfg):
    """Same cross-check for the outward loop: findings are the product, the
    state file's `last_learn_day` is the claim."""
    e = _from_dir("learn", cfg.findings_dir, "*.md",
                  "a written finding is the evidence; last_learn_day is only a claim")
    try:
        state = json.loads((cfg.root / "outward_state.json").read_text(encoding="utf-8"))
        claim = state.get("last_learn_day")
    except (OSError, ValueError):
        return e
    if not claim:
        return e
    e["self_reported"] = claim
    try:
        claim_age = (datetime.now() - datetime.fromisoformat(claim)).total_seconds() / 3600.0
    except ValueError:
        return e
    if claim_age < WINDOWS["learn"] and e["status"] in ("stale", "never_fired"):
        e["status"] = "failed"
        e["note"] = (
            "the loop recorded that it learned today, and produced no finding to show "
            "for it. The marker was written by the run that happened, not by the work "
            "that landed."
        )
    return e


def _heartbeat_entry(cfg):
    """The wake under everything else. Registration and firing are different
    questions: a job can be perfectly registered and never once run."""
    log = cfg.root / "heartbeat.log"
    age = _age_hours(log)
    if age is None:
        if log.exists():
            return _entry("heartbeat", "unreachable", None, log)
        return _entry("heartbeat", "never_fired", None, log,
                      "no heartbeat log yet. On POSIX the wrapper does not redirect "
                      "output, so this can also mean the log was never going to exist: "
                      "check `genesis schedule status` for whether the job is registered")
    status = "ok" if age < WINDOWS["heartbeat"] else "stale"
    return _entry("heartbeat", status, _iso(log), log)


def collect(cfg) -> list:
    """One entry per mechanism, in the order a reader should scan them."""
    return [
        _heartbeat_entry(cfg),
        _dream_entry(cfg),
        _learn_entry(cfg),
        _from_dir("graph_hygiene", cfg.root / "hygiene", "*.md"),
        _from_dir("capture", cfg.root, "capture_queue.jsonl",
                  "sparse by design; 10 quiet days is the flag, not 1",
                  expected=cfg.root / "capture_queue.jsonl"),
    ]


def snapshot(cfg) -> dict:
    return {
        "host": socket.gethostname(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "schema": SCHEMA,
        "mechanisms": collect(cfg),
    }


def write_snapshot(cfg) -> Path:
    path = cfg.root / "mechanism_health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot(cfg), indent=2), encoding="utf-8")
    return path


def findings(snap: dict) -> list:
    """Everything wrong in a snapshot, INCLUDING the snapshot's own age.

    A stale snapshot is listed first and deliberately: a consumer trusting an
    old health file will read every mechanism below it as current, which is the
    failure mode this whole file was written to prevent, arriving one level up.
    """
    out = []
    try:
        age = (datetime.now() - datetime.fromisoformat(snap["generated_at"])).total_seconds() / 3600
        if age > SNAPSHOT_STALE_HOURS:
            out.append(f"this snapshot is {age:.0f}h old, so everything below it is history")
    except (KeyError, ValueError):
        out.append("this snapshot has no readable generated_at, so its age cannot be judged")
    for m in snap.get("mechanisms", []):
        if m["status"] in ("failed", "stale"):
            out.append(f"{m['mechanism']}: {m['status']}")
    return out


def render(snap: dict) -> str:
    """Plain language. never_fired is stated as normal, because on a fresh
    install every loop is never_fired and a wall of alarming words would teach
    someone to disregard the one that matters later."""
    lines = [f"mechanisms, as of {snap['generated_at']} on {snap['host']}:"]
    for m in snap["mechanisms"]:
        when = m["last_fired"] or "never"
        lines.append(f"  {m['mechanism']:<14} {m['status']:<12} last: {when}")
        lines.append(f"                 evidence: {m['evidence_path']}")
        if m.get("self_reported") and m["status"] == "failed":
            lines.append(f"                 it claims: {m['self_reported']}")
        if m.get("note"):
            lines.append(f"                 {m['note']}")
    bad = findings(snap)
    lines.append("")
    if bad:
        lines.append("needs attention:")
        lines += [f"  {b}" for b in bad]
    else:
        lines.append("nothing is overdue. Loops that have never fired are listed above "
                     "as never_fired, which on a new install is correct and not a problem.")
    return "\n".join(lines)
