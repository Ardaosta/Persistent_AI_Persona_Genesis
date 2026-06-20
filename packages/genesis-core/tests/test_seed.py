"""The onboarding seed codec and the seeded `genesis init` path."""

import argparse
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_core import seed as seedmod


class TestSeedCodec(unittest.TestCase):
    def test_roundtrip(self):
        s = seedmod.make_seed(
            archetype={"relationship": "companion", "engagement": "challenge"},
            machinery={"proactivity": "active", "autonomy": "act"},
            look="matrix",
            provider="gemini",
            sponsor="friend@example.com",
        )
        blob = seedmod.encode(s)
        self.assertNotIn("=", blob)  # no padding → shell-safe
        out = seedmod.decode(blob)
        self.assertEqual(out["machinery"], s["machinery"])
        self.assertEqual(out["archetype"], s["archetype"])
        self.assertEqual(out["look"], "matrix")
        self.assertEqual(out["provider"], "gemini")
        self.assertEqual(out["sponsor"], "friend@example.com")

    def test_decode_drops_unknown_keys(self):
        import base64, json
        raw = json.dumps({"v": 1, "machinery": {}, "evil": "rm -rf"}).encode()
        blob = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        out = seedmod.decode(blob)
        self.assertNotIn("evil", out)

    def test_decode_rejects_garbage(self):
        with self.assertRaises(ValueError):
            seedmod.decode("!!!not base64!!!")
        with self.assertRaises(ValueError):
            seedmod.decode("")

    def test_decode_coerces_bad_shapes(self):
        import base64, json
        raw = json.dumps({"v": 1, "machinery": "notadict", "archetype": 5}).encode()
        blob = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        out = seedmod.decode(blob)
        self.assertEqual(out["machinery"], {})
        self.assertEqual(out["archetype"], {})


class TestLoadSeedArg(unittest.TestCase):
    def setUp(self):
        self.blob = seedmod.encode(seedmod.make_seed(machinery={"proactivity": "active"}))

    def test_from_blob(self):
        out = seedmod.load_seed_arg(self.blob)
        self.assertEqual(out["machinery"], {"proactivity": "active"})

    def test_from_env_fallback(self):
        out = seedmod.load_seed_arg(None, env_value=self.blob)
        self.assertEqual(out["machinery"], {"proactivity": "active"})

    def test_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".seed", delete=False) as f:
            f.write(self.blob)
            path = f.name
        try:
            out = seedmod.load_seed_arg(path)
            self.assertEqual(out["machinery"], {"proactivity": "active"})
        finally:
            Path(path).unlink()

    def test_from_stdin(self):
        with mock.patch("sys.stdin", io.StringIO(self.blob)):
            out = seedmod.load_seed_arg("-")
        self.assertEqual(out["machinery"], {"proactivity": "active"})

    def test_none_when_absent(self):
        self.assertIsNone(seedmod.load_seed_arg(None, None))


class TestSeededInit(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_init_applies_seed_without_a_key(self):
        from genesis_core import cli
        from genesis_core import config as cfgmod
        blob = seedmod.encode(seedmod.make_seed(
            archetype={"relationship": "companion", "engagement": "challenge",
                       "scope": "broad", "modality": "text"},
            machinery={"proactivity": "active", "autonomy": "act",
                       "memory_aggressiveness": "high", "surface": "text"},
            look="tron",
            provider="gemini",
            sponsor="helper@example.com",
        ))
        # Drive cfgmod.load to always resolve our temp root
        real_load = cfgmod.load
        with mock.patch.object(cfgmod, "load", lambda *a, **k: real_load(self.root)), \
             mock.patch.object(cli, "cmd_setup_daemon") as daemon:
            rc = cli.cmd_init(argparse.Namespace(seed=blob))
        self.assertEqual(rc, 0)
        # vault + tiers exist
        self.assertTrue((self.root / "vault" / "continuity").is_dir())
        self.assertTrue((self.root / "perishable").is_dir())
        # config tuned by the seed
        loaded = real_load(self.root)
        self.assertEqual(loaded.machinery.get("proactivity"), "active")
        self.assertEqual(loaded.provider, "gemini")
        # the help-graph sponsor became the allowed email recipient
        self.assertEqual(loaded.allowed_email_recipients, ["helper@example.com"])
        # no key → did not try to schedule
        daemon.assert_not_called()

    def test_seed_mode_claude_code_wires_claude(self):
        from genesis_core import cli
        from genesis_core import config as cfgmod
        blob = seedmod.encode(seedmod.make_seed(
            machinery={"proactivity": "active"},
            archetype={"relationship": "companion", "engagement": "tinkerer",
                       "scope": "broad", "modality": "text"},
            provider="anthropic", mode="claude-code",
        ))
        real_load = cfgmod.load
        with mock.patch.object(cfgmod, "load", lambda *a, **k: real_load(self.root)), \
             mock.patch.object(cli, "cmd_setup_daemon") as daemon, \
             mock.patch.object(cli, "_prompt_for_key") as keyprompt:
            rc = cli.cmd_init(argparse.Namespace(seed=blob, mode="agent"))
        self.assertEqual(rc, 0)
        # Mode B wired: a project settings.json with our SessionStart hook exists
        settings = self.root / ".claude" / "settings.json"
        self.assertTrue(settings.is_file())
        self.assertIn("boot-context", settings.read_text())
        self.assertTrue((self.root / "CLAUDE.md").is_file())
        # Mode B never asks for an API key and never schedules the Mode-A daemon
        keyprompt.assert_not_called()
        daemon.assert_not_called()


if __name__ == "__main__":
    unittest.main()
