"""Tests for the dream daykey ledger and journal helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genesis_core.dream import (
    already_dreamed_today,
    generate_plist,
    generate_wrapper,
    get_last_dream,
    mark_dream,
    today_key,
    write_journal,
)


class TestDaykey(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_no_dreams_yet(self):
        self.assertIsNone(get_last_dream(self.root))
        self.assertFalse(already_dreamed_today(self.root))

    def test_mark_and_detect(self):
        ts = mark_dream(self.root)
        self.assertIsNotNone(ts)
        self.assertTrue(already_dreamed_today(self.root))

    def test_last_dream_returns_today(self):
        mark_dream(self.root)
        last = get_last_dream(self.root)
        self.assertIsNotNone(last)
        self.assertEqual(last[0], today_key())

    def test_past_day_not_counted_as_today(self):
        # Write a key for a past date directly
        ledger = self.root / "daykeys"
        ledger.mkdir()
        (ledger / "2000-01-01.txt").write_text("2000-01-01T03:00:00")
        self.assertFalse(already_dreamed_today(self.root))

    def test_force_flag_not_handled_here(self):
        # already_dreamed_today just checks the ledger; CLI handles --force
        mark_dream(self.root)
        self.assertTrue(already_dreamed_today(self.root))


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.journal_dir = self.td / "vault" / "journal"

    def test_writes_file(self):
        path = write_journal(self.journal_dir, "Today I thought about things.")
        self.assertTrue(path.exists())
        text = path.read_text()
        self.assertIn("Today I thought about things.", text)
        self.assertIn("# Dream", text)

    def test_creates_dirs(self):
        write_journal(self.journal_dir, "test")
        self.assertTrue(self.journal_dir.exists())

    def test_filename_is_today(self):
        path = write_journal(self.journal_dir, "test")
        self.assertEqual(path.stem, today_key())


class TestDaemonHelpers(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())

    def test_wrapper_is_executable(self):
        wrapper = generate_wrapper(self.td, "/some/pythonpath", "/usr/bin/python3")
        self.assertTrue(wrapper.exists())
        import stat
        mode = wrapper.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)

    def test_wrapper_contains_paths(self):
        wrapper = generate_wrapper(self.td, "/some/pythonpath", "/usr/bin/python3")
        text = wrapper.read_text()
        self.assertIn("/some/pythonpath", text)
        self.assertIn("/usr/bin/python3", text)
        self.assertIn(str(self.td), text)

    def test_plist_generation(self):
        wrapper = generate_wrapper(self.td, "/some/pp", "/usr/bin/python3")
        with patch("pathlib.Path.home", return_value=self.td):
            plist = generate_plist(self.td, wrapper)
        self.assertTrue(plist.exists())
        text = plist.read_text()
        self.assertIn("ai.genesis.heartbeat", text)
        self.assertIn(str(wrapper), text)
        self.assertIn("StartInterval", text)


if __name__ == "__main__":
    unittest.main()
