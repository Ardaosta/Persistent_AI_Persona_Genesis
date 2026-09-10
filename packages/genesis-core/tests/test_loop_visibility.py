"""A background loop must never surface a window.

The Windows heartbeat once ran its .cmd directly in the interactive session and
popped a console every hour, mid-work, at someone who had not asked for it.

These tests run on ANY host and assert the WINDOWS behavior, which is the entire
point. Every OS here hides background work by default except Windows, where
hiding it takes a deliberate extra artifact. So the developer who deletes that
artifact is, almost by definition, not on Windows: they run the suite, it goes
green, and a console window ships to every Windows user. A check that can only
run on the OS that breaks is a check that never runs.
"""

import tempfile
import unittest
from pathlib import Path

from genesis_core import scheduler as sch


class VisibilityCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def good_vbs(self, stem="heartbeat", style="0") -> Path:
        p = self.root / f"{stem}.vbs"
        p.write_text(
            f'CreateObject("WScript.Shell").Run """{self.root}\\{stem}.cmd""", {style}, False\r\n',
            encoding="utf-8",
        )
        return p


class TestTheShippedRegression(VisibilityCase):
    def test_the_public_mirrors_action_is_rejected(self):
        """Locks the exact shape that is live in the public mirror right now:
        schtasks /TR "<wrapper.cmd>", straight into the interactive session."""
        self.good_vbs()
        action = f'"{self.root}\\heartbeat.cmd"'
        problems = sch.audit_visibility("Windows", action, self.root)
        self.assertTrue(problems)
        self.assertTrue(any("wscript" in p for p in problems))

    def test_a_missing_hidden_launcher_is_caught(self):
        action = f'wscript.exe "{self.root}\\heartbeat.vbs"'
        problems = sch.audit_visibility("Windows", action, self.root)
        self.assertTrue(any("never generated" in p for p in problems))

    def test_a_visible_window_style_is_caught(self):
        """Style 1 is a normal visible window. The launcher exists, is wired, is
        invoked through wscript, and still shows itself: the failure that would
        survive every structural check but the value one."""
        self.good_vbs(style="1")
        action = f'wscript.exe "{self.root}\\heartbeat.vbs"'
        problems = sch.audit_visibility("Windows", action, self.root)
        self.assertTrue(any("window style 1" in p for p in problems))

    def test_terminal_emulators_are_caught_on_any_os(self):
        for action in ('osascript -e "do script"', "gnome-terminal -- /x/heartbeat.sh"):
            with self.subTest(action=action):
                self.assertTrue(sch.audit_visibility("Linux", action, self.root))


class TestItPassesWhatItShould(VisibilityCase):
    """A check that fails on correct configuration gets disabled, and then it is
    not a check."""

    def test_the_real_windows_action_passes(self):
        self.good_vbs()
        action = f'wscript.exe "{self.root}\\heartbeat.vbs"'
        self.assertEqual(sch.audit_visibility("Windows", action, self.root), [])

    def test_the_real_mailcheck_action_passes(self):
        self.good_vbs(stem="mailcheck")
        action = f'wscript.exe "{self.root}\\mailcheck.vbs"'
        self.assertEqual(sch.audit_visibility("Windows", action, self.root, "mailcheck"), [])

    def test_launchd_and_cron_actions_pass(self):
        for sysname, action in (("Darwin", f"{self.root}/heartbeat.sh"),
                                ("Linux", f'"{self.root}/heartbeat.sh"')):
            with self.subTest(sysname=sysname):
                self.assertEqual(sch.audit_visibility(sysname, action, self.root), [])


class TestTheGeneratorSatisfiesItsOwnInvariant(VisibilityCase):
    def test_generated_windows_artifacts_pass_the_audit(self):
        """End to end: what generate_wrapper actually writes for Windows must
        satisfy the rule, checked here from whatever host is running the suite."""
        import platform as _pl
        real = _pl.system
        _pl.system = lambda: "Windows"
        try:
            wrapper = sch.generate_wrapper(self.root, "/x", "/usr/bin/python3")
        finally:
            _pl.system = real
        vbs = wrapper.with_suffix(".vbs")
        self.assertTrue(vbs.is_file(), "the hidden launcher must be generated alongside the .cmd")
        action = f'wscript.exe "{vbs}"'
        self.assertEqual(sch.audit_visibility("Windows", action, self.root, wrapper.stem), [])

    def test_assert_invisible_refuses_rather_than_warns(self):
        self.good_vbs()
        with self.assertRaises(sch.VisibleLoopError):
            sch.assert_invisible("Windows", f'"{self.root}\\heartbeat.cmd"', self.root)


if __name__ == "__main__":
    unittest.main()
