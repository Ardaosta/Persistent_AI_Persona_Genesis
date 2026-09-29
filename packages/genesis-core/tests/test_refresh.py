"""`genesis refresh`, and the guard that keeps re-rendering off a hand-written
manual (an owner-authored companion keeps its persona in CLAUDE.md)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from genesis_core import cli, config as cfgmod


class TestRefresh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "root"
        self.home = base / "home"
        (self.home / "My AI").mkdir(parents=True)
        self.root.mkdir()
        (self.root / "config.json").write_text(json.dumps(
            {"engine_trains": False, "harnesses": ["claude-code"], "drip": True}), encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"GENESIS_ROOT": str(self.root)})
        self.env.start()
        self.homep = mock.patch.object(cli._P, "home", return_value=self.home)
        self.homep.start()

    def tearDown(self):
        self.homep.stop()
        self.env.stop()
        self.tmp.cleanup()

    def run_refresh(self, **kw):
        args = SimpleNamespace(question_bank=kw.get("bank"), print_section=kw.get("section", False))
        return cli.cmd_refresh(args)

    def test_generated_manual_is_rerendered_with_open_loops(self):
        md = self.home / "My AI" / "CLAUDE.md"
        md.write_text("# Genesis: operating manual\n\n(old)\n", encoding="utf-8")
        self.assertEqual(self.run_refresh(), 0)
        text = md.read_text(encoding="utf-8")
        self.assertIn("## Open loops", text)
        self.assertNotIn("(old)", text)

    def test_hand_written_manual_is_never_overwritten(self):
        md = self.home / "My AI" / "CLAUDE.md"
        authored = "# Jam\n\nYou are a hand-written companion.\n"
        md.write_text(authored, encoding="utf-8")
        self.assertEqual(self.run_refresh(), 0)
        self.assertEqual(md.read_text(encoding="utf-8"), authored)

    def test_rename_no_longer_clobbers_a_hand_written_manual(self):
        """The latent bug the guard also closes: rename re-rendered unconditionally."""
        md = self.home / "My AI" / "CLAUDE.md"
        authored = "# Mine\n\nhand-written\n"
        md.write_text(authored, encoding="utf-8")
        cli._rerender_doors(cfgmod.load())
        self.assertEqual(md.read_text(encoding="utf-8"), authored)

    def test_question_bank_switch_persists_and_installs_bank(self):
        self.assertEqual(self.run_refresh(bank="working"), 0)
        cfg = cfgmod.load()
        self.assertEqual(cfg.machinery.get("question_bank"), "working")
        self.assertTrue((cfg.vault_dir / "reference" / "working-questions.md").is_file())

    def test_bank_switch_keeps_other_machinery(self):
        data = json.loads((self.root / "config.json").read_text())
        data["machinery"] = {"autonomy": "act"}
        (self.root / "config.json").write_text(json.dumps(data))
        self.run_refresh(bank="working")
        self.assertEqual(cfgmod.load().machinery, {"autonomy": "act", "question_bank": "working"})


if __name__ == "__main__":
    unittest.main()
