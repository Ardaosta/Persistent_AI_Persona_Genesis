"""Cheap YAML-ish frontmatter parse for cluster docs — lists only.

This is deliberately kept semantically identical to the aimee-core reference
resolver's `_front`, so a cluster doc is portable between the two stores without
translation (the format is SHARED; changing it would need coordination with the
aimee-core owner). We only need list-valued keys (`aliases`, `paths`) and the
body, so we do not pull in a YAML dependency — Genesis packages stay
zero-dependency.

Supported shapes:

    aliases: [voice, "voice for aimee", presence]     # inline list
    paths:
      - "repos/A Voice for Someone"                      # dash list
      - "aimee-core/portal"
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


def parse(text: str) -> Tuple[Dict[str, List[str]], str]:
    """Return (meta, body). `meta` maps each key to a list of strings.

    A doc with no frontmatter fences returns ({}, text). Scalar-valued keys land
    as an empty list (we only consume list keys), which is harmless.
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: Dict[str, List[str]] = {}
    body = parts[2]
    cur = None
    for line in parts[1].splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m and not line.startswith(" ") and not line.startswith("-"):
            cur = m.group(1)
            inline = m.group(2).strip()
            if inline.startswith("[") and inline.endswith("]"):
                meta[cur] = [
                    x.strip().strip('"').strip("'")
                    for x in inline[1:-1].split(",")
                    if x.strip()
                ]
            else:
                meta[cur] = []
        elif cur and re.match(r"^\s*-\s+", line):
            meta.setdefault(cur, []).append(
                re.sub(r"^\s*-\s+", "", line).strip().strip('"').strip("'")
            )
    return meta, body


def scalar(text: str, key: str) -> Optional[str]:
    """Read a SCALAR frontmatter value (e.g. `updated: 2026-07-06`, `cluster: voice`).

    `parse()` deliberately keeps only list-valued keys (aliases/paths) and collapses
    scalars to []. The freshness discipline (see docs/HEADLINES.md) needs the `updated:`
    and `cluster:` scalars, so read them straight off the frontmatter block. This is a
    READ helper only — it does not change the shared cluster-doc format. Returns None
    when the key is absent or the doc has no frontmatter fence.
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    for line in parts[1].splitlines():
        m = re.match(rf"^{re.escape(key)}:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None
