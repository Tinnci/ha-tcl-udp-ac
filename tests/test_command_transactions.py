"""Command transaction model tests."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module


class CommandTransactionTest(unittest.TestCase):
    """Transactions should separate send acceptance from device application."""

    def setUp(self) -> None:
        self.command_bundles = load_integration_module("command_bundles")

    def test_transaction_classifies_applied_status(self) -> None:
        tx = self.command_bundles.TclCommandTransaction(
            intent="mode:fan_only",
            payload={"turnOn": "1", "baseMode": "0"},
            evidence=self.command_bundles.CaptureEvidence(
                level="capture-supported",
                source="capture",
                rationale="test",
            ),
            expected_status_projection={"turnOn": "1", "baseMode": "0"},
            verification_policy=self.command_bundles.VerificationPolicy.STATUS_MATCH,
        )

        result = tx.classify_result(
            transport_accepted=True,
            status_after={"turnOn": "1", "baseMode": "0"},
        )

        self.assertEqual(
            result.outcome, self.command_bundles.TransactionOutcome.APPLIED
        )
        self.assertEqual(result.matches, {"turnOn": "1", "baseMode": "0"})
        self.assertEqual(result.mismatches, {})

    def test_transaction_classifies_cloud_only_or_ignored(self) -> None:
        tx = self.command_bundles.TclCommandTransaction(
            intent="temperature:candidate",
            payload={"setTemp": "75", "degreeH": "0"},
            evidence=self.command_bundles.CaptureEvidence(
                level="hypothesis",
                source="manual experiment",
                rationale="test",
            ),
            expected_status_projection={"setTemp": "75", "degreeH": "0"},
            verification_policy=self.command_bundles.VerificationPolicy.STATUS_MATCH,
        )

        result = tx.classify_result(
            transport_accepted=True,
            status_after={"setTemp": "73", "degreeH": "0"},
        )

        self.assertEqual(
            result.outcome,
            self.command_bundles.TransactionOutcome.CLOUD_ONLY_OR_IGNORED,
        )
        self.assertEqual(
            result.mismatches,
            {"setTemp": {"expected": "75", "actual": "73"}},
        )

    def test_transaction_classifies_transport_failure(self) -> None:
        tx = self.command_bundles.TclCommandTransaction(
            intent="power:off",
            payload={"turnOn": "0"},
            evidence=self.command_bundles.CaptureEvidence(
                level="capture-supported",
                source="capture",
                rationale="test",
            ),
            expected_status_projection={"turnOn": "0"},
            verification_policy=self.command_bundles.VerificationPolicy.STATUS_MATCH,
        )

        result = tx.classify_result(
            transport_accepted=False,
            status_after={"turnOn": "1"},
        )

        self.assertEqual(result.outcome, self.command_bundles.TransactionOutcome.FAILED)


if __name__ == "__main__":
    unittest.main()
