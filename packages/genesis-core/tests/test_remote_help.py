"""Remote help: consented public keys parked by init, the privileged step
generated from one source, and everything it adds marked so it can be removed."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_core import remote_help as rh

# Synthetic keys: the right shape, not anyone's real key.
GOOD = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyBodyNotARealKey0000000000000000000 helper@example"
GOOD2 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAnotherExampleKeyBodyNotReal111111111111111111 second@example"


class TestParking(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_only_consented_valid_keys_are_parked(self):
        self.assertIsNone(rh.park_keys(self.root, {"keys": [GOOD], "consented": False}))
        self.assertIsNone(rh.park_keys(self.root, {"keys": ["junk"], "consented": True}))
        self.assertEqual(rh.parked(self.root), [])
        p = rh.park_keys(self.root, {"keys": [GOOD, "junk", GOOD2, GOOD], "consented": True})
        self.assertEqual(p.name, rh.KEYS_FILE)
        self.assertEqual(rh.parked(self.root), [GOOD, GOOD2])


class TestWindowsScript(unittest.TestCase):
    def test_script_carries_tagged_keys_marker_and_removal(self):
        d = Path("C:/Users/x/AppData/Local/Genesis")
        s = rh.windows_enable_script('Morgan "the" Sponsor', [GOOD], d)
        self.assertIn(GOOD + " " + rh.SUFFIX, s)
        self.assertNotIn('"the"', s)                       # quotes stripped from the name
        self.assertIn("administrators_authorized_keys", s)
        self.assertIn("icacls", s)
        self.assertIn("remote-help.json", s)
        self.assertIn("Remove-RemoteHelp.ps1", s)
        self.assertIn("exit 0", s)
        # the removal script is embedded verbatim and only strips OUR lines
        r = rh.windows_remove_script()
        self.assertIn(" " + rh.SUFFIX + "$", r)
        self.assertIn(r.strip().splitlines()[0], s)
        # no em dashes anywhere in generated text (a house rule the gate enforces on files)
        self.assertNotIn("\u2014", s)

    def test_windows_enable_runs_elevated_and_returns_code(self):
        with tempfile.TemporaryDirectory() as td:
            calls = []

            def fake_run(cmd, **kw):
                calls.append(cmd)
                return mock.Mock(returncode=0)
            code = rh.windows_enable("Morgan", [GOOD], Path(td), run=fake_run)
            self.assertEqual(code, 0)
            self.assertTrue((Path(td) / "enable-remote-help.ps1").is_file())
            self.assertIn("RunAs", " ".join(calls[0]))


class TestPosix(unittest.TestCase):
    def test_posix_enable_writes_keys_marker_and_remover(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            home.mkdir()
            ak = home / ".ssh" / "authorized_keys"
            (home / ".ssh").mkdir()
            ak.write_text("ssh-ed25519 AAAA existing@host\n")
            ran = []
            with mock.patch.object(Path, "home", staticmethod(lambda: home)), \
                 mock.patch.object(rh.platform, "system", return_value="Darwin"):
                out = rh.posix_enable("Morgan", [GOOD], Path(td),
                                      run=lambda cmd, **kw: (ran.append(cmd), mock.Mock(returncode=0))[1])
            lines = ak.read_text().splitlines()
            self.assertEqual(lines[0], "ssh-ed25519 AAAA existing@host")   # kept
            self.assertEqual(lines[1], GOOD + " " + rh.SUFFIX)
            self.assertEqual(stat.S_IMODE(os.stat(ak).st_mode), 0o600)
            self.assertEqual(ran[0][:2], ["sudo", "systemsetup"])
            self.assertEqual(out["note"], "remote login on")
            st = rh.status(Path(td))
            self.assertEqual(st["name"], "Morgan")
            remover = (Path(td) / "remove-remote-help.sh").read_text()
            self.assertIn(rh.SUFFIX, remover)
            # idempotent: a second enable does not duplicate the key
            with mock.patch.object(Path, "home", staticmethod(lambda: home)), \
                 mock.patch.object(rh.platform, "system", return_value="Linux"):
                rh.posix_enable("Morgan", [GOOD], Path(td), run=lambda *a, **k: mock.Mock(returncode=0))
            self.assertEqual(ak.read_text().count(GOOD), 1)

    def test_status_none_when_never_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(rh.status(Path(td)))


if __name__ == "__main__":
    unittest.main()
