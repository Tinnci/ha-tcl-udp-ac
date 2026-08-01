"""Typed device-state reconciliation tests."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
