import tempfile
import unittest
from pathlib import Path

from genesis_headlines import frontmatter
from genesis_headlines.resolver import resolve

CLUSTER = """---
cluster: voice-portal
aliases: [voice, portal, "voice for aimee", inara]
paths:
  - "repos/A Voice for Someone"
  - "owned-surface"
updated: 2026-07-06
---

# HEADLINES — Voice / Portal

1. **The Portal replaces the old voice app.** Do not fix the old one.
"""


class TestFrontmatter(unittest.TestCase):
    def test_inline_and_dash_lists(self):
        meta, body = frontmatter.parse(CLUSTER)
        self.assertEqual(meta["aliases"], ["voice", "portal", "voice for aimee", "inara"])
        self.assertEqual(meta["paths"], ["repos/A Voice for Someone", "owned-surface"])
        self.assertIn("Portal replaces", body)

    def test_no_frontmatter(self):
        meta, body = frontmatter.parse("just a body")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just a body")

    def test_scalar_reads_updated_and_cluster(self):
        # parse() drops scalars; scalar() recovers them for the freshness discipline.
        self.assertEqual(frontmatter.parse(CLUSTER)[0].get("updated"), [])
        self.assertEqual(frontmatter.scalar(CLUSTER, "updated"), "2026-07-06")
        self.assertEqual(frontmatter.scalar(CLUSTER, "cluster"), "voice-portal")

    def test_scalar_absent_key_and_no_fence(self):
        self.assertIsNone(frontmatter.scalar(CLUSTER, "nope"))
        self.assertIsNone(frontmatter.scalar("just a body", "updated"))


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "voice-portal.md").write_text(CLUSTER, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_alias_whole_word_match(self):
        hits = resolve("please fix the voice loop", dir=str(self.dir))
        self.assertEqual([h.slug for h in hits], ["voice-portal"])

    def test_alias_does_not_match_substring(self):
        # "voice" must not fire on "invoice"
        hits = resolve("reconcile the invoice totals", dir=str(self.dir))
        self.assertEqual(hits, [])

    def test_multiword_alias(self):
        hits = resolve("working on a voice for aimee today", dir=str(self.dir))
        self.assertEqual(len(hits), 1)

    def test_path_match_from_cwd(self):
        # a session whose cwd is under a declared path matches without naming it
        hits = resolve("do the thing /Users/x/genesis/owned-surface", dir=str(self.dir))
        self.assertEqual(len(hits), 1)

    def test_no_match_is_empty(self):
        self.assertEqual(resolve("unrelated task about taxes", dir=str(self.dir)), [])

    def test_empty_store(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(resolve("voice portal inara", dir=empty), [])


if __name__ == "__main__":
    unittest.main()
