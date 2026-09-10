"""Scaffold a new HEADLINES cluster — the init function for a new project.

Any system a session might touch cold should get a cluster: a short, curated list
of the load-bearing "huge things" that a task-focused session must not overlook.
This writes a well-formed cluster doc (frontmatter alias/path net + headline
scaffold + the maintenance rule) so starting one is a one-liner, not a blank page.

Cluster on the real SYSTEM, not a name (names drift). Give a FAT alias net (every
name the thing goes by) and real file paths/dirs — that's how sessions match it
drift-proof. Refuses to overwrite an existing cluster.

The scaffold ships structure only — no content, no persona. Empty prompts
("Replace this.") are the correct day-0 state; a companion fills them from its own
lived record.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .store import headlines_dir

TEMPLATE = """---
cluster: {slug}
# Match on ANY of these — names drift, so cast a wide net. A session that touches
# these paths, edits these files, or mentions these aliases surfaces this set.
# Add drifted names to `aliases` freely; it's a cheap append.
aliases:
{aliases}
paths:
{paths}
updated: {today}
---

# HEADLINES — {title}

_The load-bearing frame. Read this BEFORE acting on anything in this cluster.
These are the "huge things" a task-focused session would otherwise miss._

1. **<the single most important thing a cold session must know>** — e.g. what
   supersedes what, the strategic direction, the one fact whose absence causes
   the wrong work. Replace this.

2. **<major structural fact>** — e.g. "X moved to a new home", "the canonical
   store is now Y, not Z". Replace this.

3. **<hard constraint / gotcha>** — the thing that bites if unknown. Replace this.

---
_Maintenance: when something load-bearing changes here (a component supersedes
another, a path moves, a strategic call is made), UPDATE this file as PART of
that work — a stale headline lies with authority. Add drifted names to `aliases`._
"""


def slugify(s: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    if not out:
        raise ValueError("cluster slug is empty after normalization")
    return out


def new_cluster(
    slug: str,
    *,
    aliases: Optional[List[str]] = None,
    paths: Optional[List[str]] = None,
    title: Optional[str] = None,
    today: str = "",
    dir: Optional[str] = None,
) -> Path:
    """Write a scaffold cluster doc and return its path. Refuses to overwrite.

    `today` is passed in (not read from the clock) so callers stay deterministic
    and testable; the CLI fills it with the real date.
    """
    slug = slugify(slug)
    d = headlines_dir(dir)
    dest = d / f"{slug}.md"
    if dest.exists():
        raise FileExistsError(f"{dest} already exists (edit it, don't re-init)")

    aliases = aliases or [slug]
    paths = paths or ["<add real dir/file paths>"]
    d.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        TEMPLATE.format(
            slug=slug,
            aliases="\n".join(f"  - {x}" for x in aliases),
            paths="\n".join(f'  - "{x}"' for x in paths),
            today=today,
            title=title or slug.replace("-", " ").title(),
        ),
        encoding="utf-8",
    )
    return dest
