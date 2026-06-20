"""The lean loaded index: one line per fact, the only thing always in context.

The hard-won lesson from the reference build: LLM-side discipline alone fails the
byte budget, so the shrink is a deterministic mechanical guard. The reference's
own index once blew past its cap and got silently truncated at load time, dropping
half the pointers. So `enforce_budget` NEVER drops an entry; it clips the longest
descriptions until the whole index fits (or every entry is at the floor).
"""

from __future__ import annotations

DEFAULT_MAX_BYTES = 24_000
MIN_DESC = 24  # never clip a description shorter than this
_STEP = 8


def _safe_label(text: str) -> str:
    """One-line, link-safe label: fold whitespace and neutralize the brackets
    that would otherwise break the markdown link in the always-loaded index
    (the identity-load layer the model sees every boot)."""
    return " ".join(text.split()).replace("[", "(").replace("]", ")")


def entry_line(fact, desc: str | None = None) -> str:
    d = _safe_label(fact.description if desc is None else desc)
    return f"- [{d}]({fact.kind}/{fact.id}.md) — {fact.kind}"


def build(facts) -> str:
    facts = sorted(facts, key=lambda f: (f.kind, f.id))
    return "\n".join(entry_line(f) for f in facts)


def enforce_budget(facts, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[str, bool]:
    facts = sorted(facts, key=lambda f: (f.kind, f.id))
    orig = {f.id: f.description for f in facts}
    target_len = {f.id: len(f.description) for f in facts}

    def render() -> str:
        lines = []
        for f in facts:
            d = orig[f.id]
            if target_len[f.id] < len(d):
                d = d[: target_len[f.id]].rstrip() + "…"
            lines.append(entry_line(f, d))
        return "\n".join(lines)

    text = render()
    shrunk = False
    while len(text.encode("utf-8")) > max_bytes:
        clippable = [f for f in facts if target_len[f.id] > MIN_DESC]
        if not clippable:
            break  # everything's at the floor; we did our best, dropped nothing
        longest = max(clippable, key=lambda f: target_len[f.id])
        target_len[longest.id] = max(MIN_DESC, target_len[longest.id] - _STEP)
        shrunk = True
        text = render()

    return text, shrunk
