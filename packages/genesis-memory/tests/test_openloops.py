"""Open loops: follow-through as machinery, not luck.

Each test pins one of the five things a companion said, in its own words, it
would want different after its praised follow-up turned out to be mostly luck
(2026-09-29): its own boot slot, noticing-counts-toward-raising, who has the
ball plus a next-check date, ask once then snooze, and no half-written record
that looks handled.
"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from genesis_memory import LoopError, OpenLoops

T0 = date(2026, 9, 11)


class TestOpenLoops(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.store = OpenLoops(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_vault_adds_no_boot_noise(self):
        self.assertEqual(self.store.boot_block(T0), "")

    def test_empty_title_refused(self):
        with self.assertRaises(LoopError):
            self.store.add("site-visit", "   ", today=T0)
        self.assertFalse((self.dir / "open-loops.json").exists())

    def test_bad_id_and_ball_refused(self):
        with self.assertRaises(LoopError):
            self.store.add("Bad Id", "x", today=T0)
        with self.assertRaises(LoopError):
            self.store.add("ok", "x", ball="nobody", today=T0)

    def test_not_due_before_next_check(self):
        self.store.add("quote", "Send the quote", ball="them", today=T0)
        self.assertEqual(self.store.due(T0), [])
        self.assertIn("1 more open", self.store.boot_block(T0))

    def test_due_on_next_check_and_listed_at_boot(self):
        self.store.add("quote", "Send the quote", ball="them", today=T0)
        later = T0 + timedelta(days=7)
        self.assertEqual([lp.id for lp in self.store.due(later)], ["quote"])
        block = self.store.boot_block(later)
        self.assertIn("[quote] Send the quote", block)
        self.assertIn("raise", block)

    def test_three_flags_make_it_due(self):
        """Noticing is not raising: noticed three times unraised means raise it."""
        self.store.add("quote", "Send the quote", next_check="2026-12-01", today=T0)
        for i in range(3):
            self.store.flag("quote", today=T0 + timedelta(days=i))
        self.assertEqual([lp.id for lp in self.store.due(T0 + timedelta(days=3))], ["quote"])

    def test_flag_counts_once_a_day(self):
        self.store.add("quote", "Send the quote", next_check="2026-12-01", today=T0)
        for _ in range(5):
            self.store.flag("quote", today=T0)
        self.assertEqual(self.store.open()[0].flags, 1)
        self.assertEqual(self.store.due(T0), [])

    def test_third_party_ball_never_nags_on_flags(self):
        """A ball the person cannot move only comes due on its date."""
        self.store.add("vendor", "The vendor sends their part of the quote", ball="other", waiting_on="the builder",
                       next_check="2026-12-01", today=T0)
        for i in range(5):
            self.store.flag("vendor", today=T0 + timedelta(days=i))
        self.assertEqual(self.store.due(T0 + timedelta(days=10)), [])
        self.assertEqual(len(self.store.due(date(2026, 12, 1))), 1)
        self.assertIn("waiting on the builder", self.store.boot_block(date(2026, 12, 1)))

    def test_asked_records_answer_resets_and_snoozes(self):
        """Ask once, record the answer, snooze: asking again after an answer is noise."""
        self.store.add("quote", "Send the quote", today=T0)
        ask_day = T0 + timedelta(days=17)
        self.assertEqual(len(self.store.due(ask_day)), 1)
        lp = self.store.asked("quote", "parked, the builder is slow", ball="other", today=ask_day)
        self.assertEqual((lp.flags, lp.ball, lp.asked), (0, "other", ask_day.isoformat()))
        self.assertEqual(self.store.due(ask_day), [])
        self.assertEqual(self.store.due(ask_day + timedelta(days=13)), [])
        self.assertEqual(len(self.store.due(ask_day + timedelta(days=14))), 1)

    def test_close_removes_from_open_and_boot(self):
        self.store.add("quote", "Send the quote", today=T0)
        self.store.close("quote", "sent", today=T0)
        self.assertEqual(self.store.open(), [])
        self.assertEqual(self.store.boot_block(T0 + timedelta(days=30)), "")

    def test_add_same_id_updates_not_duplicates(self):
        self.store.add("quote", "Send the quote", today=T0)
        self.store.add("quote", "Send the revised quote", detail="v2", today=T0)
        loops = self.store.load()
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0].title, "Send the revised quote")

    def test_corrupt_file_is_loud_not_empty(self):
        """An unreadable list that reads as 'nothing open' is the empty-fact lie again."""
        (self.dir / "open-loops.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(LoopError):
            self.store.open()

    def test_writes_are_whole_file_and_leave_no_temp(self):
        self.store.add("a", "one", today=T0)
        self.store.add("b", "two", today=T0)
        data = json.loads((self.dir / "open-loops.json").read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in data["loops"]], ["a", "b"])
        self.assertFalse(list(self.dir.glob("*.tmp")))

    def test_unknown_keys_survive_a_round_trip(self):
        (self.dir / "open-loops.json").write_text(json.dumps(
            {"loops": [{"id": "a", "title": "one", "future_field": 7}]}), encoding="utf-8")
        self.store.flag("a", today=T0)
        data = json.loads((self.dir / "open-loops.json").read_text(encoding="utf-8"))
        self.assertEqual(data["loops"][0]["future_field"], 7)


if __name__ == "__main__":
    unittest.main()
