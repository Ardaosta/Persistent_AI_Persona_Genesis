import tempfile
import unittest
from pathlib import Path

from genesis_core import config as c


class TestConfig(unittest.TestCase):
    def test_layout(self):
        cfg = c.GenesisConfig(root=Path("/tmp/x"), provider="anthropic")
        self.assertEqual(cfg.vault_dir, Path("/tmp/x/vault"))
        self.assertEqual(cfg.secrets_dir, Path("/tmp/x/secrets"))
        self.assertEqual(cfg.key_path, Path("/tmp/x/secrets/anthropic.key"))
        # the load-bearing rule: secrets must NOT live under the vault
        self.assertNotIn(cfg.vault_dir, cfg.secrets_dir.parents)

    def test_load_defaults_to_anthropic(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = c.load(Path(d))
            self.assertEqual(cfg.provider, "anthropic")
            self.assertIsNone(cfg.model)

    def test_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = c.GenesisConfig(root=Path(d), provider="openai", model="gpt-x")
            c.save(cfg)
            again = c.load(Path(d))
            self.assertEqual(again.provider, "openai")
            self.assertEqual(again.model, "gpt-x")

    def test_openai_requires_model(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = c.GenesisConfig(root=Path(d), provider="openai", model=None)
            (cfg.secrets_dir).mkdir(parents=True)
            cfg.key_path.write_text("sk-test")
            with self.assertRaises(RuntimeError):
                cfg.build_backend()


if __name__ == "__main__":
    unittest.main()
