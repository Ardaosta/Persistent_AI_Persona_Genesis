import unittest

from genesis_memory import Fact
from genesis_memory.graph import Graph


def _f(fid, desc, body="", kind="feedback"):
    return Fact(id=fid, kind=kind, description=desc, body=body)


def _sample():
    # auth -> ratelimit -> cache, plus a disconnected fact and a few links that
    # exercise drift (typed under a different slug) and a true write-me marker.
    return [
        _f("auth-module", "the auth module decisions", "depends on [[rate-limiter]]"),
        _f("rate-limiter", "request rate limiting", "shares a store with [[cache-layer]]"),
        _f("cache-layer", "the cache layer", "nothing links out"),
        _f("lonely-fact", "no edges at all", "plain body"),
        # link drops a word: 'ratelimiter' should classify as drift -> rate-limiter
        _f("gateway", "the api gateway", "fronts [[ratelimiter]] and [[billing-service]]"),
    ]


class TestGraphBuild(unittest.TestCase):
    def test_edges_and_dangling(self):
        g = Graph(_sample())
        self.assertEqual(g.edges["auth-module"], ["rate-limiter"])
        # 'billing-service' has no fact -> dangling; 'ratelimiter' too (normalizes
        # to itself, no exact fact) -> dangling, but lint reclassifies it as drift
        dangling_targets = {t for _, t in g.dangling}
        self.assertIn("billing-service", dangling_targets)
        self.assertIn("ratelimiter", dangling_targets)

    def test_underscore_vs_hyphen_link_resolves(self):
        facts = [
            _f("a-fact", "a", "see [[b_fact]]"),   # underscore link
            _f("b-fact", "b", "leaf"),
        ]
        g = Graph(facts)
        self.assertEqual(g.edges["a-fact"], ["b-fact"])
        self.assertEqual(g.dangling, [])


class TestJoin(unittest.TestCase):
    def test_two_hop_path(self):
        g = Graph(_sample())
        self.assertEqual(
            g.path("auth-module", "cache-layer"),
            ["auth-module", "rate-limiter", "cache-layer"],
        )

    def test_no_path_when_disconnected(self):
        g = Graph(_sample())
        self.assertIsNone(g.path("auth-module", "lonely-fact"))

    def test_join_resolves_then_traverses(self):
        g = Graph(_sample())
        r = g.join("auth module", "cache layer")
        self.assertEqual(r["a"], "auth-module")
        self.assertEqual(r["b"], "cache-layer")
        self.assertEqual(r["how_a"], "keyword")
        self.assertEqual(len(r["path"]), 3)


class TestResolution(unittest.TestCase):
    def test_keyword_first_is_confident(self):
        g = Graph(_sample())
        fid, how = g.best("rate limiter")
        self.assertEqual(fid, "rate-limiter")
        self.assertEqual(how, "keyword")

    def test_stopwords_do_not_force_a_match(self):
        # a query of only scaffolding words must not spuriously resolve
        g = Graph(_sample())
        fid, how = g.best("the about to of for")
        self.assertIsNone(fid)
        self.assertEqual(how, "miss")

    def test_resolver_fires_only_on_keyword_miss(self):
        g = Graph(_sample())
        calls = []

        def resolver(query, candidates):
            calls.append(query)
            return "cache-layer"

        # strong keyword hit: resolver must NOT be consulted
        fid, how = g.best("rate limiter", resolver=resolver)
        self.assertEqual((fid, how), ("rate-limiter", "keyword"))
        self.assertEqual(calls, [])

        # genuine miss: resolver is consulted and its answer is honored
        fid, how = g.best("where do evicted entries go", resolver=resolver)
        self.assertEqual((fid, how), ("cache-layer", "resolver"))
        self.assertEqual(len(calls), 1)

    def test_resolver_exception_is_swallowed(self):
        g = Graph(_sample())

        def boom(query, candidates):
            raise RuntimeError("model down")

        fid, how = g.best("totally unrelated zzz", resolver=boom)
        self.assertIn(how, ("miss", "keyword-weak"))


class TestLint(unittest.TestCase):
    def test_missing_vs_drift(self):
        g = Graph(_sample())
        r = g.lint()
        missing = {t for t, _ in r["missing"]}
        drift = {t for t, _, _ in r["drift"]}
        # 'ratelimiter' shares >=2 tokens with 'rate-limiter' -> drift w/ a guess
        self.assertIn("ratelimiter", drift)
        guess = {t: gss for t, _, gss in r["drift"]}["ratelimiter"]
        self.assertEqual(guess, "rate-limiter")
        # 'billing-service' has no near fact -> genuine write-me marker
        self.assertIn("billing-service", missing)


if __name__ == "__main__":
    unittest.main()
