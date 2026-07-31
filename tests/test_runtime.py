import tempfile
import unittest
from pathlib import Path

from umml_runtime.client import RuntimeClient
from umml_runtime.protocol import CompatibilityGate, ProtocolError, decode_message
from umml_runtime.server import RuntimeBridgeServer


class RuntimeTests(unittest.TestCase):
    def test_unknown_build_fails_closed(self):
        gate = CompatibilityGate({"known": {"texture_reload"}})
        self.assertEqual(gate.check("unknown").features, frozenset())

    def test_invalid_protocol_is_rejected(self):
        with self.assertRaises(ProtocolError):
            decode_message(b'{"protocol":99,"command":"hello"}')

    def test_loopback_server_auth_and_feature_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            server = RuntimeBridgeServer(temp, gate=CompatibilityGate({"build-a": {"texture_reload"}}))
            server.start()
            host, port = server.address
            try:
                bad = RuntimeClient(host, port, "wrong").request("hello", build="build-a")
                self.assertFalse(bad["ok"])
                client = RuntimeClient(host, port, server.token)
                known = client.request("hello", build="build-a")
                self.assertEqual(known["features"], ["texture_reload"])
                unknown = client.request("hello", build="new-build")
                self.assertEqual(unknown["mode"], "disabled")
            finally:
                server.close()

    def test_profile_change_is_queued_not_applied_in_process(self):
        with tempfile.TemporaryDirectory() as temp:
            server = RuntimeBridgeServer(temp)
            response = server.dispatch({
                "protocol": 1,
                "command": "queue_profile",
                "token": server.token,
                "build": "unknown",
                "profile": "Dark",
            })
            self.assertTrue(response["pending_restart"])
            self.assertTrue((Path(temp) / "runtime-pending.json").is_file())
            server._server.server_close()


if __name__ == "__main__":
    unittest.main()
