"""Not "is it stored" but "can it be found". Those are different questions and
only one of them is usually measured.

The thesis, from measuring a real store rather than theorizing about one: I do
not have a memory problem, I have a reachability problem. Three findings, each
independent, each invisible to a storage-shaped metric:

  * The documents that DEFINE behavior were the ones too long to be recalled by
    meaning. Around 18KB each against an embedder that cut at 2048 tokens, so
    roughly 60% of each was reachable only by exact keyword. Length inverted
    the author's intent: the more carefully something was written, the less
    findable it became.
  * 83 orphans, 28% of the store, that nothing linked to and nothing retrieved.
  * An always-loaded index selected by mtime, until a bulk pass flattened every
    mtime and the cap silently collapsed to the last N filenames alphabetically.
    A personality-defining memory can be dropped by an alphabet.

Every local-first framework of this shape will grow an always-loaded index with
a hard budget and, sooner or later, a semantic layer with a chunk cap. Storage
grows. Retrieval silently does not. So retrieval gets instrumented here, and the
numbers are reported per document rather than as one average, because an average
over a store where the important documents are the unreachable ones reads fine.

This module measures and never gates. A reachability score is a judgment call
about writing, and a build that fails on one teaches people to write for the
metric. The one exception is a hard budget overflow, which is not a judgment.
"""

from __future__ import annotations

from .graph import Graph

# A rough tokens-per-character ratio. Deliberately crude and deliberately named
# as an ESTIMATE everywhere it surfaces: this package ships no tokenizer and
# will not pretend to one. It is right within a factor that matters for "is this
# document three times the window", which is the question being asked.
CHARS_PER_TOKEN = 4

# Where a semantic layer would cut. Genesis ships no embedder, so this is the
# window a HOST would bring, defaulted to the one that was actually measured
# doing the damage. Configurable because a bigger window is the other real fix.
DEFAULT_CHUNK_TOKENS = 2048

# A description this short cannot carry a retrieval trigger, whatever it says.
MIN_USEFUL_DESC = 40


def est_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def orphans(facts) -> list:
    """Facts that nothing links to and that link to nothing.

    An orphan is not necessarily wrong. It IS necessarily reachable by keyword
    only, so a store that is mostly orphans has a retrieval layer doing far less
    than its size suggests.
    """
    g = Graph(facts)
    out = []
    for fid in g.facts:
        fwd, rev = g.neighbors(fid)
        if not fwd and not rev:
            out.append(fid)
    return sorted(out)


def chunk_coverage(fact, chunk_tokens: int = DEFAULT_CHUNK_TOKENS) -> dict:
    """How much of one document a semantic layer with this window could see."""
    body = fact.body or ""
    total = est_tokens(body)
    reachable = min(total, chunk_tokens)
    return {
        "id": fact.id,
        "est_tokens": total,
        "chunk_tokens": chunk_tokens,
        "reachable_pct": round(100.0 * reachable / total, 1) if total else 100.0,
        "over_window": total > chunk_tokens,
    }


def description_quality(fact) -> list:
    """Reasons this description will not do its job at retrieval time.

    A description is not a summary of the document, it is the text a search
    matches against. "The design plan, approved in June" is a true summary and a
    useless trigger: it cannot surface the document for anyone searching for
    what the document is actually needed for. This checks only what can be
    checked without judgment.
    """
    d = (fact.description or "").strip()
    problems = []
    if not d:
        problems.append("no description at all, so nothing but the id is searchable")
        return problems
    if len(d) < MIN_USEFUL_DESC:
        problems.append(f"only {len(d)} characters, too thin to carry a retrieval trigger")
    slug_words = set(fact.id.replace("_", "-").split("-"))
    desc_words = {w.strip(".,:;\"'").lower() for w in d.split()}
    if slug_words and slug_words <= desc_words and len(desc_words) <= len(slug_words) + 2:
        problems.append("restates the id and adds nothing a searcher would type")
    return problems


