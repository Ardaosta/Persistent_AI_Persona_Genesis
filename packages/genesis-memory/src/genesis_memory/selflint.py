"""Does a document obey the rules it itself declares?

An em-dash was authored into the TITLE of an operating manual whose own text
says not to use em-dashes. Nobody caught it, because nothing was looking: the
rule lived in prose, addressed to a reader, and prose does not execute.

That is the general shape worth catching. A persona document is the one file in
a vault that states, in plain language, how its subject writes. Those statements
are machine-checkable against the very document that makes them, and a file that
breaks its own stated rule on line one is going to be read, by the AI booting
from it, as permission.

Two passes here, and they answer different questions:

  declared rules  the document says "no X" and then contains X
  encoding        the document contains characters that will not survive the
                  trip to a Windows console, where they arrive as mojibake

The second is not a style opinion. The em-dash above was FOUND because it turned
into garbage on a Windows box, so the encoding pass is the one that surfaced the
rule violation in the first place.

Deliberately narrow: it only knows rules it can check without judgment. A lint
that guesses at intent produces findings an author cannot act on, and a finding
nobody can act on trains people to skip the report.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

EM_DASH = "—"

# A rule counts as DECLARED only when the document says so plainly. The hedge is
# deliberate: inferring a rule from tone would produce findings the author never
# agreed to, and this lint is only useful if every finding is one they asked for.
_DECLARES = {
    "em-dash": re.compile(
        r"\b(?:no|never\s+use|never|avoid|don'?t\s+use|do\s+not\s+use)\b[^.\n]{0,40}"
        r"\bem[\s-]?dash(?:es)?\b", re.I),
    "emoji": re.compile(
        r"\b(?:no|never\s+use|never|avoid|don'?t\s+use|do\s+not\s+use)\b[^.\n]{0,40}"
        r"\bemoji(?:s)?\b", re.I),
    "exclamation": re.compile(
        r"\b(?:no|never\s+use|never|avoid|don'?t\s+use|do\s+not\s+use)\b[^.\n]{0,40}"
        r"\bexclamation\s*(?:point|mark)s?\b", re.I),
}

# `never use the word "x"` / `never say "x"`. Quotes are REQUIRED, because an
# unquoted version cannot be told apart from ordinary prose about words.
_DECLARES_WORD = re.compile(
    r"\bnever\s+(?:use|say)\s+(?:the\s+word\s+)?[\"“]([^\"”]{1,40})[\"”]", re.I)

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⬀-⯿]")

_FENCE = re.compile(r"^\s*```")


def _prose_lines(text: str):
    """(line_number, line) for prose only, skipping fenced code.

    Code is exempt from prose rules. An exclamation mark in a shell snippet is
    not a tone violation, and a lint that says it is gets switched off.
    """
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield i, line


def _declaring_lines(text: str) -> set:
    """Line numbers that DECLARE a rule, exempted from that rule's own check.

    Quote-awareness, and it is load-bearing rather than a nicety. A rule is very
    often written with its own violation as the example, `no em-dashes (—)`, and
    a checker that cannot tell the statement of a rule from a breach of it
    reports the rulebook as the offender. That has happened here before, to a
    blocking guard, and the result was a guard people learned to route around.
    """
    lines = set()
    for n, line in _prose_lines(text):
        if any(p.search(line) for p in _DECLARES.values()) or _DECLARES_WORD.search(line):
            lines.add(n)
    return lines


def declared_rules(text: str) -> dict:
    """Which checkable rules does this document declare about itself?"""
    found = {name: bool(pat.search(text)) for name, pat in _DECLARES.items()}
    rules = {k for k, v in found.items() if v}
    words = {m.group(1).strip().lower() for m in _DECLARES_WORD.finditer(text)}
    return {"rules": sorted(rules), "banned_words": sorted(w for w in words if w)}


def _violations_for(rule: str, text: str, exempt: set) -> list:
    out = []
    for n, line in _prose_lines(text):
        if n in exempt:
            continue
        if rule == "em-dash" and EM_DASH in line:
            out.append((n, line.strip(), f"contains {EM_DASH!r}"))
        elif rule == "emoji":
            m = _EMOJI.search(line)
            if m:
                out.append((n, line.strip(), f"contains the emoji {m.group(0)!r}"))
        elif rule == "exclamation" and "!" in line:
            out.append((n, line.strip(), "contains '!'"))
    return out


def _word_violations(word: str, text: str, exempt: set) -> list:
    pat = re.compile(r"\b" + re.escape(word) + r"\b", re.I)
    return [
        (n, line.strip(), f"uses the banned word {word!r}")
        for n, line in _prose_lines(text)
        if n not in exempt and pat.search(line)
    ]


def non_ascii(text: str) -> list:
    """Characters that arrive as mojibake on a Windows console.

    Reported, never fatal on its own: a vault may legitimately hold other
    languages, and refusing those would be a worse bug than the one this catches.
    """
    out = []
    seen = set()
    for n, line in enumerate(text.splitlines(), 1):
        for ch in line:
            if ord(ch) > 127 and ch not in seen:
                seen.add(ch)
                try:
                    name = unicodedata.name(ch)
                except ValueError:
                    name = "unnamed"
                out.append((n, ch, name))
    return out


def lint_text(text: str) -> dict:
    """Check one document against the rules it declares about itself."""
    declared = declared_rules(text)
    exempt = _declaring_lines(text)
    violations = []
    for rule in declared["rules"]:
        for n, line, why in _violations_for(rule, text, exempt):
            violations.append({"rule": rule, "line": n, "text": line[:120], "why": why})
    for word in declared["banned_words"]:
        for n, line, why in _word_violations(word, text, exempt):
            violations.append({"rule": f"word:{word}", "line": n, "text": line[:120], "why": why})
    violations.sort(key=lambda v: (v["line"], v["rule"]))
    return {
        "declared": declared["rules"] + [f"word:{w}" for w in declared["banned_words"]],
        "violations": violations,
        "non_ascii": non_ascii(text),
    }


def lint_vault(vault_dir: Path) -> dict:
    """Every markdown document in the vault, checked against its own rules."""
    vault_dir = Path(vault_dir)
    docs, violations, encoding = 0, [], []
    if vault_dir.is_dir():
        for p in sorted(vault_dir.rglob("*.md")):
            if not p.is_file():
                continue
            docs += 1
            rel = p.relative_to(vault_dir).as_posix()
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                encoding.append({"doc": rel, "char": "", "name": f"unreadable as utf-8: {e}", "line": 0})
                continue
            r = lint_text(text)
            for v in r["violations"]:
                violations.append(dict(v, doc=rel))
            for n, ch, name in r["non_ascii"]:
                encoding.append({"doc": rel, "line": n, "char": ch, "name": name})
    return {"docs": docs, "violations": violations, "non_ascii": encoding}


def render(result: dict) -> str:
    v = result["violations"]
    head = f"self-consistency: {result['docs']} documents, {len(v)} broke a rule they declare"
    out = [head]
    if v:
        out.append("")
        for e in v:
            rule = e["rule"]
            says = (f"bans the word {rule[5:]!r}" if rule.startswith("word:")
                    else f"declares no {rule}")
            out.append(f"  {e['doc']}:{e['line']} {says}, and {e['why']}")
            out.append(f"      {e['text']}")
        out.append(
            "\nA document that breaks its own stated rule on the page reads, to the AI\n"
            "booting from it, as permission. Fix the document, or drop the rule."
        )
    na = result["non_ascii"]
    if na:
        chars = sorted({e["char"] for e in na if e["char"]})
        out.append(
            f"\nencoding: {len(chars)} non-ASCII character(s) present. On a Windows console "
            f"these arrive as mojibake: {' '.join(repr(c) for c in chars[:12])}"
        )
    return "\n".join(out)
