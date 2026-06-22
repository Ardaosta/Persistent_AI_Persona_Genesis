"""Mode-B wiring: boot-context assembly, idempotent settings merge, CLAUDE.md +
SessionStart hook written to the right places."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_core import claude_wire
from genesis_core import config as cfgmod
from genesis_memory import Continuity, Fact, Vault


class TestBootContext(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = cfgmod.GenesisConfig(root=Path(self._td.name))
        self.cfg.vault_dir.mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_includes_index_and_now(self):
        from genesis_core.boot import boot_context_text
        Vault(self.cfg.vault_dir).write(Fact(id="dog-vin", kind="user", description="has a wolfhound"))
        text = boot_context_text(self.cfg)
        self.assertIn("Genesis boot context", text)
        self.assertIn("dog-vin", text)       # the index is in there
        self.assertIn("## Now", text)         # the wall clock block

    def test_empty_vault_is_graceful(self):
        from genesis_core.boot import boot_context_text
        text = boot_context_text(self.cfg)
        self.assertIn("just getting started", text)

    def test_handshake_echoed_when_token_present(self):
        from genesis_core.boot import boot_context_text
        (self.cfg.vault_dir / "handshake.txt").write_text("LUMEN-7", encoding="utf-8")
        text = boot_context_text(self.cfg)
        self.assertIn("LUMEN-7", text)
        self.assertIn("handshake", text.lower())

    def test_carries_continuity(self):
        from genesis_core.boot import boot_context_text
        Continuity(self.cfg.vault_dir).append("I noticed I lean long.")
        text = boot_context_text(self.cfg)
        self.assertIn("lean long", text)

    def test_early_catalysis_nudge_when_sparse(self):
        from genesis_core.boot import boot_context_text
        text = boot_context_text(self.cfg)  # empty vault
        self.assertIn("still new to each other", text)
        self.assertIn("ask at least one genuine question", text)
        self.assertIn("invite them", text)  # bidirectional

    def test_catalysis_tapers_to_lighter_then_off(self):
        from genesis_core.boot import boot_context_text

        def seed(rng):  # unique ids per index so counts actually accumulate
            for i in rng:
                Vault(self.cfg.vault_dir).write(Fact(id=f"u{i}", kind="user", description=f"thing {i}"))

        seed(range(15))  # 15 facts: still under the strong gate (20)
        text = boot_context_text(self.cfg)
        self.assertIn("still new to each other", text)  # strong runway is wide on purpose

        seed(range(15, 25))  # 25 facts: past 20 -> lighter band
        text = boot_context_text(self.cfg)
        self.assertNotIn("still new to each other", text)
        self.assertIn("Still getting to know them", text)

        seed(range(25, 45))  # 45 facts: past 40 -> the perpetual light tier, never silent
        text = boot_context_text(self.cfg)
        self.assertNotIn("Still getting to know them", text)
        self.assertIn("Keep noticing them", text)


class TestSettingsMerge(unittest.TestCase):
    def test_merge_is_idempotent(self):
        root = Path("/tmp/x")
        s = claude_wire.merge_session_hook({}, "/bin/genesis", root)
        s = claude_wire.merge_session_hook(s, "/bin/genesis", root)  # twice
        starts = s["hooks"]["SessionStart"]
        ours = [e for e in starts if any("boot-context" in h["command"] for h in e["hooks"])]
        self.assertEqual(len(ours), 1)  # not duplicated

    def test_preserves_other_settings_and_hooks(self):
        existing = {
            "model": "claude-sonnet-4-6",
            "hooks": {
                "SessionStart": [
                    {"matcher": "startup", "hooks": [{"type": "command", "command": "echo unrelated"}]}
                ],
                "PreToolUse": [{"matcher": "Bash", "hooks": []}],
            },
        }
        s = claude_wire.merge_session_hook(existing, "/bin/genesis", Path("/r"))
        self.assertEqual(s["model"], "claude-sonnet-4-6")          # unrelated key kept
        self.assertIn("PreToolUse", s["hooks"])                     # other hook kept
        cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]]
        self.assertIn("echo unrelated", cmds)                      # foreign SessionStart kept
        self.assertTrue(any("boot-context" in c for c in cmds))    # ours added

    def test_hook_command_carries_root(self):
        entry = claude_wire.build_hook_entry("/opt/genesis", Path("/home/u/.genesis"))
        cmd = entry["hooks"][0]["command"]
        self.assertIn("/home/u/.genesis", cmd)
        self.assertIn("boot-context", cmd)
        self.assertEqual(entry["matcher"], "startup|resume")


class TestWire(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = cfgmod.GenesisConfig(root=Path(self._td.name) / "home")

    def tearDown(self):
        self._td.cleanup()

    def test_project_scope_writes_companion_home(self):
        out = claude_wire.wire(self.cfg, "/bin/genesis", scope="project")
        self.assertTrue(out["claude_md"].is_file())
        self.assertTrue(out["settings"].is_file())
        self.assertEqual(out["launch_dir"], self.cfg.root)
        # CLAUDE.md points at the vault and stays un-authored
        md = out["claude_md"].read_text()
        self.assertIn(str(self.cfg.vault_dir), md)
        self.assertIn("EMPTY", md)
        # the settings file has our hook
        s = json.loads(out["settings"].read_text())
        cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]]
        self.assertTrue(any("boot-context" in c for c in cmds))

    def test_user_scope_targets_home_claude(self):
        with mock.patch.object(claude_wire.Path, "home", return_value=Path(self._td.name) / "fakehome"):
            out = claude_wire.wire(self.cfg, "/bin/genesis", scope="user")
        self.assertEqual(out["claude_md"], Path(self._td.name) / "fakehome" / ".claude" / "CLAUDE.md")
        self.assertIsNone(out["launch_dir"])
        self.assertTrue(out["settings"].is_file())


if __name__ == "__main__":
    unittest.main()
