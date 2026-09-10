"""The drift-proof matcher: which cluster(s) does a signal touch?

We match on WHAT A SESSION IS DOING — its prompt text and cwd — never on a
canonical project name, because names drift (one system goes by many names over
its life). Each cluster declares a fat `aliases` net and real `paths`; a signal
blob that contains any alias as a whole word, or a cwd/path fragment under any
declared path, surfaces that cluster.

Matching semantics are kept identical to the aimee-core reference resolver so a
cluster doc is portable between the two stores:

  * **alias hit** — whole-word-ish substring of an alias in the (lowercased)
    signal. "voice" matches "fix the voice loop" but not "invoice".
  * **path hit** — a declared path appears as a plain substring of the signal
    (the signal carries the cwd, so a session working under the path matches even
    if it never names the system).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import frontmatter, store


@dataclass
class Hit:
    slug: str          # cluster slug (the doc filename stem) — the dedup key
    body: str          # the headline text to surface (frontmatter stripped)
    path: Path         # the source doc


def _alias_hit(sig: str, aliases: List[str]) -> bool:
    return any(
        re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", sig)
        for a in aliases
    )


def resolve(signal: str, dir: Optional[str] = None) -> List[Hit]:
    """Return the clusters this signal touches, sorted by slug (stable order)."""
    sig = signal.lower()
    hits: List[Hit] = []
    for f in store.cluster_paths(dir):
        meta, body = frontmatter.parse(f.read_text(encoding="utf-8"))
        aliases = [a.lower() for a in meta.get("aliases", []) if a]
        paths = [p.lower() for p in meta.get("paths", []) if p]
        if _alias_hit(sig, aliases) or any(p in sig for p in paths):
            hits.append(Hit(slug=f.stem, body=body.strip(), path=f))
    return hits
