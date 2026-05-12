"""Legacy TCL mode profile command tests."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module


class LegacyModeProfileTest(unittest.TestCase):
    """Legacy mode bundles should match capture-supported payloads."""

    def setUp(self) -> None:
        self.profiles = load_integration_module("protocol_profiles")
        self.const = load_integration_module("const")
        self.profile = self.profiles.resolve_protocol_profile("2743138")

    def test_fan_only_profile_emits_base_mode_zero(self) -> None:
        bundle = self.profile.build_mode_command(self.const.MODE_FAN)

        self.assertEqual(
            bundle.payload,
            {
                "turnOn": "1",
                "baseMode": "0",
                "setTemp": "73",
                "degreeH": "0",
                "windSpd": "0",
                "optSuper": "0",
            },
        )

    def test_dry_profile_emits_captured_fallback_bundle(self) -> None:
        bundle = self.profile.build_mode_command(self.const.MODE_DEHUMI)

        self.assertEqual(
            bundle.payload,
            {
                "turnOn": "1",
                "baseMode": "2",
                "setTemp": "82",
                "degreeH": "0",
                "windSpd": "0",
                "optSuper": "0",
            },
        )

    def test_dry_profile_uses_valid_current_target(self) -> None:
        bundle = self.profile.build_mode_command(
            self.const.MODE_DEHUMI,
            target_temperature=23.0,
        )

        self.assertEqual(bundle.payload["setTemp"], "73")

    def test_cool_profile_uses_grouped_current_target_with_captured_mode(self) -> None:
        bundle = self.profile.build_mode_command(
            self.const.MODE_COOL,
            target_temperature=24.0,
        )

        self.assertEqual(bundle.payload["turnOn"], "1")
        self.assertEqual(bundle.payload["baseMode"], "1")
        self.assertEqual(bundle.payload["setTemp"], "75")
        self.assertEqual(bundle.payload["windSpd"], "0")
        self.assertEqual(bundle.payload["optSuper"], "0")

    def test_heat_profile_uses_grouped_current_target_with_super_clear(self) -> None:
        bundle = self.profile.build_mode_command(
            self.const.MODE_HEAT,
            target_temperature=28.0,
        )

        self.assertEqual(bundle.payload["turnOn"], "1")
        self.assertEqual(bundle.payload["baseMode"], "4")
        self.assertEqual(bundle.payload["setTemp"], "82")
        self.assertEqual(bundle.payload["windSpd"], "0")
        self.assertEqual(bundle.payload["optSuper"], "0")

    def test_temperature_profile_requires_cool_or_heat_context(self) -> None:
        cool_bundle = self.profile.build_temperature_command(
            25.0,
            current_mode=self.const.MODE_COOL,
        )
        heat_bundle = self.profile.build_temperature_command(
            25.0,
            current_mode=self.const.MODE_HEAT,
        )

        self.assertEqual(
            cool_bundle.payload,
            {"setTemp": "77", "degreeH": "0", "optSuper": "0"},
        )
        self.assertEqual(heat_bundle.payload, cool_bundle.payload)
        with self.assertRaises(self.profiles.UnsupportedModeError):
            self.profile.build_temperature_command(
                25.0,
                current_mode=self.const.MODE_DEHUMI,
            )

    def test_auto_profile_is_not_available(self) -> None:
        with self.assertRaises(self.profiles.UnsupportedModeError):
            self.profile.build_mode_command(self.const.MODE_AUTO)

    def test_supported_profiles_never_emit_base_mode_seven_or_eight(self) -> None:
        emitted = {
            self.profile.build_mode_command(mode).payload["baseMode"]
            for mode in (
                self.const.MODE_COOL,
                self.const.MODE_DEHUMI,
                self.const.MODE_FAN,
                self.const.MODE_HEAT,
            )
        }

        self.assertNotIn("7", emitted)
        self.assertNotIn("8", emitted)

    def test_power_off_profile_emits_app_shutdown_group(self) -> None:
        bundle = self.profile.build_power_off_command()

        self.assertEqual(
            bundle.payload,
            {
                "optSleepMd": "0",
                "optECO": "0",
                "optHealthy": "0",
                "optSuper": "0",
                "optHeat": "0",
                "turnOn": "0",
            },
        )
        self.assertEqual(bundle.expected_status, {"power": False})
        self.assertFalse(bundle.requires_power_on)


if __name__ == "__main__":
    unittest.main()
