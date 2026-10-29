"""Offline safety tests: python -m unittest discover -s . -p 'test_*.py'"""
import unittest

from agent import AgentHarness, Memory


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        self.agent = AgentHarness(self.memory)
        self.event = {"event_id": "call_1", "phone": "+16235550100", "business": "Test Plumbing", "service": "water heater"}

    def test_dry_run_never_sends(self):
        result = self.agent.handle_missed_call("tenant_a", self.event)
        self.assertEqual(result["delivery"], "never_sent")
        self.assertEqual(self.memory.list_proposals("tenant_a")[0]["state"], "pending_approval")

    def test_idempotency(self):
        self.agent.handle_missed_call("tenant_a", self.event)
        self.assertEqual(self.agent.handle_missed_call("tenant_a", self.event)["result"], "duplicate_ignored")
        self.assertEqual(len(self.memory.list_proposals("tenant_a")), 1)

    def test_tenant_isolation_and_approval(self):
        self.agent.handle_missed_call("tenant_a", self.event)
        self.assertEqual(self.memory.list_proposals("tenant_b"), [])
        self.assertFalse(self.memory.approve("tenant_b", "call_1"))
        self.assertTrue(self.memory.approve("tenant_a", "call_1"))
        self.assertEqual(self.memory.list_proposals("tenant_a")[0]["state"], "approved_not_sent")

    def test_invalid_phone_is_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.handle_missed_call("tenant_a", {**self.event, "phone": "DROP TABLE"})


if __name__ == "__main__":
    unittest.main()
