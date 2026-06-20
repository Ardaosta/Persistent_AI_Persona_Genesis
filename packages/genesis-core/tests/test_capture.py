"""Tests for soul-capture (the queue half of the INWARD loop)."""

import tempfile
import unittest
from pathlib import Path

from genesis_core.capture import (
    append_capture,
    archive_queue,
    format_for_dream,
    load_queue,
)


class TestCapture(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_append_and_load(self):
        self.assertTrue(append_capture(self.root, "I keep returning to honesty as a value", why="self"))
        q = load_queue(self.root)
        self.assertEqual(len(q), 1)
        self.assertIn("honesty", q[0]["text"])
        self.assertEqual(q[0]["why"], "self")

    def test_empty_text_rejected(self):
        self.assertFalse(append_capture(self.root, "   "))
        self.assertEqual(load_queue(self.root), [])

    def test_multiple_appends_accumulate(self):
        append_capture(self.root, "first")
        append_capture(self.root, "second")
        self.assertEqual(len(load_queue(self.root)), 2)

    def test_load_skips_corrupt_lines(self):
        append_capture(self.root, "good")
        with (self.root / "capture_queue.jsonl").open("a") as fh:
            fh.write("{ not json\n")
        append_capture(self.root, "also good")
        q = load_queue(self.root)
        self.assertEqual(len(q), 2)  # corrupt line skipped, not crashed

    def test_archive_clears_queue_and_counts(self):
        append_capture(self.root, "a")
        append_capture(self.root, "b")
        n = archive_queue(self.root)
        self.assertEqual(n, 2)
        self.assertEqual(load_queue(self.root), [])  # queue cleared
        # archived copy exists
        archives = list((self.root / "capture_archive").glob("*.jsonl"))
        self.assertEqual(len(archives), 1)

    def test_archive_empty_is_zero(self):
        self.assertEqual(archive_queue(self.root), 0)

    def test_format_for_dream(self):
        append_capture(self.root, "I value precision", why="craft")
        text = format_for_dream(load_queue(self.root))
        self.assertIn("I value precision", text)
        self.assertIn("craft", text)


if __name__ == "__main__":
    unittest.main()
