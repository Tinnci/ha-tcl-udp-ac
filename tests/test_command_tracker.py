"""Concurrent command tracking tests."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module


class CommandTrackerTest(unittest.TestCase):
    """Each pending command should have an independent stable identifier."""

    def setUp(self) -> None:
        self.commands = load_integration_module("command_tracker")
        self.bundles = load_integration_module("command_bundles")

    def receipt(self, intent, expected):
        return self.bundles.CommandReceipt(
            intent,
            expected,
            self.bundles.TransportDelivery(udp=self.bundles.TransportAttempt.ACCEPTED),
        )

    def test_multiple_commands_do_not_overwrite_each_other(self) -> None:
        tracker = self.commands.CommandTracker()

        power_id = tracker.record(self.receipt("power:on", {"power": True}))
        mode_id = tracker.record(self.receipt("mode:cool", {"mode": "cool"}))

        self.assertNotEqual(power_id, mode_id)
        self.assertEqual(tracker.pending(power_id).expected_status, {"power": True})
        self.assertEqual(tracker.pending(mode_id).expected_status, {"mode": "cool"})

    def test_completing_one_command_keeps_other_pending(self) -> None:
        tracker = self.commands.CommandTracker()
        first = tracker.record(self.receipt("power:on", {"power": True}))
        second = tracker.record(self.receipt("temperature:set", {"target_temp": 24.0}))

        completed = tracker.complete(first)

        self.assertEqual(completed.command_id, first)
        self.assertIsNone(tracker.pending(first))
        self.assertEqual(tracker.pending(second).command_id, second)

    def test_latest_pending_supports_compatibility_callers(self) -> None:
        tracker = self.commands.CommandTracker()
        tracker.record(self.receipt("power:on", {"power": True}))
        latest = tracker.record(self.receipt("mode:heat", {"mode": "heat"}))

        self.assertEqual(tracker.pending().command_id, latest)


if __name__ == "__main__":
    unittest.main()
