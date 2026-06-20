"""A tiny, dependency-free, tolerant frontmatter reader/writer.

Deliberately not a full YAML parser: the vault is human-editable and a heavyweight
YAML dependency is the wrong call for a single-purpose file. Scalars are parsed as
`key: value`; any frontmatter line without a colon is *preserved* (under `_raw`)
rather than dropped. When in doubt, preserve.
"""

from __future__ import annotations

_DELIM = "---"

# frontmatter keys we render first, in this order
_ORDER = ["id", "description", "kind", "status", "created", "updated"]


def parse(text: str) -> tuple[dict, str]:
    """Return (meta, body). No frontmatter block -> ({}, text)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _DELIM:
        return {}, text

    meta: dict = {}
    raw: list[str] = []
    body_start: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            body_start = i + 1
            break
        line = lines[i]
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
        elif line.strip():
            raw.append(line)

    if body_start is None:  # no closing delimiter -> tolerant: treat all as body
        return {}, text

    if raw:
        meta["_raw"] = raw
    body = "\n".join(lines[body_start:]).lstrip("\n")
    return meta, body


def _scalar(value) -> str:
    """Frontmatter values are single-line scalars. Fold any newline/whitespace run
    to a single space so a multi-line value can never orphan into a bare,
    colon-less line that the parser would mis-read or drop. Lossless for a real
    one-line value; the multi-line BODY is unaffected (it lives below the fence)."""
    return " ".join(str(value).split())


def serialize(meta: dict, body: str) -> str:
    out = [_DELIM]
    seen: set[str] = set()
    for k in _ORDER:
        if meta.get(k) is not None:
            out.append(f"{k}: {_scalar(meta[k])}")
            seen.add(k)
    for k, v in meta.items():
        if k in seen or k == "_raw" or v is None:
            continue
        out.append(f"{k}: {_scalar(v)}")
    for raw_line in meta.get("_raw", []):
        out.append(raw_line)
    out.append(_DELIM)
    out.append("")
    out.append(body.rstrip("\n"))
    out.append("")
    return "\n".join(out)
