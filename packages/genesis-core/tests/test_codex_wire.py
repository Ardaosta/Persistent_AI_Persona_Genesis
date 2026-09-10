"""Mode-B second door: AGENTS.md + hooks.json + the trust block, idempotent, content-free."""

import json
import tempfile
import unittest
from pathlib import Path

from genesis_core import codex_wire, claude_wire
from genesis_core import config as cfgmod


class TestHooksMerge(unittest.TestCase):
    def test_all_three_events_and_idempotent(self):
        root = Path("/tmp/r")
        h = codex_wire.merge_hooks({}, "/bin/genesis", root)
        h = codex_wire.merge_hooks(h, "/bin/genesis", root)
        for ev in ("SessionStart", "UserPromptSubmit", "Stop"):
            ours = [e for e in h["hooks"][ev] if codex_wire._is_ours(e)]
            self.assertEqual(len(ours), 1, ev)
        boot = h["hooks"]["SessionStart"][0]["hooks"][0]
        self.assertIn("boot-context --hook", boot["command"])
        self.assertIn("/tmp/r", boot["command"])
        self.assertEqual(boot["additionalContextLimit"], codex_wire.CONTEXT_LIMIT)

    def test_preserves_foreign_hooks(self):
        existing = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}],
                              "PreToolUse": [{"matcher": "shell", "hooks": []}]},
                    "other": 1}
        h = codex_wire.merge_hooks(existing, "/bin/genesis", Path("/r"))
        cmds = [x["command"] for e in h["hooks"]["Stop"] for x in e["hooks"]]
        self.assertIn("echo mine", cmds)
        self.assertTrue(any("craft-gate" in c for c in cmds))
        self.assertIn("PreToolUse", h["hooks"])
        self.assertEqual(h["other"], 1)


class TestTrustBlock(unittest.TestCase):
    def test_append_then_replace(self):
        home = Path("/Users/x/My AI")
        t = codex_wire.merge_trust('model = "gpt-5.5"\n', home)
        self.assertIn('model = "gpt-5.5"', t)
        self.assertIn("[projects.'/Users/x/My AI']", t)
        self.assertIn('trust_level = "trusted"', t)
        t2 = codex_wire.merge_trust(t, Path("/Users/x/Other"))
        self.assertEqual(t2.count("trust_level"), 1)       # replaced, not duplicated
        self.assertIn("Other", t2)
        self.assertEqual(t2, codex_wire.merge_trust(t2, Path("/Users/x/Other")))  # stable

    def test_windows_path_survives_verbatim(self):
        t = codex_wire.merge_trust("", Path(r"C:\Users\p\My AI"))
        self.assertIn(r"[projects.'C:\Users\p\My AI']", t)


class TestWire(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        base = Path(self._td.name)
        self.cfg = cfgmod.GenesisConfig(root=base / "home", name="Quill",
                                        project_repo="https://example.org/repo", drip=True)
        self.cfg.vault_dir.mkdir(parents=True)
        self.home = base / "My AI"
        self.codex_home = base / ".codex"

    def tearDown(self):
        self._td.cleanup()

    def test_writes_everything_and_agrees_with_claude_door(self):
        out = codex_wire.wire(self.cfg, "/bin/genesis", home_dir=self.home, codex_home=self.codex_home)
        self.assertTrue(out["agents_md"].is_file())
        self.assertTrue(out["hooks"].is_file())
        self.assertTrue(out["config_toml"].is_file())
        md = out["agents_md"].read_text()
        self.assertIn("You are **Quill**", md)
        self.assertIn("EMPTY", md)                       # identity section still empty
        self.assertIn("https://example.org/repo", md)    # project pointer rendered
        self.assertIn("relationship-questions.md", md)   # drip section rendered
        self.assertIn(str(self.cfg.vault_dir), md)
        # the two doors render the same manual (only the file name differs)
        c = claude_wire.render_claude_md(self.cfg, "/bin/genesis")
        self.assertEqual(md, c)
        h = json.loads(out["hooks"].read_text())
        self.assertIn("SessionStart", h["hooks"])
        self.assertIn(str(self.home), out["config_toml"].read_text())

    def test_unnamed_is_unauthored(self):
        cfg = cfgmod.GenesisConfig(root=self.cfg.root)
        md = codex_wire.render_agents_md(cfg, "/bin/genesis")
        self.assertIn("un-authored", md)
        self.assertNotIn("You are **", md)
        self.assertNotIn("The project you are joining", md)
        self.assertNotIn("Getting to know them", md)


if __name__ == "__main__":
    unittest.main()
