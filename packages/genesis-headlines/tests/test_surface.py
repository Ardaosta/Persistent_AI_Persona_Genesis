import tempfile
import unittest
from pathlib import Path

from genesis_headlines.surface import surface

CLUSTER = """---
cluster: memory-core
aliases: [memory, vault, substrate]
paths:
  - "genesis-memory"
updated: 2026-07-06
---

# HEADLINES — Memory core

1. **The vault is the source of truth.** Derived indexes rebuild from it.
"""


class TestSurface(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "headlines"
        self.dir.mkdir()
        (self.dir / "memory-core.md").write_text(CLUSTER, encoding="utf-8")
        self.state = tempfile.TemporaryDirectory()
        import os
        os.environ["GENESIS_STATE_DIR"] = self.state.name

    def tearDown(self):
        import os
        os.environ.pop("GENESIS_STATE_DIR", None)
        self.tmp.cleanup()
        self.state.cleanup()

    def test_first_touch_surfaces(self):
        r = surface("work on the vault", "sess-1", dir=str(self.dir))
        self.assertTrue(r.matched)
        self.assertIn("PROJECT HEADLINES", r.text)
        self.assertIn("source of truth", r.text)
        self.assertEqual(r.clusters, ["memory-core"])

    def test_second_touch_suppressed_same_session(self):
        surface("work on the vault", "sess-1", dir=str(self.dir))
        r2 = surface("more vault work", "sess-1", dir=str(self.dir))
        self.assertFalse(r2.matched)
        self.assertEqual(r2.suppressed, ["memory-core"])

    def test_different_session_surfaces_again(self):
        surface("vault", "sess-1", dir=str(self.dir))
        r = surface("vault", "sess-2", dir=str(self.dir))
        self.assertTrue(r.matched)

    def test_edited_headline_resurfaces(self):
        surface("vault", "sess-1", dir=str(self.dir))
        (self.dir / "memory-core.md").write_text(
            CLUSTER.replace("source of truth", "SOLE source of truth"), encoding="utf-8"
        )
        r = surface("vault", "sess-1", dir=str(self.dir))
        self.assertTrue(r.matched)  # the update is itself load-bearing

    def test_no_dedup_always_surfaces(self):
        surface("vault", "sess-1", dir=str(self.dir))
        r = surface("vault", "sess-1", dir=str(self.dir), dedup=False)
        self.assertTrue(r.matched)

    def test_no_match_empty(self):
        r = surface("unrelated task", "sess-1", dir=str(self.dir))
        self.assertFalse(r.matched)
        self.assertEqual(r.text, "")


if __name__ == "__main__":
    unittest.main()
