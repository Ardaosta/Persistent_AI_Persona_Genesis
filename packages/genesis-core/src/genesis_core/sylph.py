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
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

_CLAUDE_CANDIDATES = [
    Path.home() / ".local" / "bin" / "claude.exe",   # Windows native install
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


def oauth_token(cfg) -> str | None:
    """A durable Claude subscription token (from `claude setup-token`), for reliable
    headless/scheduled auth. Stored in secrets, never the vault."""
    p = cfg.secrets_dir / "claude_oauth_token"
    if p.is_file():
        t = p.read_text(encoding="utf-8").strip()
        return t or None
    return None


def _research(topic: str, *, cwd: Path, timeout: int = 200, token: str | None = None) -> str:
    """One headless claude-on-subscription web-research turn. Returns the raw result
    text (the FINDING|SOURCE|WHY line, or NONE)."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)   # force subscription auth (apiKeySource null)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token   # durable subscription auth for scheduled runs
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


# --- the trust gate (Phase 2): real cited source, soft-corroborated ---

def _fetch(url: str, timeout: int = 15) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Genesis Sylph)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return getattr(r, "status", r.getcode()), r.read(300_000).decode("utf-8", "replace")


def _distinctive_tokens(finding: str) -> list[str]:
    toks = set()
    toks.update(re.findall(r"\bv?\d+\.\d+[\w.]*\b", finding, re.I))      # versions: V1.4.2
    toks.update(re.findall(r"\b[A-Z][A-Za-z0-9_]{3,}\b", finding))       # ProperNouns / CamelCase / IDs
    return [t for t in toks if len(t) >= 3][:6]


def verify_finding(finding: str, source: str) -> dict:
    """The trust gate. The source MUST be a real URL that resolves (hard gate, kills
    hallucinated/dead links). Soft-check that distinctive terms from the claim
    actually appear on the page (corroboration). Returns {resolves, corroborated, reason}."""
    if not re.match(r"^https?://", (source or "").strip()):
        return {"resolves": False, "corroborated": False, "reason": "no real http(s) source URL"}
    try:
        status, body = _fetch(source.strip())
    except Exception as e:  # noqa: BLE001
        return {"resolves": False, "corroborated": False, "reason": f"source did not resolve ({type(e).__name__})"}
    if not (200 <= status < 400):
        return {"resolves": False, "corroborated": False, "reason": f"source returned HTTP {status}"}
    tokens = _distinctive_tokens(finding)
    text = re.sub(r"<[^>]+>", " ", body).lower()
    hits = sum(1 for t in tokens if t.lower() in text)
    corroborated = bool(tokens) and hits >= max(1, len(tokens) // 3)
    return {"resolves": True, "corroborated": corroborated,
            "reason": f"HTTP {status}; {hits}/{len(tokens)} key terms on page"}


def write_finding(cfg, topic: str, raw: str, *, today: str | None = None, verified: dict | None = None) -> Path:
    finding, source, why = _parse(raw)
    today = today or date.today().isoformat()
    fdir = cfg.findings_dir
    fdir.mkdir(parents=True, exist_ok=True)
    path = fdir / f"{today}-{_slug(topic)}.md"
    vline = ""
    if verified:
        tag = "verified" if verified.get("corroborated") else "source resolves (auto-corroboration weak)"
        vline = f"\n**Trust:** {tag} ({verified.get('reason','')})\n"
    path.write_text(
        f"# {topic}\n\n_Sylph, {today}_\n\n"
        f"**Finding:** {finding or raw}\n\n"
        f"**Source:** {source}\n\n"
        f"**Why it's useful:** {why}\n{vline}",
        encoding="utf-8",
    )
    return path


def _log(cfg, line: str) -> None:
    try:
        with (cfg.root / "sylph.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{date.today().isoformat()} {line}\n")
    except Exception:
        pass


# --- Phase 3: paced surfacing + watch-list tuning ---

def _surfaced_ledger(cfg) -> Path:
    return cfg.root / "sylph_surfaced.txt"


def _surfaced_set(cfg) -> set[str]:
    p = _surfaced_ledger(cfg)
    return set(p.read_text(encoding="utf-8").split()) if p.exists() else set()


def pending_finding(cfg):
    """The newest finding not yet surfaced to the person. Returns (path, body) or None.
    Findings are date-prefixed, so reverse-sorted name == newest-first."""
    fdir = cfg.findings_dir
    if not fdir.is_dir():
        return None
    done = _surfaced_set(cfg)
    files = sorted((f for f in fdir.glob("*.md") if f.name not in done), reverse=True)
    if not files:
        return None
    f = files[0]
    return f, f.read_text(encoding="utf-8")


def mark_surfaced(cfg, path) -> None:
    led = _surfaced_ledger(cfg)
    led.parent.mkdir(parents=True, exist_ok=True)
    with led.open("a", encoding="utf-8") as fh:
        fh.write(Path(path).name + "\n")


def remove_interest(cfg, topic: str) -> bool:
    """Stop tracking a topic ('stop tracking X'). Matches loosely. Returns True if removed."""
    t = topic.strip().lower()
    topics = read_interests(cfg)
    kept = [x for x in topics if t != x.lower() and t not in x.lower()]
    if len(kept) == len(topics):
        return False
    p = interests_path(cfg)
    p.write_text("# Things to keep an eye on for this person\n\n" + "".join(f"- {x}\n" for x in kept), encoding="utf-8")
    ptr = cfg.root / "sylph_ptr.txt"
    if ptr.exists():
        ptr.write_text("0", encoding="utf-8")
    return True


# --- Phase 5: propose new interests from what the agent already knows ---

def suggest_interests(cfg, limit: int = 8) -> list[str]:
    """Candidate watch-topics derived from the vault, distinctive proper-noun-ish
    terms in the person's project/user/reference facts, minus what's already
    tracked. Hints the agent reviews and proposes ('you care about X, track it?')."""
    from genesis_memory import Vault
    if not cfg.vault_dir.exists():
        return []
    tracked = {t.lower() for t in read_interests(cfg)}
    counts: dict[str, int] = {}
    for f in Vault(cfg.vault_dir).iter_facts():
        if f.kind not in ("project", "user", "reference"):
            continue
        for tok in _distinctive_tokens(f.description + " " + (f.body or "")):
            k = tok.strip()
            if len(k) >= 4:
                counts[k] = counts.get(k, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out = [k for k, _ in ranked if k.lower() not in tracked and not any(k.lower() in t for t in tracked)]
    return out[:limit]


# --- Phase 4: close the loop to behavior ---

def promote_finding(cfg, finding_path) -> str:
    """Turn a valued finding into a durable `reference` fact so it loads at boot and
    actually shapes future turns. This is the collection -> memory -> changed-practice
    hop: the difference between the agent 'knowing more' and being 'better'."""
    from genesis_memory import Fact, Vault
    p = Path(finding_path)
    if not p.is_file():
        # allow passing a slug/name instead of a full path
        cand = list(cfg.findings_dir.glob(f"*{Path(finding_path).stem}*.md")) if cfg.findings_dir.is_dir() else []
        if not cand:
            raise SylphError(f"no finding found for {finding_path!r}")
        p = cand[0]
    body = p.read_text(encoding="utf-8")
    m = re.search(r"\*\*Finding:\*\*\s*(.+)", body)
    desc = " ".join((m.group(1).strip() if m else p.stem).split())[:180]
    fid = ("sylph-" + _slug(re.sub(r"^\d{4}-\d{2}-\d{2}-", "", p.stem)))[:58]
    Vault(cfg.vault_dir).write(Fact(id=fid, kind="reference", description=desc, body=body))
    return fid


def run_cycle(cfg, topic: str | None = None) -> dict | None:
    """One Sylph cycle: pick a thread, research it for real, VERIFY the cited source
    resolves, then write the finding. Returns {topic, path, finding, source, why,
    verified} or None (no topics, honest no-find, or the source failed the trust gate)."""
    topic = topic or _next_topic(cfg, read_interests(cfg))
    if not topic:
        return None
    raw = _research(topic, cwd=cfg.root, token=oauth_token(cfg))
    if not raw or raw.strip().upper() == "NONE":
        _log(cfg, f"no-find: {topic}")
        return None
    finding, source, why = _parse(raw)
    verified = verify_finding(finding, source)
    if not verified["resolves"]:
        # Trust gate: a finding without a real, resolving source is noise. Drop it.
        _log(cfg, f"rejected: {topic} -> {verified['reason']} ({source!r})")
        return None
    path = write_finding(cfg, topic, raw, verified=verified)
    return {"topic": topic, "path": path, "finding": finding or raw, "source": source,
            "why": why, "verified": verified}
