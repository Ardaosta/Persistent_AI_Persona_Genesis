"""The onboarding output actually configures the agent (the bridge)."""

import json
import tempfile
import unittest
from pathlib import Path

from genesis_core.agent import machinery_note
from genesis_core.config import GenesisConfig, load


class TestMachineryNote(unittest.TestCase):
    def test_empty_machinery_no_note(self):
        self.assertEqual(machinery_note({}), "")

    def test_active_vs_passive_differ(self):
        active = machinery_note({"proactivity": "active", "autonomy": "act", "memory_aggressiveness": "high"})
        passive = machinery_note({"proactivity": "on_request", "autonomy": "review_first", "memory_aggressiveness": "modest"})
        self.assertNotEqual(active, passive)
        self.assertIn("when you notice something useful", active)
        self.assertIn("Stay out of the way", passive)
        self.assertIn("check with them first", passive)

    def test_voice_surface_adds_listening_note(self):
        self.assertIn("listen", machinery_note({"surface": "voice"}))
        self.assertNotIn("easy to listen", machinery_note({"surface": "text"}))

    def test_note_carries_no_disposition_words(self):
        note = machinery_note({"proactivity": "active", "autonomy": "act", "memory_aggressiveness": "high", "surface": "voice"})
        for forbidden in ("warm", "flirt", "personality", "register", "tone"):
            self.assertNotIn(forbidden, note.lower())


class TestConfigRoundTrip(unittest.TestCase):
    def test_machinery_persists_in_config(self):
        root = Path(tempfile.mkdtemp())
        (root).mkdir(parents=True, exist_ok=True)
        machinery = {"proactivity": "active", "autonomy": "review_first", "memory_aggressiveness": "high", "surface": "text"}
        (root / "config.json").write_text(json.dumps({"provider": "anthropic", "machinery": machinery}))
        cfg = load(root)
        self.assertEqual(cfg.machinery, machinery)

    def test_default_machinery_is_empty(self):
        self.assertEqual(GenesisConfig(root=Path("/tmp/x")).machinery, {})


if __name__ == "__main__":
    unittest.main()