def report(facts, *, chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
           max_bytes: int = None, unreadable=None) -> dict:
    """Every reachability metric, per document where per document matters.

    `unreadable` carries files the vault could not parse. They belong here rather
    than in an error log: a fact nobody can parse is the most unreachable a fact
    can be, and it is invisible to every other metric in this report because it
    never became a fact at all.
    """
    from . import index as index_mod

    facts = list(facts)
    max_bytes = index_mod.DEFAULT_MAX_BYTES if max_bytes is None else max_bytes

    orph = orphans(facts)
    coverage = [chunk_coverage(f, chunk_tokens) for f in facts]
    over = [c for c in coverage if c["over_window"]]

    thin = []
    for f in facts:
        problems = description_quality(f)
        if problems:
            thin.append({"id": f.id, "problems": problems})

    text, shrunk = index_mod.enforce_budget(facts, max_bytes)
    used = len(text.encode("utf-8"))
    # enforce_budget never DROPS an entry, which is the important guarantee. But
    # when every description has been clipped to the floor and it still does not
    # fit, it returns text over the cap. Nothing downstream refuses that, so the
    # overflow has to be named here or it is a silent one.
    kept = {}
    for f in facts:
        full = len(f.description or "")
        line = next((ln for ln in text.splitlines() if f"({f.kind}/{f.id}.md)" in ln), "")
        shown = len(line)
        kept[f.id] = round(100.0 * min(shown, full) / full, 1) if full else 100.0

    clipped = sorted((fid for fid, pct in kept.items() if pct < 100.0))

    return {
        "facts": len(facts),
        "unreadable": list(unreadable or []),
        "orphans": orph,
        "orphan_pct": round(100.0 * len(orph) / len(facts), 1) if facts else 0.0,
        "index_bytes": used,
        "index_budget": max_bytes,
        "index_over_budget": used > max_bytes,
        "index_shrunk": shrunk,
        "clipped_descriptions": clipped,
        "over_window": over,
        "thin_descriptions": thin,
        "chunk_tokens": chunk_tokens,
    }


def render(r: dict) -> str:
    lines = [
        f"reachability over {r['facts']} facts "
        f"(can they be FOUND, which is not the same as stored):",
        "",
    ]
    if r.get("unreadable"):
        lines.append(
            f"  UNREADABLE:   {len(r['unreadable'])} file(s) the vault could not parse. "
            "These are not in any count below, because they never became facts:"
        )
        lines += [f"                {u}" for u in r["unreadable"]]
        lines.append("")
    lines += [
        f"  orphans:      {len(r['orphans'])} ({r['orphan_pct']}%) linked by nothing, "
        f"reachable by exact keyword only",
        f"  loaded index: {r['index_bytes']}/{r['index_budget']} bytes"
        + ("  OVER BUDGET" if r["index_over_budget"] else ""),
    ]
    if r["clipped_descriptions"]:
        lines.append(
            f"                {len(r['clipped_descriptions'])} description(s) clipped to fit; "
            "clipped text is text a search cannot match"
        )
    if r["index_over_budget"]:
        lines.append(
            "                every description is already at the floor and it STILL does not\n"
            "                fit. Nothing was dropped, but something downstream will truncate\n"
            "                this, and whatever it drops will be dropped by position."
        )

    ow = r["over_window"]
    lines.append(
        f"  long docs:    {len(ow)} longer than the {r['chunk_tokens']}-token window a "
        f"semantic layer would use (estimated)"
    )
    for c in sorted(ow, key=lambda c: -c["est_tokens"])[:10]:
        lines.append(
            f"                {c['id']}: ~{c['est_tokens']} tokens, about "
            f"{c['reachable_pct']}% reachable by meaning"
        )
    if ow:
        lines.append(
            "                Length inverts intent here: the more carefully a document is\n"
            "                written, the less of it can be found by meaning. Split it, or\n"
            "                give the part that matters its own fact."
        )

    td = r["thin_descriptions"]
    lines.append(f"  descriptions: {len(td)} that will not do their job at retrieval time")
    for t in td[:10]:
        lines.append(f"                {t['id']}: {t['problems'][0]}")
    if td:
        lines.append(
            "                A description is not a summary of the document, it is the text\n"
            "                a search matches against."
        )
    return "\n".join(lines)


def write_warnings(fact, chunk_tokens: int = DEFAULT_CHUNK_TOKENS) -> list:
    """What to tell an author AT WRITE TIME, while the document is still theirs.

    Chunk-cap awareness where it is cheap. Told at write time this is an edit;
    discovered in a report six weeks later it is an archaeology project, and by
    then the document has been quietly unfindable the whole time.

    Warnings, never refusals. A long fact is legitimate and a write path that
    rejects one would lose the thought entirely, which is a worse outcome than
    a thought that is hard to search for.
    """
    out = []
    cov = chunk_coverage(fact, chunk_tokens)
    if cov["over_window"]:
        out.append(
            f"this is ~{cov['est_tokens']} estimated tokens against a {chunk_tokens}-token "
            f"window, so only about {cov['reachable_pct']}% of it could be found by meaning. "
            "Consider splitting it, or giving the part that matters its own fact."
        )
    for problem in description_quality(fact):
        out.append(f"description: {problem}")
    return out
