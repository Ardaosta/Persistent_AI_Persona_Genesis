"""Sylph: the outward learning loop. Devoted curiosity, in flight.

Where `dream` turns inward (reflect, consolidate), Sylph turns outward: it picks a
thread the person cares about, actually researches the live web for the current,
cited bleeding edge of it, and writes a concrete finding to vault/findings/. The
inward loop makes the agent wiser about what it holds; Sylph keeps it current.

The research ENGINE is a headless Claude Code session on the user's subscription
(`claude -p` with WebSearch, billed to the sub, no API key). Proven 2026-06-25:
apiKeySource null, real web search, cited findings, ~1 min/cycle. This is the
Mode-B-on-sub path; it needs the `claude` CLI present (Mode B installs it).

Watch-list: `vault/interests.md`, one topic per line. Sylph rotates through them so
no topic starves. The trust bar (real cited source, relevance) lives in the prompt
for now; a verification pass is the named upgrade (Phase 2).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path

_CLAUDE_CANDIDATES = [
    Path.home() / ".local" / "bin" / "claude",
    Path("/opt/homebrew/bin/claude"),
    Path("/usr/local/bin/claude"),
]


class SylphError(RuntimeError):
    pass


def claude_bin() -> str:
    for c in _CLAUDE_CANDIDATES:
        if c.exists():
            return str(c)
    return "claude"  # rely on PATH


def interests_path(cfg) -> Path:
    return cfg.vault_dir / "interests.md"


def read_interests(cfg) -> list[str]:
    p = interests_path(cfg)
    if not p.is_file():
        return []
    topics = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip().lstrip("-*").strip()
        if s and not s.startswith("#"):
            topics.append(s)
    return topics


def add_interest(cfg, topic: str) -> bool:
    """Add a watch-topic if not already present. Returns True if added."""
    topic = topic.strip()
    if not topic:
        return False
    existing = [t.lower() for t in read_interests(cfg)]
    if topic.lower() in existing:
        return False
    p = interests_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    header = "" if p.exists() else "# Things to keep an eye on for this person\n\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(f"{header}- {topic}\n")
    return True


def _next_topic(cfg, topics: list[str]) -> str | None:
    """Round-robin so each topic gets its turn."""
    if not topics:
        return None
    ptr = cfg.root / "sylph_ptr.txt"
    i = 0
    if ptr.exists():
        try:
            i = int(ptr.read_text().strip())
        except Exception:
            i = 0
    topic = topics[i % len(topics)]
    ptr.write_text(str((i + 1) % len(topics)), encoding="utf-8")
    return topic


RESEARCH_PROMPT = (
    "Search the web. Find ONE concrete, recent (last ~2 years), genuinely useful and "
    "ACTIONABLE finding about: {topic}. It must be something that would actually help "
    "the person who cares about this, not generic background. Output EXACTLY this and "
    "nothing else:\n"
    "FINDING: <one specific sentence> | SOURCE: <a real URL you actually retrieved> | "
    "WHY: <one sentence on why it's useful>\n"
    "If you cannot find a real, current, cited source, output only: NONE"
)


def _research(topic: str, *, cwd: Path, timeout: int = 200) -> str:
    """One headless claude-on-subscription web-research turn. Returns the raw result
    text (the FINDING|SOURCE|WHY line, or NONE)."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)   # force subscription auth (apiKeySource null)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    try:
        r = subprocess.run(
            [claude_bin(), "-p", RESEARCH_PROMPT.format(topic=topic),
             "--allowedTools", "WebSearch,WebFetch", "--output-format", "json"],
            capture_output=True, text=True, env=env, cwd=str(cwd), timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise SylphError("research timed out") from None
    except FileNotFoundError:
        raise SylphError("the `claude` CLI isn't installed (Sylph's research engine needs it)") from None
    try:
        d = json.loads(r.stdout)
    except Exception:
        raise SylphError(f"research call failed: {(r.stderr or r.stdout)[:200]}") from None
    if d.get("is_error"):
        raise SylphError("research returned an error")
    return (d.get("result") or "").strip()


def _parse(text: str) -> tuple[str, str, str]:
    def grab(label: str) -> str:
        m = re.search(rf"{label}:\s*(.+?)(?=\s*\|\s*(?:FINDING|SOURCE|WHY):|$)", text, re.I | re.S)
        return m.group(1).strip() if m else ""
    return grab("FINDING"), grab("SOURCE"), grab("WHY")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "topic"


def write_finding(cfg, topic: str, raw: str, *, today: str | None = None) -> Path:
    finding, source, why = _parse(raw)
    today = today or date.today().isoformat()
    fdir = cfg.findings_dir
    fdir.mkdir(parents=True, exist_ok=True)
    path = fdir / f"{today}-{_slug(topic)}.md"
    path.write_text(
        f"# {topic}\n\n_Sylph, {today}_\n\n"
        f"**Finding:** {finding or raw}\n\n"
        f"**Source:** {source}\n\n"
        f"**Why it's useful:** {why}\n",
        encoding="utf-8",
    )
    return path


def run_cycle(cfg, topic: str | None = None) -> dict | None:
    """One Sylph cycle: pick a thread, research it for real, write a cited finding.
    Returns {topic, path, finding, source, why} or None (no topics, or honest no-find)."""
    topic = topic or _next_topic(cfg, read_interests(cfg))
    if not topic:
        return None
    raw = _research(topic, cwd=cfg.root)
    if not raw or raw.strip().upper() == "NONE":
        return None
    path = write_finding(cfg, topic, raw)
    finding, source, why = _parse(raw)
    return {"topic": topic, "path": path, "finding": finding or raw, "source": source, "why": why}
