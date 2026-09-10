"""The context-graph view over the vault: the [[wikilinks]] facts carry between
each other, made queryable.

This is not a second store and not a vector index. It is the *implicit* graph
the companion already writes by hand — `[[other-fact]]` references in fact
bodies — read back as nodes and edges so two questions become answerable that a
flat per-fact index answers poorly:

  1. JOIN — "what connects fact A and fact B?" (graph traversal, not similarity).
  2. HYGIENE — "which links point at a fact that doesn't exist, or drifted to a
     different slug?" The auto-heal signal: a link graph rots quietly, and a
     rotted graph degrades retrieval before anyone notices.

Engine-free by construction, like the rest of this package. Keyword resolution
(query -> fact id) is built in and deterministic. The harder, fuzzier resolution
the article calls out as needing a model is injected as an optional `resolver`
callable; genesis-memory ships none, so a model-less or sleeping host loses a
nicety, never the graph. An engine pack or app supplies the resolver.
"""

from __future__ import annotations

import re
from collections import Counter, deque

from .vault import Vault

_LINK = re.compile(r"\[\[([^\]]+)\]\]")

# generic English stop-words + the scaffolding words that show up in a spoken
# "the rule about ..." query and would otherwise score spurious matches.
_STOP = frozenset(
    "a an the that this about to of for in on at is it as be and or with when "
    "whenever if how me my i you your rule not no thing things which what where "
    "dont into over via he she him her his".split()
)


def _norm(s: str) -> str:
    """Canonicalize a slug/link into one comparable key: lowercase, fold spaces
    and underscores to hyphens, drop anything else. Defeats the
    underscore-vs-hyphen / casing drift between how a link is typed and how a
    fact id is stored."""
    s = s.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    return re.sub(r"-+", "-", s).strip("-")


def _toks(s: str) -> set[str]:
    """Whole tokens, not substrings — so 'go' can't match 'gotchas'."""
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t}


