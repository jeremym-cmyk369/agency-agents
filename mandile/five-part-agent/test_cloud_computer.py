"""Offline tests for Orgo cloud-computer control. Never provisions a real VM."""
import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from cloud_computer import ComputerSpec, OrgoCloud, main, safe_summary

WORKSPACE = "550e8400-e29b-41d4-a716-446655440000"
COMPUTER = "a3bb189e-8bf9-3888-9912-ace4e6543002"

class Response:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, *args):
        return json.dumps({"id": COMPUTER, "vnc_password": "secret", "status": "running"}).encode()

class CloudTests(unittest.TestCase):
    def test_tenant_and_agent_name(self):
        spec = ComputerSpec("client_a", "lead_recovery", WORKSPACE)
        self.assertEqual(spec.name, "mandile-client_a-lead_recovery")
        self.assertEqual(spec.create_payload()["os"], "linux")

    def test_plan_no_network(self):
        out = StringIO()
        with patch.object(sys, "argv", ["cloud_computer.py", "create", "--workspace-id", WORKSPACE]):
            with patch("cloud_computer.urlopen", side_effect=AssertionError("network used")):
                with redirect_stdout(out): main()
        self.assertEqual(json.loads(out.getvalue())["mode"], "DRY_RUN")

    def test_actual_api_shape_mocked(self):
        recorded = {}
        def fake_urlopen(req, timeout):
            recorded["url"] = req.full_url
            recorded["auth"] = req.get_header("Authorization")
            recorded["body"] = json.loads(req.data)
            recorded["idempotency"] = req.get_header("Idempotency-key")
            return Response()
        with patch("cloud_computer.urlopen", side_effect=fake_urlopen):
            result = OrgoCloud("test-key").create(ComputerSpec("client_a", "agent", WORKSPACE))
        self.assertEqual(recorded["url"], "https://www.orgo.ai/api/computers")
        self.assertEqual(recorded["body"]["workspace_id"], WORKSPACE)
        self.assertEqual(recorded["auth"], "Bearer test-key")
        self.assertTrue(recorded["idempotency"])
        self.assertNotIn("vnc_password", result)

    def test_sanitizes_secrets(self):
        self.assertEqual(safe_summary({"id": COMPUTER, "vnc_password": "secret"}), {"id": COMPUTER})

    def test_invalid_tenant_and_id_rejected(self):
        with self.assertRaises(ValueError):
            ComputerSpec("../../oops", "agent", WORKSPACE)
        with self.assertRaises(ValueError):
            OrgoCloud("key").stop("../../oops")

    def test_key_required_for_live_actions(self):
        with self.assertRaises(ValueError):
            OrgoCloud("")

if __name__ == "__main__":
    unittest.main()
