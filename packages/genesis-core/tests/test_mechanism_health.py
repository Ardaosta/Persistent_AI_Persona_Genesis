"""Is every loop that maintains this AI actually firing?

From an audit that found four mechanisms green by their own account and dead by
their logs. The rule under all of it: `last_fired` comes from primary evidence,
never from the mechanism's own status output.
"""

import json
import os
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from genesis_core import config as cfgmod
from genesis_core import mechanism_health as mh

HOUR = 3600


class HealthCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "vault" / "journal").mkdir(parents=True)
        (self.root / "vault" / "findings").mkdir(parents=True)
        self.cfg = cfgmod.GenesisConfig(root=self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def aged(self, path: Path, hours: float, body: str = "x") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        when = time.time() - hours * HOUR
        os.utime(path, (when, when))
        return path

    def by_name(self, name: str) -> dict:
        return {m["mechanism"]: m for m in mh.collect(self.cfg)}[name]


class TestTheLyingLoop(HealthCase):
    """A fresh self-report on stale evidence is not a late loop."""

    def test_a_daykey_with_no_journal_is_failed_not_ok(self):
        self.aged(self.root / "daykeys" / f"{date.today()}.txt", 0.1)
        d = self.by_name("dream")
        self.assertEqual(d["status"], "failed")
        self.assertIsNone(d["last_fired"], "the claim must never become last_fired")
        # the claim is carried, clearly labelled as a claim, and kept out of last_fired
        self.assertTrue(d["self_reported"])
        self.assertNotEqual(d["self_reported"], d["last_fired"])

    def test_evidence_is_the_journal_never_the_daykey(self):
        self.aged(self.root / "daykeys" / f"{date.today()}.txt", 0.1)
        self.aged(self.root / "vault" / "journal" / "2026-08-18.md", 0.2)
        d = self.by_name("dream")
        self.assertEqual(d["status"], "ok")
        self.assertIn("journal", d["evidence_path"])
        self.assertNotIn("daykey", d["evidence_path"])

    def test_both_stale_is_stale_not_failed(self):
        """Nothing is lying here, the loop is just overdue. Calling this failed
        would spend the word on the ordinary case and leave nothing for the
        contradiction that actually matters."""
        self.aged(self.root / "daykeys" / "2026-01-01.txt", 100)
        self.aged(self.root / "vault" / "journal" / "old.md", 100)
        self.assertEqual(self.by_name("dream")["status"], "stale")

    def test_learn_claiming_a_day_with_no_finding_is_failed(self):
        (self.root / "outward_state.json").write_text(
            json.dumps({"last_learn_day": date.today().isoformat()}), encoding="utf-8")
        e = self.by_name("learn")
        self.assertEqual(e["status"], "failed")
        self.assertIsNone(e["last_fired"])

    def test_learn_with_a_real_finding_is_ok(self):
        (self.root / "outward_state.json").write_text(
            json.dumps({"last_learn_day": date.today().isoformat()}), encoding="utf-8")
        self.aged(self.root / "vault" / "findings" / "f.md", 1)
        self.assertEqual(self.by_name("learn")["status"], "ok")


class TestNeverFiredIsNotUnreachable(HealthCase):
    """Collapsing these turns 'I cannot see' into 'it is not there'."""

    def test_a_readable_empty_directory_is_never_fired(self):
        self.assertEqual(self.by_name("dream")["status"], "never_fired")

    def test_an_unreadable_directory_is_unreachable(self):
        hyg = self.root / "hygiene"
        hyg.mkdir()
        os.chmod(hyg, 0o000)
        try:
            e = self.by_name("graph_hygiene")
            if os.geteuid() == 0:
                self.skipTest("root reads anything, so this cannot be provoked")
            self.assertEqual(e["status"], "unreachable")
            self.assertIn("vantage point", e["note"])
        finally:
            os.chmod(hyg, 0o755)

    def test_never_fired_does_not_count_as_a_finding(self):
        """On a fresh install every loop is never_fired. A health check that goes
        red on a brand new machine is one the person learns to disregard before
        it ever means anything."""
        snap = mh.snapshot(self.cfg)
        self.assertTrue(all(m["status"] == "never_fired" for m in snap["mechanisms"]))
        self.assertEqual(mh.findings(snap), [])

    def test_a_never_fired_entry_points_at_the_expected_artifact(self):
        e = self.by_name("capture")
        self.assertTrue(e["evidence_path"].endswith("capture_queue.jsonl"))


class TestPerMechanismWindows(HealthCase):
    """One global freshness number cannot be right for both an hourly heartbeat
    and a capture queue where ten quiet days is healthy."""

    def test_capture_is_quiet_for_days_without_complaint(self):
        self.aged(self.root / "capture_queue.jsonl", 24 * 5)
        self.assertEqual(self.by_name("capture")["status"], "ok")

    def test_capture_finally_flags_past_its_own_window(self):
        self.aged(self.root / "capture_queue.jsonl", 24 * 11)
        self.assertEqual(self.by_name("capture")["status"], "stale")

    def test_the_same_age_means_different_things_per_mechanism(self):
        age = 24 * 5
        self.aged(self.root / "capture_queue.jsonl", age)
        self.aged(self.root / "heartbeat.log", age)
        self.assertEqual(self.by_name("capture")["status"], "ok")
        self.assertEqual(self.by_name("heartbeat")["status"], "stale")


class TestTheSnapshotJudgesItself(HealthCase):
    def test_an_old_snapshot_is_itself_a_finding(self):
        snap = mh.snapshot(self.cfg)
        old = datetime.now() - timedelta(hours=mh.SNAPSHOT_STALE_HOURS + 5)
        snap["generated_at"] = old.isoformat(timespec="seconds")
        found = mh.findings(snap)
        self.assertTrue(found)
        self.assertIn("history", found[0], "and it is listed FIRST, before the mechanisms")

    def test_an_unreadable_generated_at_is_a_finding_too(self):
        snap = mh.snapshot(self.cfg)
        snap["generated_at"] = "not a timestamp"
        self.assertTrue(any("generated_at" in f for f in mh.findings(snap)))

    def test_every_entry_carries_an_evidence_path(self):
        for m in mh.snapshot(self.cfg)["mechanisms"]:
            with self.subTest(mechanism=m["mechanism"]):
                self.assertTrue(m["evidence_path"])
                self.assertIn(m["status"], mh.STATUSES)

    def test_write_snapshot_round_trips(self):
        path = mh.write_snapshot(self.cfg)
        again = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(again["schema"], mh.SCHEMA)
        self.assertTrue(again["mechanisms"])


if __name__ == "__main__":
    unittest.main()
