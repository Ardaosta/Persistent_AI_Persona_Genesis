"""The shared manual: content-free, and the seed-time conditions render on both doors."""

import tempfile
import unittest
from pathlib import Path

from genesis_core import manual, config as cfgmod, emptiness, seed as seedmod


class TestManual(unittest.TestCase):
    def test_no_shipped_soul_content_in_source_tree(self):
        src = Path(__file__).resolve().parents[1] / "src"
        self.assertEqual(emptiness.scan(src), [])

    def test_disciplines_present_and_identity_empty(self):
        cfg = cfgmod.GenesisConfig(root=Path("/tmp/h"))
        md = manual.render(cfg, "/bin/genesis")
        for needle in ("Verify before asserting", "Name the form, never the absence",
                       "Loaded is not run", "friction", "Think it through first",
                       "(EMPTY: authored by the relationship"):
            self.assertIn(needle, md)
        self.assertNotIn("Getting to know them", md)

    def test_seed_roundtrip_carries_new_conditions(self):
        s = seedmod.make_seed(name="Quill", harnesses=["codex", "claude-code", "bogus"],
                              project_repo="https://x/y", drip=True, mode="claude-code")
        out = seedmod.decode(seedmod.encode(s))
        self.assertEqual(out["name"], "Quill")
        self.assertEqual(out["harnesses"], ["codex", "claude-code"])
        self.assertEqual(out["project_repo"], "https://x/y")
        self.assertTrue(out["drip"])

    def test_config_roundtrip_of_new_fields(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = cfgmod.GenesisConfig(root=Path(td))
            cfgmod.update_fields(cfg, name="Quill", drip=True, harnesses=["codex"], project_repo="r")
            cfgmod.update_fields(cfg, provider="anthropic")   # a second write keeps the first
            back = cfgmod.load(Path(td), creating=True)
            self.assertEqual((back.name, back.drip, back.harnesses, back.project_repo, back.provider),
                             ("Quill", True, ["codex"], "r", "anthropic"))


if __name__ == "__main__":
    unittest.main()
