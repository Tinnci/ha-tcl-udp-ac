"""Capture replay contract tests for generated legacy mode profiles."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_protocol_commands import load_integration_module
from tools.analyze_legacy_mode_capture import build_summary


CAPTURES = [
    Path("newly_captured/tcl_1778556941.jsonl"),
    Path("newly_captured/tcl_1778557400.jsonl"),
]


class LegacyCaptureReplayContractTest(unittest.TestCase):
    """Generated bundles must remain justified by observed captures."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = build_summary(CAPTURES, "2743138")
        cls.profiles = load_integration_module("protocol_profiles")
        cls.const = load_integration_module("const")
        cls.profile = cls.profiles.resolve_protocol_profile("2743138")

    def _inferred_payload(self, mode: str) -> dict[str, str]:
        profiles = {profile["mode"]: profile for profile in self.summary["inferredProfiles"]}
        return profiles[mode]["payload"]

    def test_generated_fan_profile_matches_captured_shape(self) -> None:
        bundle = self.profile.build_mode_command(self.const.MODE_FAN)
        captured = self._inferred_payload("fan_only")

        for key, value in captured.items():
            self.assertEqual(bundle.payload[key], value)
        self.assertEqual(bundle.payload["turnOn"], "1")

    def test_generated_dry_profile_matches_captured_shape(self) -> None:
        bundle = self.profile.build_mode_command(self.const.MODE_DEHUMI)

        self.assertEqual(bundle.payload["baseMode"], self._inferred_payload("dry")["baseMode"])
        self.assertEqual(bundle.payload["setTemp"], self._inferred_payload("dry")["setTemp"])
        self.assertEqual(bundle.payload["windSpd"], self._inferred_payload("dry")["windSpd"])
        self.assertEqual(bundle.payload["optSuper"], self._inferred_payload("dry")["optSuper"])

    def test_no_supported_generated_profile_emits_base_mode_seven_or_eight(self) -> None:
        emitted = {
            self.profile.build_mode_command(mode).payload["baseMode"]
            for mode in (
                self.const.MODE_FAN,
                self.const.MODE_DEHUMI,
                self.const.MODE_COOL,
                self.const.MODE_HEAT,
            )
        }

        self.assertFalse({"7", "8"} & emitted)

    def test_generated_fields_are_observed_in_capture(self) -> None:
        observed_fields = set(self.summary["fieldEvidence"])

        for mode in (
            self.const.MODE_FAN,
            self.const.MODE_DEHUMI,
            self.const.MODE_COOL,
            self.const.MODE_HEAT,
        ):
            bundle = self.profile.build_mode_command(mode)
            self.assertLessEqual(set(bundle.payload), observed_fields)

    def test_opt_super_is_not_blindly_added_to_cool_or_heat(self) -> None:
        self.assertNotIn("optSuper", self.profile.build_mode_command(self.const.MODE_COOL).payload)
        self.assertNotIn("optSuper", self.profile.build_mode_command(self.const.MODE_HEAT).payload)


if __name__ == "__main__":
    unittest.main()