class Graph:
    """A context graph built from a set of Facts. Undirected for traversal,
    edges remembered directionally for display."""

    # keyword is trusted only on a strong (id/description) hit; a weak match
    # defers to the injected resolver when one is available.
    KEYWORD_TRUST = 3

    def __init__(self, facts):
        self.facts = {f.id: f for f in facts}
        self._alias: dict[str, str] = {}
        for fid in self.facts:
            self._alias[_norm(fid)] = fid
        self.edges: dict[str, list[str]] = {fid: [] for fid in self.facts}
        self.dangling: list[tuple[str, str]] = []
        for fid, fact in self.facts.items():
            for raw in _LINK.findall(fact.body):
                tgt = self._alias.get(_norm(raw))
                if tgt:
                    self.edges[fid].append(tgt)
                else:
                    self.dangling.append((fid, _norm(raw)))

    @classmethod
    def from_vault(cls, vault: Vault) -> "Graph":
        return cls(vault.iter_facts())

    # ── traversal ────────────────────────────────────────────────────────────
    def neighbors(self, fid: str) -> tuple[list[str], list[str]]:
        """(outgoing, incoming) fact ids."""
        fwd = list(self.edges.get(fid, []))
        rev = [s for s in self.facts if fid in self.edges.get(s, [])]
        return fwd, rev

    def _adjacency(self) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = {fid: set() for fid in self.facts}
        for s, tgts in self.edges.items():
            for t in tgts:
                adj[s].add(t)
                adj.setdefault(t, set()).add(s)
        return adj

    def path(self, a: str, b: str, max_hops: int = 4) -> list[str] | None:
        """Shortest undirected link path a..b — the join query. None if the two
        facts are not connected within max_hops."""
        if a not in self.facts or b not in self.facts:
            return None
        if a == b:
            return [a]
        adj = self._adjacency()
        seen = {a}
        q: deque[list[str]] = deque([[a]])
        while q:
            p = q.popleft()
            if len(p) - 1 >= max_hops:
                continue
            for nxt in adj.get(p[-1], ()):
                if nxt in seen:
                    continue
                if nxt == b:
                    return p + [nxt]
                seen.add(nxt)
                q.append(p + [nxt])
        return None

    # ── resolution ───────────────────────────────────────────────────────────
    def find_scored(self, query: str) -> list[tuple[int, str]]:
        """Rank facts by whole-token query overlap on id (x3) and description
        (x1), stop-words and <3-char tokens dropped. Sorted desc."""
        terms = [t for t in _toks(query) if t not in _STOP and len(t) >= 3]
        scored = []
        for fid, fact in self.facts.items():
            itok = _toks(fid)
            dtok = _toks(fact.description)
            score = sum(3 * (t in itok) + (t in dtok) for t in terms)
            if score:
                scored.append((score, fid))
        scored.sort(reverse=True)
        return scored

    def find(self, query: str, limit: int = 5) -> list[str]:
        return [fid for _, fid in self.find_scored(query)[:limit]]

    def best(self, query: str, resolver=None) -> tuple[str | None, str]:
        """Resolve a fuzzy query to one fact id. Confident keyword first (fast,
        deterministic); on a weak/no keyword hit, defer to `resolver` if given.

        `resolver(query, candidates) -> fact_id | None`, where candidates is a
        list of (id, description). Returns (fact_id_or_None, how) with how in
        {keyword, resolver, keyword-weak, miss}.
        """
        scored = self.find_scored(query)
        top = scored[0] if scored else (0, None)
        if top[0] >= self.KEYWORD_TRUST:
            return top[1], "keyword"
        if resolver is not None:
            cands = [(fid, self.facts[fid].description) for fid in self.facts]
            try:
                got = resolver(query, cands)
            except Exception:
                got = None
            if got in self.facts:
                return got, "resolver"
            if got:
                norm_hit = self._alias.get(_norm(got))
                if norm_hit:
                    return norm_hit, "resolver"
        return (top[1], "keyword-weak") if top[1] else (None, "miss")

    def join(self, query_a: str, query_b: str, resolver=None):
        """Resolve both ends then traverse. Returns dict with a, b, how_a, how_b,
        and path (list of ids) or None."""
        a, how_a = self.best(query_a, resolver)
        b, how_b = self.best(query_b, resolver)
        path = self.path(a, b) if (a and b) else None
        return {"a": a, "b": b, "how_a": how_a, "how_b": how_b, "path": path}

    # ── hygiene / auto-heal ────────────────────────────────────────────────────
    def lint(self) -> dict:
        """Classify dangling links into genuine write-me markers vs name-drift.

        A dangling target is *drift* (the fact probably exists under a slightly
        different id) when some existing id shares >=2 tokens with it or contains
        it; otherwise it is *missing* — a link to a fact that was never written.
        The residual the token classifier can't place is exactly what an injected
        resolver would settle; this stays string-only and free.
        """
        counts = Counter(t for _, t in self.dangling)
        ids = list(self.facts)
        missing, drift = [], []
        for tgt, n in counts.items():
            ttok = set(tgt.split("-"))
            tgt_flat = tgt.replace("-", "")
            guess = None
            for fid in ids:
                nfid = _norm(fid)
                # substring, de-hyphenated equality (catches 'ratelimiter' ->
                # 'rate-limiter'), or >=2 shared tokens => probably the same fact
                if (tgt in nfid
                        or tgt_flat == nfid.replace("-", "")
                        or len(ttok & set(nfid.split("-"))) >= 2):
                    guess = fid
                    break
            (drift if guess else missing).append((tgt, n, guess))
        missing.sort(key=lambda x: -x[1])
        drift.sort(key=lambda x: -x[1])
        edges = sum(len(v) for v in self.edges.values())
        return {
            "nodes": len(self.facts),
            "edges": edges,
            "dangling": len(self.dangling),
            "missing": [(t, n) for t, n, _ in missing],
            "drift": drift,
        }

    def render_lint(self) -> str:
        """One-glance hygiene report, mirroring the `genesis status` voice."""
        r = self.lint()
        out = [
            f"nodes {r['nodes']} · edges {r['edges']} · dangling {r['dangling']} "
            f"({len(r['missing'])} missing, {len(r['drift'])} name-drift)"
        ]
        if r["missing"]:
            out.append("\nwrite-me (linked, no such fact):")
            out += [f"  [[{t}]] x{n}" for t, n in r["missing"]]
        if r["drift"]:
            out.append("\nname-drift (link -> differently-slugged fact):")
            out += [f"  [[{t}]] x{n} -> likely {g}" for t, n, g in r["drift"]]
        return "\n".join(out)
