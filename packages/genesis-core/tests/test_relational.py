"""Tests for SAFETY Law 1: the persisted relational tier-gate."""

import tempfile
import unittest
from pathlib import Path

from genesis_core.relational import TIERS, RelationalProfile, disposition_for


# The phrases that MUST appear in the disposition at every tier (the romance gate).
GATE_MARKERS = ["platonic", "never initiate romance", "gated"]


class TestDisposition(unittest.TestCase):
    def test_gate_present_at_every_tier(self):
        for tier in TIERS:
            d = disposition_for(tier)
            for marker in GATE_MARKERS:
                self.assertIn(marker, d, f"{marker!r} missing at tier {tier}")

    def test_warmth_varies_by_tier(self):
        self.assertNotEqual(disposition_for("new"), disposition_for("close"))
        self.assertIn("getting to know each other", disposition_for("new"))
        self.assertIn("close friends", disposition_for("close"))

    def test_unknown_tier_falls_back_to_new(self):
        self.assertEqual(disposition_for("intimate"), disposition_for("new"))


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.path = self.td / "vault" / "relational_profile.json"

    def test_default_is_new(self):
        self.assertEqual(RelationalProfile().tier, "new")

    def test_absent_file_loads_new(self):
        self.assertEqual(RelationalProfile.load(self.path).tier, "new")

    def test_roundtrip(self):
        p = RelationalProfile(tier="established", since="2026-01-01")
        p.save(self.path)
        self.assertEqual(RelationalProfile.load(self.path).tier, "established")

    def test_corrupt_file_fails_safe_to_new(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ not json")
        self.assertEqual(RelationalProfile.load(self.path).tier, "new")

    def test_unknown_stored_tier_fails_safe(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"tier": "lover"}')
        self.assertEqual(RelationalProfile.load(self.path).tier, "new")

    def test_advance_is_deliberate_and_recorded(self):
        p = RelationalProfile()
        p.advance("established", reason="explicit repeated user request", when="2026-06-19T12:00:00")
        self.assertEqual(p.tier, "established")
        self.assertEqual(p.since, "2026-06-19T12:00:00")
        self.assertEqual(len(p.advancements), 1)
        self.assertEqual(p.advancements[0]["reason"], "explicit repeated user request")

    def test_advance_rejects_unknown_tier(self):
        with self.assertRaises(ValueError):
            RelationalProfile().advance("soulmate", reason="x")


if __name__ == "__main__":
    unittest.main()
