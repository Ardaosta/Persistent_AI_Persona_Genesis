"""Tests for the boot ritual + liveness handshake."""

import tempfile
import unittest
from pathlib import Path

from genesis_core.boot import (
    handshake_instruction,
    handshake_token,
    recent_continuity,
    verify_handshake,
)
from genesis_core.config import GenesisConfig


def _cfg(root: Path) -> GenesisConfig:
    return GenesisConfig(root=root, provider="anthropic")


class TestHandshake(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = _cfg(self.root)
        self.cfg.vault_dir.mkdir(parents=True)

    def test_no_token_when_unauthored(self):
        self.assertIsNone(handshake_token(self.cfg))

    def test_reads_token(self):
        (self.cfg.vault_dir / "handshake.txt").write_text("  emberlight-7  \n")
        self.assertEqual(handshake_token(self.cfg), "emberlight-7")

    def test_empty_token_file_is_none(self):
        (self.cfg.vault_dir / "handshake.txt").write_text("   \n")
        self.assertIsNone(handshake_token(self.cfg))

    def test_instruction_contains_token(self):
        self.assertIn("emberlight-7", handshake_instruction("emberlight-7"))

    def test_verify(self):
        self.assertTrue(verify_handshake("emberlight-7\nHello again.", "emberlight-7"))
        self.assertFalse(verify_handshake("Hello, I am a generic assistant.", "emberlight-7"))
        self.assertFalse(verify_handshake("anything", None))  # un-authored: no proof needed


class TestContinuity(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = _cfg(self.root)

    def test_empty_when_nothing(self):
        self.assertEqual(recent_continuity(self.cfg), "")

    def test_includes_recent_dream_and_finding(self):
        self.cfg.journal_dir.mkdir(parents=True)
        (self.cfg.journal_dir / "2026-06-19.md").write_text("# Dream\n\nI thought about honesty.")
        self.cfg.findings_dir.mkdir(parents=True)
        (self.cfg.findings_dir / "2026-06-19.md").write_text("## finding\n\nKanban for the shop.")
        cont = recent_continuity(self.cfg)
        self.assertIn("honesty", cont)
        self.assertIn("Kanban", cont)


if __name__ == "__main__":
    unittest.main()
