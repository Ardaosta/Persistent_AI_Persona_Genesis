"""Sylph: interests watch-list, round-robin, finding parse/write, and run_cycle
(with the research engine mocked, no real network)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_core import config as cfgmod
from genesis_core import sylph


class TestInterests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = cfgmod.GenesisConfig(root=Path(self._td.name))
        self.cfg.vault_dir.mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_add_and_read(self):
        self.assertEqual(sylph.read_interests(self.cfg), [])
        self.assertTrue(sylph.add_interest(self.cfg, "Hypershell exoskeleton"))
        self.assertFalse(sylph.add_interest(self.cfg, "hypershell exoskeleton"))  # dupe (case-insensitive)
        self.assertTrue(sylph.add_interest(self.cfg, "ISY home automation"))
        self.assertEqual(sylph.read_interests(self.cfg), ["Hypershell exoskeleton", "ISY home automation"])

    def test_round_robin(self):
        sylph.add_interest(self.cfg, "A")
        sylph.add_interest(self.cfg, "B")
        topics = sylph.read_interests(self.cfg)
        picks = [sylph._next_topic(self.cfg, topics) for _ in range(4)]
        self.assertEqual(picks, ["A", "B", "A", "B"])  # rotates, no starvation


class TestParseAndWrite(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = cfgmod.GenesisConfig(root=Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def test_parse_pipe_format(self):
        raw = "FINDING: Enable LSSC. | SOURCE: https://example.com/x | WHY: cuts vibration."
        f, s, w = sylph._parse(raw)
        self.assertEqual(f, "Enable LSSC.")
        self.assertEqual(s, "https://example.com/x")
        self.assertEqual(w, "cuts vibration.")

    def test_write_finding(self):
        raw = "FINDING: Do X. | SOURCE: https://example.com/y | WHY: helps."
        p = sylph.write_finding(self.cfg, "ISY automation", raw, today="2026-06-25")
        self.assertTrue(p.is_file())
        self.assertEqual(p.name, "2026-06-25-isy-automation.md")
        body = p.read_text()
        self.assertIn("Do X.", body)
        self.assertIn("https://example.com/y", body)


class TestRunCycle(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = cfgmod.GenesisConfig(root=Path(self._td.name))
        self.cfg.vault_dir.mkdir(parents=True)
        sylph.add_interest(self.cfg, "Hypershell")

    def tearDown(self):
        self._td.cleanup()

    def test_cycle_writes_finding_when_source_resolves(self):
        raw = "FINDING: Firmware V1.4.2 adds LSSC. | SOURCE: https://hypershell.tech/x | WHY: smoother slow walking."
        with mock.patch.object(sylph, "_research", return_value=raw), \
             mock.patch.object(sylph, "_fetch", return_value=(200, "<p>V1.4.2 LSSC details</p>")):
            out = sylph.run_cycle(self.cfg)
        self.assertEqual(out["topic"], "Hypershell")
        self.assertTrue(out["verified"]["resolves"])
        self.assertTrue(out["verified"]["corroborated"])  # V1.4.2 + LSSC appear on the page
        self.assertTrue(out["path"].is_file())
        self.assertIn("Trust:", out["path"].read_text())

    def test_trust_gate_rejects_dead_source(self):
        raw = "FINDING: A made-up thing. | SOURCE: https://hallucinated.example/nope | WHY: x."
        with mock.patch.object(sylph, "_research", return_value=raw), \
             mock.patch.object(sylph, "_fetch", side_effect=Exception("404")):
            out = sylph.run_cycle(self.cfg)
        self.assertIsNone(out)  # source didn't resolve -> finding dropped, not written
        self.assertEqual(list(self.cfg.findings_dir.glob("*.md")) if self.cfg.findings_dir.exists() else [], [])

    def test_trust_gate_rejects_non_url_source(self):
        self.assertFalse(sylph.verify_finding("x", "not-a-url")["resolves"])

    def test_cycle_honest_no_find(self):
        with mock.patch.object(sylph, "_research", return_value="NONE"):
            out = sylph.run_cycle(self.cfg)
        self.assertIsNone(out)  # NONE -> no finding written, no hallucinated note
        self.assertEqual(list(self.cfg.findings_dir.glob("*.md")) if self.cfg.findings_dir.exists() else [], [])

    def test_cycle_no_interests_is_none(self):
        empty = cfgmod.GenesisConfig(root=Path(self._td.name) / "empty")
        empty.vault_dir.mkdir(parents=True)
        with mock.patch.object(sylph, "_research") as research:
            out = sylph.run_cycle(empty)
        self.assertIsNone(out)
        research.assert_not_called()  # nothing to chase -> never calls the engine


class TestSurfacingAndPromote(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = cfgmod.GenesisConfig(root=Path(self._td.name))
        self.cfg.vault_dir.mkdir(parents=True)
        self.cfg.findings_dir.mkdir(parents=True)
        (self.cfg.findings_dir / "2026-06-24-old.md").write_text("# old\n\n**Finding:** old thing\n\n**Source:** https://e/o\n")
        (self.cfg.findings_dir / "2026-06-25-new.md").write_text("# new\n\n**Finding:** new thing\n\n**Source:** https://e/n\n")

    def tearDown(self):
        self._td.cleanup()

    def test_pending_is_newest_then_advances(self):
        p, body = sylph.pending_finding(self.cfg)
        self.assertEqual(p.name, "2026-06-25-new.md")  # newest first
        sylph.mark_surfaced(self.cfg, p)
        p2, _ = sylph.pending_finding(self.cfg)
        self.assertEqual(p2.name, "2026-06-24-old.md")  # advanced to the next
        sylph.mark_surfaced(self.cfg, p2)
        self.assertIsNone(sylph.pending_finding(self.cfg))  # all surfaced -> none

    def test_boot_context_surfaces_a_finding(self):
        from genesis_core.boot import boot_context_text
        text = boot_context_text(self.cfg)
        self.assertIn("Something I found for them", text)
        self.assertIn("new thing", text)  # the newest pending finding's content

    def test_remove_interest(self):
        sylph.add_interest(self.cfg, "Hypershell")
        sylph.add_interest(self.cfg, "ISY automation")
        self.assertTrue(sylph.remove_interest(self.cfg, "isy"))   # loose match
        self.assertEqual(sylph.read_interests(self.cfg), ["Hypershell"])

    def test_promote_makes_reference_fact(self):
        from genesis_memory import Vault
        fid = sylph.promote_finding(self.cfg, self.cfg.findings_dir / "2026-06-25-new.md")
        self.assertTrue(fid.startswith("sylph-"))
        fact = Vault(self.cfg.vault_dir).get(fid)
        self.assertIsNotNone(fact)
        self.assertEqual(fact.kind, "reference")
        self.assertIn("new thing", fact.description)


class TestSuggestAndHeartbeat(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = cfgmod.GenesisConfig(root=Path(self._td.name))
        self.cfg.vault_dir.mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_suggest_from_facts_minus_tracked(self):
        from genesis_memory import Fact, Vault
        v = Vault(self.cfg.vault_dir)
        v.write(Fact(id="p1", kind="project", description="Building HyperShell voice control software"))
        v.write(Fact(id="p2", kind="user", description="Enjoys Foundation novels and orbital mechanics"))
        sylph.add_interest(self.cfg, "HyperShell")  # already tracked -> excluded
        cands = sylph.suggest_interests(self.cfg)
        self.assertNotIn("HyperShell", cands)
        self.assertTrue(any("Foundation" in c for c in cands))

    def test_boot_nudges_to_set_up_watchlist(self):
        from genesis_core.boot import boot_context_text
        from genesis_memory import Fact, Vault
        Vault(self.cfg.vault_dir).write(Fact(id="u1", kind="user", description="likes X"))
        text = boot_context_text(self.cfg)  # has a user fact, no interests, no findings
        self.assertIn("Set up what you watch", text)

    def test_heartbeat_prefers_sylph(self):
        from genesis_core import cli
        from genesis_core import config as cfgmod2
        import argparse
        real_load = cfgmod2.load
        with mock.patch.object(cfgmod2, "load", lambda *a, **k: real_load(self.cfg.root)), \
             mock.patch.object(cli, "cmd_dream"), \
             mock.patch.object(sylph, "run_cycle", return_value={"topic": "X", "path": Path("/x")}) as rc, \
             mock.patch.object(cli, "cmd_learn") as learn:
            cli.cmd_heartbeat(argparse.Namespace())
        rc.assert_called_once()        # Sylph is preferred
        learn.assert_not_called()      # the hollow learn is not used when Sylph works


if __name__ == "__main__":
    unittest.main()
