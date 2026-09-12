"""Typed device-state reconciliation tests."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from tests.test_protocol_commands import load_integration_module


class StateReducerTest(unittest.TestCase):
    """State reconciliation should be deterministic per field."""

    def setUp(self) -> None:
        self.state = load_integration_module("device_state")

    def test_partial_observations_preserve_unmentioned_fields(self) -> None:
        reducer = self.state.StateReducer()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                received_at=10,
                values={"power": True, "target_temp": 24.0},
            )
        )
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=11,
                values={"current_temp": 27.0},
            )
        )

        self.assertEqual(
            reducer.as_dict(),
            {"power": True, "target_temp": 24.0, "current_temp": 27.0},
        )

    def test_older_observation_cannot_overwrite_newer_field(self) -> None:
        reducer = self.state.StateReducer()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=20,
                values={"power": True},
            )
        )
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                received_at=10,
                values={"power": False},
            )
        )

        self.assertEqual(reducer.as_dict()["power"], True)

    def test_udp_wins_equal_timestamp_tie(self) -> None:
        reducer = self.state.StateReducer()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                received_at=20,
                values={"power": False},
            )
        )
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=20,
                values={"power": True},
            )
        )

        self.assertEqual(reducer.as_dict()["power"], True)

    def test_recent_udp_field_is_not_overwritten_by_cloud_fallback(self) -> None:
        reducer = self.state.StateReducer()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=20,
                values={"power": True},
            )
        )
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                received_at=21,
                values={"power": False},
            )
        )

        self.assertEqual(reducer.as_dict()["power"], True)

    def test_cloud_can_replace_udp_field_after_local_freshness_window(self) -> None:
        reducer = self.state.StateReducer()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=20,
                values={"power": True},
            )
        )
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                received_at=111,
                values={"power": False},
            )
        )

        self.assertEqual(reducer.as_dict()["power"], False)

    def test_snapshot_is_not_mutated_by_later_updates(self) -> None:
        reducer = self.state.StateReducer()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=1,
                values={"power": True},
            )
        )
        snapshot = reducer.as_dict()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=2,
                values={"power": False},
            )
        )

        self.assertEqual(snapshot, {"power": True})

    def test_nested_input_and_snapshot_values_are_isolated(self) -> None:
        reducer = self.state.StateReducer()
        source = {"energy_statistics": {"energy_kwh": 3.4}}
        state = reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                received_at=1,
                values=source,
            )
        )

        source["energy_statistics"]["energy_kwh"] = 99
        exported = state.as_dict()
        exported["energy_statistics"]["energy_kwh"] = 55

        self.assertEqual(
            reducer.as_dict()["energy_statistics"]["energy_kwh"],
            3.4,
        )

    def test_snapshot_nested_values_cannot_change_while_shared(self) -> None:
        """Consumers must not be able to rewrite a retained observation snapshot."""
        reducer = self.state.StateReducer()
        snapshot = reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.DERIVED,
                received_at=1,
                values={"energy_statistics": {"energy_kwh": 3.4}},
            )
        )

        with self.assertRaises(TypeError):
            snapshot.values["energy_statistics"]["energy_kwh"] = 99

    def test_partial_reports_retain_per_field_receipt_time_and_source(self) -> None:
        """A new field must not refresh the evidence attached to existing fields."""
        reducer = self.state.StateReducer()
        first_at = datetime(2026, 9, 12, tzinfo=UTC)
        first = reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                received_at=10,
                received_at_utc=first_at,
                values={"compressor_frequency": 42},
            )
        )
        latest = reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.UDP,
                received_at=400,
                received_at_utc=first_at + timedelta(seconds=390),
                values={"power": True},
            )
        )

        self.assertEqual(
            latest.observations["compressor_frequency"],
            first.observations["compressor_frequency"],
        )
        self.assertEqual(latest.fresh_values(400), {"power": True})
        self.assertEqual(
            latest.observed_at("compressor_frequency"), first_at.isoformat()
        )
        self.assertEqual(first.as_dict(), {"compressor_frequency": 42})
        with self.assertRaises(TypeError):
            latest.observations["power"] = first.observations["compressor_frequency"]

    def test_repeated_equal_report_can_confirm_without_a_value_change(self) -> None:
        """Confirmation needs a new report, not necessarily a changed value."""
        reducer = self.state.StateReducer()
        for timestamp in (10, 20):
            snapshot = reducer.apply(
                self.state.Observation(
                    source=self.state.StateSource.UDP,
                    received_at=timestamp,
                    values={"power": False},
                )
            )

        self.assertEqual(snapshot.observed_since(15), {"power": False})

    def test_late_cloud_response_cannot_replace_a_newer_requested_snapshot(
        self,
    ) -> None:
        """Responses arriving out of request order must not rewind physical state."""
        reducer = self.state.StateReducer()
        reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                requested_at=20,
                received_at=21,
                values={"power": False},
            )
        )
        snapshot = reducer.apply(
            self.state.Observation(
                source=self.state.StateSource.CLOUD,
                requested_at=10,
                received_at=22,
                values={"power": True},
            )
        )

        self.assertEqual(snapshot.as_dict(), {"power": False})
        self.assertEqual(snapshot.observations["power"].received_at, 21)


if __name__ == "__main__":
    unittest.main()
