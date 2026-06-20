"""Scheduler: portable pause/resume sentinel, per-OS wrapper generation, status
state machine, and the heartbeat honoring the pause sentinel."""

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_core import scheduler as sch


class TestPauseSentinel(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_pause_creates_sentinel_resume_removes(self):
        self.assertFalse(sch.is_paused(self.root))
        sch.pause(self.root)
        self.assertTrue(sch.is_paused(self.root))
        self.assertTrue(sch.pause_sentinel(self.root).exists())
        self.assertTrue(sch.resume(self.root))  # was paused
        self.assertFalse(sch.is_paused(self.root))

    def test_resume_when_not_paused_returns_false(self):
        self.assertFalse(sch.resume(self.root))

    def test_pause_is_idempotent(self):
        sch.pause(self.root)
        first = sch.pause_sentinel(self.root).read_text()
        sch.pause(self.root)  # must not overwrite the original stamp
        self.assertEqual(first, sch.pause_sentinel(self.root).read_text())


class TestWrapperGeneration(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_posix_wrapper(self):
        with mock.patch.object(sch.platform, "system", return_value="Darwin"):
            w = sch.generate_wrapper(self.root, "/a:/b", "/usr/bin/python3")
        self.assertEqual(w.name, "heartbeat.sh")
        text = w.read_text()
        self.assertIn("genesis_core.cli heartbeat", text)
        self.assertIn('export GENESIS_ROOT', text)
        self.assertIn("/usr/bin/python3", text)

    def test_windows_wrapper(self):
        with mock.patch.object(sch.platform, "system", return_value="Windows"):
            w = sch.generate_wrapper(self.root, r"C:\a;C:\b", r"C:\Python\python.exe")
        self.assertEqual(w.name, "heartbeat.cmd")
        text = w.read_text()
        self.assertIn("genesis_core.cli heartbeat %*", text)
        self.assertIn('set "GENESIS_ROOT=', text)
        self.assertIn(r"C:\Python\python.exe", text)


class TestStatusState(unittest.TestCase):
    def test_state_logic(self):
        s = sch.ScheduleStatus("Darwin", registered=False, paused=False, detail="")
        self.assertEqual(s.state, "not scheduled")
        s = sch.ScheduleStatus("Darwin", registered=True, paused=False, detail="")
        self.assertEqual(s.state, "running")
        s = sch.ScheduleStatus("Darwin", registered=True, paused=True, detail="")
        self.assertEqual(s.state, "paused")


class TestSchedulerFactory(unittest.TestCase):
    def test_factory_picks_backend_by_os(self):
        with mock.patch.object(sch.platform, "system", return_value="Darwin"):
            self.assertIsInstance(sch.get_scheduler("/tmp/x"), sch.LaunchdScheduler)
        with mock.patch.object(sch.platform, "system", return_value="Windows"):
            self.assertIsInstance(sch.get_scheduler("/tmp/x"), sch.WindowsScheduler)
        with mock.patch.object(sch.platform, "system", return_value="Linux"):
            self.assertIsInstance(sch.get_scheduler("/tmp/x"), sch.CronScheduler)


class TestWindowsSchedulerCommands(unittest.TestCase):
    """The Windows backend builds the right schtasks calls without a real Windows."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_install_invokes_schtasks_create(self):
        s = sch.WindowsScheduler(self.root, python=r"C:\py\python.exe")
        wrapper = self.root / "heartbeat.cmd"
        wrapper.write_text("@echo off\n")
        with mock.patch.object(sch.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="SUCCESS", stderr="")
            ok, detail = s._install_os_job(wrapper)
        self.assertTrue(ok)
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "schtasks")
        self.assertIn("/Create", argv)
        self.assertIn(sch.WINDOWS_TASK_NAME, argv)
        self.assertIn("/SC", argv)
        self.assertIn("HOURLY", argv)


class TestHeartbeatHonorsPause(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_heartbeat_skips_when_paused(self):
        from genesis_core import cli
        from genesis_core import config as cfgmod
        sch.pause(self.root)
        cfg = cfgmod.GenesisConfig(root=self.root)
        with mock.patch.object(cfgmod, "load", return_value=cfg), \
             mock.patch.object(cli, "cmd_dream") as dream, \
             mock.patch.object(cli, "cmd_learn") as learn:
            rc = cli.cmd_heartbeat(argparse.Namespace())
        self.assertEqual(rc, 0)
        dream.assert_not_called()
        learn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
