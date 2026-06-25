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

    def test_cycle_writes_finding(self):
        raw = "FINDING: Firmware V1.4.2 adds LSSC. | SOURCE: https://hypershell.tech/x | WHY: smoother slow walking."
        with mock.patch.object(sylph, "_research", return_value=raw):
            out = sylph.run_cycle(self.cfg)
        self.assertEqual(out["topic"], "Hypershell")
        self.assertEqual(out["source"], "https://hypershell.tech/x")
        self.assertTrue(out["path"].is_file())

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


if __name__ == "__main__":
    unittest.main()
