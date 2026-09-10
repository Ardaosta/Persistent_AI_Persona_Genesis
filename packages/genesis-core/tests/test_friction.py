"""The craft loop: capture, explicit none, routing, scoring, and the journaling warning."""

import tempfile
import unittest
from pathlib import Path

from genesis_core import friction as fr


class TestFriction(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_append_and_none_both_count_as_answers(self):
        self.assertIsNone(fr.last_entry_time(self.root))
        fr.append_none(self.root)
        self.assertIsNotNone(fr.last_entry_time(self.root))
        self.assertEqual(fr.stats(self.root)["explicit_none"], 1)
        self.assertTrue(fr.append_friction(self.root, "had to hunt for the deploy command",
                                           kind="gap", trigger="next deploy", win="one command"))
        s = fr.stats(self.root)
        self.assertEqual((s["entries"], s["with_win"], s["routed"], s["won"]), (1, 1, 0, 0))
        self.assertEqual(len(fr.pending(self.root)), 1)

    def test_rejects_empty_and_bad_kind(self):
        self.assertFalse(fr.append_friction(self.root, "   ", kind="gap"))
        self.assertFalse(fr.append_friction(self.root, "x", kind="vibes"))

    def test_route_and_score(self):
        fr.append_none(self.root)
        fr.append_friction(self.root, "thing", kind="bug")
        self.assertFalse(fr.route(self.root, 0, "memory"))     # cannot route a none
        self.assertFalse(fr.route(self.root, 1, "nowhere"))
        self.assertTrue(fr.route(self.root, 1, "rule", "became a rule"))
        self.assertEqual(fr.pending(self.root), [])
        self.assertTrue(fr.score(self.root, 1, True))
        self.assertEqual(fr.stats(self.root)["won"], 1)

    def test_corrupt_line_never_takes_the_loop_down(self):
        fr.append_friction(self.root, "a", kind="gap")
        with fr.queue_path(self.root).open("a") as fh:
            fh.write("{not json\n")
        fr.append_friction(self.root, "b", kind="gap")
        self.assertEqual(fr.stats(self.root)["entries"], 2)

    def test_journaling_warning_needs_volume_and_no_wins(self):
        for i in range(12):
            fr.append_friction(self.root, f"f{i}", kind="gap", win="w")
        self.assertIn("journaling", fr.journaling_warning(self.root))
        fr.score(self.root, 0, True)
        self.assertEqual(fr.journaling_warning(self.root), "")

    def test_format_for_dream_carries_economics(self):
        fr.append_friction(self.root, "x", kind="tooling", trigger="t", win="w", mitigation="m")
        text = fr.format_for_dream(fr.pending(self.root))
        for needle in ("[tooling]", "trigger: t", "win: w", "mitigation: m"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
