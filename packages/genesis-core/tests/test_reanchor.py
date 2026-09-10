"""Register re-anchor: fires every N prompts, leaves breadcrumbs, prints only vault content."""

import tempfile
import unittest
from pathlib import Path

from genesis_core import reanchor as ra
from genesis_core import config as cfgmod
from genesis_memory import Continuity, Fact, Vault


class TestReanchor(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.cfg = cfgmod.GenesisConfig(root=self.root)
        self.cfg.vault_dir.mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_fires_on_the_interval_and_logs_every_tick(self):
        fired = [ra.tick(self.root, interval=3) for _ in range(7)]
        self.assertEqual(fired, [False, False, True, False, False, True, False])
        log = ra.log_path(self.root).read_text().splitlines()
        self.assertEqual(len(log), 7)                       # a breadcrumb per prompt
        self.assertEqual(sum("fired=yes" in ln for ln in log), 2)

    def test_block_is_vault_content_only(self):
        text = ra.block(self.cfg)
        self.assertIn("un-authored", text)
        self.assertNotIn("soul index", text)   # empty vault: nothing invented
        Vault(self.cfg.vault_dir).write(Fact(id="honesty-first", kind="soul", description="honest before comfortable"))
        Continuity(self.cfg.vault_dir).append("I noticed I lean long.")
        self.cfg.name = "Quill"
        text = ra.block(self.cfg)
        self.assertIn("You are Quill.", text)
        self.assertIn("honesty-first", text)
        self.assertIn("lean long", text)
        self.assertIn("platonic", text)        # the persisted disposition rides along


if __name__ == "__main__":
    unittest.main()
