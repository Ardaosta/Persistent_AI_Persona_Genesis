"""Tests for the invariant-1 emptiness scanner."""

import tempfile
import unittest
from pathlib import Path

from genesis_core.emptiness import scan


class TestEmptiness(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def _write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def test_clean_tree_passes(self):
        self._write("README.md", "# hello\nno frontmatter here")
        self._write("user/dog.md", "---\nid: dog\nkind: user\n---\nhis dog Vin")
        self.assertEqual(scan(self.root), [])

    def test_soul_fact_is_flagged(self):
        self._write("soul/me.md", "---\nid: me\nkind: soul\n---\nI value precision")
        offenders = scan(self.root)
        self.assertEqual(len(offenders), 1)
        self.assertIn("me.md", offenders[0])

    def test_skips_tests_and_archive(self):
        self._write("tests/fixture.md", "---\nid: x\nkind: soul\n---\nfixture")
        self._write("capture_archive/old.md", "---\nid: y\nkind: soul\n---\narchived")
        self.assertEqual(scan(self.root), [])  # both skipped

    def test_other_kinds_not_flagged(self):
        for k in ("user", "feedback", "project", "reference"):
            self._write(f"{k}/f.md", f"---\nid: f-{k}\nkind: {k}\n---\nbody")
        self.assertEqual(scan(self.root), [])


if __name__ == "__main__":
    unittest.main()
