"""Tests for the OUTWARD loop (selection, rotation, finding-write)."""

import tempfile
import unittest
from pathlib import Path

from genesis_core.outward import (
    candidate_threads,
    learned_today,
    mark_learned,
    pick_thread,
    write_finding,
)
from genesis_memory import Fact, Vault


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.vault = Vault(self.root / "vault")

    def _add(self, fid, kind, desc):
        self.vault.write(Fact(id=fid, kind=kind, description=desc))

    def test_empty_vault_has_no_threads(self):
        self.assertEqual(candidate_threads(self.vault), [])
        self.assertIsNone(pick_thread(self.vault, self.root))

    def test_only_pursuable_kinds_are_threads(self):
        self._add("dog", "user", "his dog Vin")
        self._add("proj", "project", "the woodworking shop")
        self._add("ref", "reference", "the brand palette")
        self._add("me", "soul", "I value precision")     # soul = not a thread
        self._add("fb", "feedback", "no emdashes")        # feedback = not a thread
        threads = candidate_threads(self.vault)
        self.assertIn("his dog Vin", threads)
        self.assertIn("the woodworking shop", threads)
        self.assertIn("the brand palette", threads)
        self.assertNotIn("I value precision", threads)
        self.assertNotIn("no emdashes", threads)

    def test_pick_rotates_through_threads(self):
        self._add("a", "user", "alpha")
        self._add("b", "user", "beta")
        first = pick_thread(self.vault, self.root)
        second = pick_thread(self.vault, self.root)
        self.assertNotEqual(first, second)  # doesn't fixate on one thread
        third = pick_thread(self.vault, self.root)
        self.assertEqual(third, first)  # wraps around

    def test_pick_survives_corrupt_state(self):
        self._add("a", "user", "alpha")
        (self.root / "outward_state.json").write_text("{ not json")
        self.assertEqual(pick_thread(self.vault, self.root), "alpha")


class TestDailyGate(unittest.TestCase):
    def test_learned_gate(self):
        root = Path(tempfile.mkdtemp())
        self.assertFalse(learned_today(root))
        mark_learned(root)
        self.assertTrue(learned_today(root))

    def test_gate_coexists_with_cursor(self):
        # marking learned must not clobber the thread-rotation cursor
        root = Path(tempfile.mkdtemp())
        v = Vault(root / "vault")
        v.write(Fact(id="a", kind="user", description="alpha"))
        v.write(Fact(id="b", kind="user", description="beta"))
        first = pick_thread(v, root)   # advances cursor
        mark_learned(root)
        second = pick_thread(v, root)
        self.assertNotEqual(first, second)
        self.assertTrue(learned_today(root))


class TestWriteFinding(unittest.TestCase):
    def test_finding_is_appended_with_thread_and_text(self):
        td = Path(tempfile.mkdtemp())
        findings = td / "vault" / "findings"
        p1 = write_finding(findings, "the woodworking shop", "Try labeling offcuts by project.")
        text = p1.read_text()
        self.assertIn("the woodworking shop", text)
        self.assertIn("Try labeling offcuts by project.", text)
        # a second finding the same day appends, not overwrites
        p2 = write_finding(findings, "his dog Vin", "Senior wolfhounds do well with...")
        self.assertEqual(p1, p2)
        text2 = p2.read_text()
        self.assertIn("Try labeling offcuts", text2)
        self.assertIn("Senior wolfhounds", text2)


if __name__ == "__main__":
    unittest.main()
