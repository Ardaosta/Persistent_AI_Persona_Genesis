"""Do the file paths written inside vault documents actually resolve?

`graph.py` answers this for `[[wikilinks]]`, and it already defeats the
underscore-vs-hyphen drift that link syntax suffers. Bare FILE PATHS get no such
check, and that is where a real deployment died: an authored persona doc pointed
at `relationship_questions.md` while the vault had slugged the file to
`relationship-questions.md`. Every read of that path was a file-not-found, the
code swallowed it, and a get-to-know-you drip stayed silently dead for five days.
Nobody could have diagnosed it without reading source.

A dangling path is worse than a dangling wikilink, because a wikilink is a note
to a future writer and a path is an instruction to running code. So this module
is deliberately blunt: find every path-shaped reference in the vault, resolve it,
and classify what fails.

  missing  the referenced file is nowhere in the vault
  drift    a file exists under a differently-normalized name, almost certainly
           the intended target (the five-day case)

Engine-free and dependency-free, like everything else here. The whole point is
that it runs at seed time on a machine with no key yet.
"""

from __future__ import annotations

import re
from pathlib import Path

# Extensions worth resolving: the ones a persona doc, a seed, or a loop actually
# points at. Deliberately not "any dotted token", which would drag in prose like
# "config.json-ish" and version numbers and drown the signal.
CHECKED_SUFFIXES = (".md", ".json", ".jsonl", ".txt", ".yaml", ".yml")

# Where documents live that we scan. Everything under the vault.
_SCAN_SUFFIXES = (".md", ".json", ".jsonl")

# A path-shaped token: optional directory segments, then a name with a checked
# extension. Anchored on characters a path may contain, so prose around it does
# not bleed in.
#
# The leading lookbehind is doing more work than it looks like: it is also what
# excludes URLs. In `https://example.com/notes.md` the `notes.md` is preceded by
# `/`, so the match is refused and no separate url-skip list is needed. Stated
# out loud because the obvious defensive helper here would be unreachable code,
# and unreachable code that a comment claims is guarding something is worse than
# no guard at all. test_filerefs locks this behavior in.
_REF = re.compile(
    r"(?<![\w./-])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.(?:md|json|jsonl|txt|yaml|yml))\b"
)


def _norm_name(name: str) -> str:
    """Canonicalize a filename for drift comparison: lowercase, fold spaces and
    underscores to hyphens, collapse repeats. The extension is kept, because a
    `.md` pointing at a `.json` is a genuine miss and not drift.

    This is the same fold `graph._norm` applies to slugs. Applying it to file
    paths too is the entire fix: `relationship_questions.md` and
    `relationship-questions.md` become one key.
    """
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = re.sub(r"[\s_]+", "-", stem.strip().lower())
    stem = re.sub(r"-+", "-", stem).strip("-")
    return f"{stem}.{ext.lower()}" if ext else stem


def iter_docs(vault_dir: Path):
    """Every document in the vault worth scanning for references."""
    vault_dir = Path(vault_dir)
    if not vault_dir.is_dir():
        return
    for p in sorted(vault_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in _SCAN_SUFFIXES:
            yield p


def _index_vault(vault_dir: Path):
    """(exact relative paths, normalized-name -> relative path) for the vault."""
    vault_dir = Path(vault_dir)
    exact = set()
    by_norm = {}
    if not vault_dir.is_dir():
        return exact, by_norm
    for p in vault_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(vault_dir)
        exact.add(rel.as_posix())
        by_norm.setdefault(_norm_name(p.name), rel.as_posix())
    return exact, by_norm


def lint(vault_dir: Path) -> dict:
    """Resolve every path-shaped reference in the vault.

    Returns {"checked": n, "docs": n, "missing": [...], "drift": [...]}, where
    each finding is {"doc", "ref", "suggestion"} and `suggestion` is set only for
    drift. Sorted for stable output, because a report that reorders itself between
    runs cannot be diffed.
    """
    vault_dir = Path(vault_dir)
    exact, by_norm = _index_vault(vault_dir)
    missing, drift = [], []
    checked = 0
    docs = 0

    for doc in iter_docs(vault_dir):
        docs += 1
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        doc_rel = doc.relative_to(vault_dir)
        doc_dir = doc_rel.parent
        seen_in_doc = set()
        for ref in _REF.findall(text):
            if ref in seen_in_doc:
                continue
            seen_in_doc.add(ref)
            checked += 1

            # A reference resolves relative to its own document first, then to the
            # vault root. Both are things an author plausibly means.
            candidates = [(doc_dir / ref).as_posix().lstrip("./"), ref]
            if any(c in exact for c in candidates):
                continue

            # Not found as written. Is a differently-normalized file sitting there?
            hit = by_norm.get(_norm_name(Path(ref).name))
            entry = {"doc": doc_rel.as_posix(), "ref": ref, "suggestion": hit}
            (drift if hit else missing).append(entry)

    key = lambda e: (e["doc"], e["ref"])  # noqa: E731 - a sort key, not a function
    missing.sort(key=key)
    drift.sort(key=key)
    return {"checked": checked, "docs": docs, "missing": missing, "drift": drift}


def render(result: dict) -> str:
    """Plain language, because the person reading it may not be a developer."""
    n_bad = len(result["missing"]) + len(result["drift"])
    head = (
        f"file references: {result['checked']} checked across {result['docs']} documents, "
        f"{n_bad} broken ({len(result['drift'])} misspelled, {len(result['missing'])} missing)"
    )
    if not n_bad:
        return head
    out = [head]
    if result["drift"]:
        out.append("\nwrong name (the file is there under a different spelling):")
        for e in result["drift"]:
            out.append(f"  {e['doc']} points at {e['ref']}, but the file is {e['suggestion']}")
    if result["missing"]:
        out.append("\nnot found (nothing in the vault answers to this):")
        for e in result["missing"]:
            out.append(f"  {e['doc']} points at {e['ref']}")
    out.append(
        "\nCode that reads one of these gets a file-not-found and, if it swallows the\n"
        "error, goes quiet instead of breaking. That is how a five-day silence starts."
    )
    return "\n".join(out)
