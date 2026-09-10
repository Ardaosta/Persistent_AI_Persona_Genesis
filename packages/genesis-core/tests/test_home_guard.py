"""The silent vault fork (KNOWN_ISSUES-silent-vault-fork.md).

A bare command with GENESIS_ROOT unset used to mkdir a fresh empty ~/.genesis and
write facts into it, forking a live agent away from its own memory. It happened
to a real person twice: nine facts, the wrong name and two days the first time,
ten more facts the second. These tests hold the three fixes in place.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_core import config as c


class HomeGuardCase(unittest.TestCase):
    """Every test runs against a fake home directory, never the developer's own."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._home_patch = mock.patch.object(Path, "home", staticmethod(lambda: self.home))
        self._home_patch.start()
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("GENESIS_ROOT", None)

    def tearDown(self):
        self._env.stop()
        self._home_patch.stop()
        self._tmp.cleanup()

    def provision(self, path: Path) -> Path:
        """A home that looks real the way a real one does: a config and a fact."""
        (path / "vault").mkdir(parents=True, exist_ok=True)
        (path / "config.json").write_text('{"provider": "anthropic"}', encoding="utf-8")
        (path / "vault" / "her-name.md").write_text("# a fact worth losing\n", encoding="utf-8")
        return path


class TestRefusesToInventAHome(HomeGuardCase):
    def test_bare_command_refuses_instead_of_forking(self):
        with self.assertRaises(c.HomeNotFound) as ctx:
            c.resolve_root()
        msg = str(ctx.exception)
        self.assertIn("GENESIS_ROOT", msg)  # names the fix, not just the symptom
        self.assertFalse((self.home / ".genesis").exists(), "refusal must not create anything")

    def test_refusal_points_at_the_real_home_when_there_is_one(self):
        real = self.provision(self.home / "Wren")  # the shape of the actual incident
        with self.assertRaises(c.HomeNotFound) as ctx:
            c.resolve_root()
        self.assertIn(str(real), str(ctx.exception))

    def test_load_is_guarded_too_not_just_the_cli(self):
        # The guard lives at the chokepoint, so every surface inherits it: the CLI,
        # the MCP server, and the agent's own tools all come through load().
        with self.assertRaises(c.HomeNotFound):
            c.load()


class TestStillWorksWhenItShould(HomeGuardCase):
    def test_explicit_env_var_wins_when_it_points_at_a_real_home(self):
        target = self.provision(self.home / "somewhere-else")
        os.environ["GENESIS_ROOT"] = str(target)
        self.assertEqual(c.resolve_root(), target)

    def test_a_stale_pin_is_refused_rather_than_rebuilt(self):
        """The way the guard could be walked around through its own front door.
        A GENESIS_ROOT left pointing at a moved or deleted folder used to be
        trusted, and the empty home would be mkdir'd back into existence: the
        exact fork, arrived at by a different road."""
        gone = self.home / "deleted-by-a-cleanup"
        os.environ["GENESIS_ROOT"] = str(gone)
        with self.assertRaises(c.HomeNotFound) as ctx:
            c.resolve_root()
        self.assertIn("does not exist", str(ctx.exception))
        self.assertFalse(gone.exists())

    def test_a_stale_pin_still_points_at_the_real_home_when_there_is_one(self):
        real = self.provision(self.home / "Wren")
        os.environ["GENESIS_ROOT"] = str(self.home / "gone")
        with self.assertRaises(c.HomeNotFound) as ctx:
            c.resolve_root()
        self.assertIn(str(real), str(ctx.exception))

    def test_init_may_still_create_at_an_explicit_path(self):
        target = self.home / "brand-new"
        os.environ["GENESIS_ROOT"] = str(target)
        self.assertEqual(c.resolve_root(creating=True), target)

    def test_provisioned_default_home_resolves_normally(self):
        self.provision(self.home / ".genesis")
        self.assertEqual(c.resolve_root(), self.home / ".genesis")

    def test_setup_commands_may_create(self):
        self.assertEqual(c.resolve_root(creating=True), self.home / ".genesis")

    def test_marker_alone_counts_as_provisioned(self):
        # An upgraded home with a marker but no facts yet is still a home, not a
        # missing one: the guard must never strand someone mid-setup.
        root = self.home / ".genesis"
        root.mkdir()
        c.write_home_marker(root)
        self.assertTrue(c.is_provisioned(root))
        self.assertEqual(c.resolve_root(), root)


class TestForkDetection(HomeGuardCase):
    def test_finds_a_second_home_one_level_down(self):
        self.provision(self.home / ".genesis")
        real = self.provision(self.home / "Wren")
        found = c.find_homes(exclude=self.home / ".genesis")
        self.assertIn(str(real), [str(f) for f in found])

    def test_excludes_the_active_home(self):
        active = self.provision(self.home / ".genesis")
        self.assertNotIn(str(active), [str(f) for f in c.find_homes(exclude=active)])

    def test_empty_directories_are_not_homes(self):
        (self.home / "Downloads").mkdir()
        (self.home / "Documents").mkdir()
        self.assertEqual(c.find_homes(), [])


class TestDurablePointer(HomeGuardCase):
    def test_marker_records_provenance_and_never_overwrites(self):
        root = self.home / ".genesis"
        root.mkdir()
        path = c.write_home_marker(root)
        first = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(first["path"], str(root))
        self.assertTrue(first["created_at"])
        self.assertTrue(first["host"])
        c.write_home_marker(root)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), first,
                         "the ORIGINAL creation stamp is the evidence; keep it")

    @unittest.skipIf(os.name == "nt", "POSIX profile path")
    def test_pointer_pins_the_home_in_the_shell_profile(self):
        root = self.provision(self.home / "Wren")
        with mock.patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            ok, detail = c.write_home_pointer(root)
        self.assertTrue(ok, detail)
        body = (self.home / ".zshrc").read_text(encoding="utf-8")
        self.assertIn(f'export GENESIS_ROOT="{root}"', body)

    @unittest.skipIf(os.name == "nt", "POSIX profile path")
    def test_pointer_is_idempotent_and_repoints_cleanly(self):
        first = self.provision(self.home / "Wren")
        second = self.provision(self.home / "Sable")
        (self.home / ".zshrc").write_text("# the user's own setup\nalias ll='ls -la'\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            c.write_home_pointer(first)
            c.write_home_pointer(first)
            c.write_home_pointer(second)
        body = (self.home / ".zshrc").read_text(encoding="utf-8")
        self.assertEqual(body.count("export GENESIS_ROOT"), 1, "one pin, not a pile")
        self.assertIn(f'export GENESIS_ROOT="{second}"', body)
        self.assertIn("alias ll=", body, "the user's own profile must survive")


if __name__ == "__main__":
    unittest.main()
