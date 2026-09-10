"""Stdlib-unittest tests for the MCP transport and the GENESIS_ROOT guard.

The protocol tests use a fake bridge so they run without genesis-core installed.
The guard tests are the ones that matter most: refusing to start on an unresolved
root is the whole reason this file exists, because the failure it prevents is
silent.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from genesis_mcp import server as srv  # noqa: E402


class FakeBridge:
    def __init__(self, reply="ok", raises=None):
        self.reply = reply
        self.raises = raises
        self.calls = []

    def tool_schemas(self):
        return [{"name": "recall", "description": "d", "inputSchema": {"type": "object"}}]

    def call(self, name, args):
        self.calls.append((name, args))
        if self.raises:
            raise self.raises
        return self.reply


def run(lines, bridge=None):
    bridge = bridge or FakeBridge()
    out = io.StringIO()
    srv.serve(stdin=io.StringIO("".join(l + "\n" for l in lines)), stdout=out, bridge=bridge)
    return [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]


class TestRootGuard(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("GENESIS_ROOT")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("GENESIS_ROOT", None)
        else:
            os.environ["GENESIS_ROOT"] = self._saved

    def test_unset_root_refuses(self):
        os.environ.pop("GENESIS_ROOT", None)
        with self.assertRaises(srv.GenesisRootError):
            srv.resolve_root()

    def test_blank_root_refuses(self):
        os.environ["GENESIS_ROOT"] = "   "
        with self.assertRaises(srv.GenesisRootError):
            srv.resolve_root()

    def test_missing_dir_refuses(self):
        os.environ["GENESIS_ROOT"] = "/nope/not/here/at/all"
        with self.assertRaises(srv.GenesisRootError):
            srv.resolve_root()

    def test_dir_without_vault_refuses(self):
        """A real directory that is not a companion home is the dangerous case:
        it exists, so a laxer check would accept it and then quietly write facts
        into the wrong tree."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["GENESIS_ROOT"] = d
            with self.assertRaises(srv.GenesisRootError):
                srv.resolve_root()

    def test_valid_root_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "vault").mkdir()
            os.environ["GENESIS_ROOT"] = d
            self.assertEqual(srv.resolve_root(), Path(d))


class TestProtocol(unittest.TestCase):
    def test_initialize_echoes_client_version(self):
        resp = run([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                "params": {"protocolVersion": "2099-01-01"}})])
        self.assertEqual(resp[0]["result"]["protocolVersion"], "2099-01-01")
        self.assertEqual(resp[0]["result"]["serverInfo"]["name"], "genesis")

    def test_initialize_without_version_uses_fallback(self):
        resp = run([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})])
        self.assertEqual(resp[0]["result"]["protocolVersion"], srv.FALLBACK_PROTOCOL_VERSION)

    def test_notification_gets_no_response(self):
        resp = run([json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})])
        self.assertEqual(resp, [])

    def test_tools_list(self):
        resp = run([json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})])
        names = [t["name"] for t in resp[0]["result"]["tools"]]
        self.assertEqual(names, ["recall"])

    def test_tools_call_routes_args(self):
        b = FakeBridge(reply="dog-vin: an aging wolfhound")
        resp = run([json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                "params": {"name": "recall", "arguments": {"query": "vin"}}})], b)
        self.assertEqual(b.calls, [("recall", {"query": "vin"})])
        self.assertEqual(resp[0]["result"]["content"][0]["text"], "dog-vin: an aging wolfhound")
        self.assertNotIn("isError", resp[0]["result"])

    def test_tool_failure_is_a_tool_error_not_a_dead_server(self):
        """A broken tool should reach the model as text it can talk about, rather
        than looking like the whole companion went away."""
        b = FakeBridge(raises=RuntimeError("vault unreadable"))
        resp = run([json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                "params": {"name": "recall", "arguments": {}}})], b)
        self.assertTrue(resp[0]["result"]["isError"])
        self.assertIn("vault unreadable", resp[0]["result"]["content"][0]["text"])

    def test_unknown_method_errors(self):
        resp = run([json.dumps({"jsonrpc": "2.0", "id": 5, "method": "nope/nope"})])
        self.assertEqual(resp[0]["error"]["code"], srv.METHOD_NOT_FOUND)

    def test_bad_json_does_not_kill_the_loop(self):
        resp = run(["{not json", json.dumps({"jsonrpc": "2.0", "id": 6, "method": "ping"})])
        self.assertEqual(resp[0]["error"]["code"], srv.PARSE_ERROR)
        self.assertEqual(resp[1]["id"], 6)

    def test_blank_lines_ignored(self):
        resp = run(["", "   ", json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"})])
        self.assertEqual(len(resp), 1)


if __name__ == "__main__":
    unittest.main()
