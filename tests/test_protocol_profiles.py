"""Protocol profile resolver and command bundle tests."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module


class ProtocolProfileTest(unittest.TestCase):
    """Profile resolver should isolate legacy 2743138 behavior."""

    def setUp(self) -> None:
        self.profiles = load_integration_module("protocol_profiles")
        self.const = load_integration_module("const")

    def test_resolver_selects_legacy_profile_for_target_device(self) -> None:
        profile = self.profiles.resolve_protocol_profile("2743138")

        self.assertIsInstance(profile, self.profiles.Legacy2743138Profile)

    def test_resolver_selects_tsl_profile_for_protocol_one_target(self) -> None:
        profile = self.profiles.resolve_protocol_profile("45816970")

        self.assertIsInstance(profile, self.profiles.Tsl1112013595NProfile)
        self.assertEqual(profile.name, "tsl_1112013595N")
        self.assertFalse(profile.legacy_transport_enabled)
        self.assertFalse(profile.local_transport_enabled)

    def test_resolver_uses_default_for_unknown_devices(self) -> None:
        profile = self.profiles.resolve_protocol_profile("other")

        self.assertEqual(profile.name, "default")

    def test_tsl_temperature_command_uses_property_transport(self) -> None:
        profile = self.profiles.resolve_protocol_profile("45816970")
        bundle = profile.build_temperature_command(25.5)

        self.assertEqual(bundle.transport, self.profiles.CommandTransport.TSL_PROPERTY)
        self.assertEqual(bundle.payload, {"targetTemperature": 25.5})
        self.assertEqual(bundle.expected_status, {"target_temp": 25.5})

    def test_tsl_mode_command_uses_work_mode_payload(self) -> None:
        profile = self.profiles.resolve_protocol_profile("45816970")
        bundle = profile.build_mode_command(self.const.MODE_HEAT, target_temperature=28)

        self.assertEqual(bundle.transport, self.profiles.CommandTransport.TSL_PROPERTY)
        self.assertEqual(
            bundle.payload,
            {"powerSwitch": 1, "workMode": 4, "targetTemperature": 28.0},
        )
        self.assertEqual(bundle.source_type, "2")
        self.assertEqual(bundle.expected_status["mode"], self.const.MODE_HEAT)

    def test_tsl_fan_swing_feature_and_number_commands_are_exact(self) -> None:
        profile = self.profiles.resolve_protocol_profile("45816970")

        auto = profile.build_fan_command("auto")
        gear = profile.build_fan_command("6")
        swing = profile.build_swing_command(vertical=True, horizontal=False)
        clean = profile.build_feature_command("self_clean", enabled=True)
        fresh_air = profile.build_number_command("fresh_air_percentage", 33.4)

        self.assertEqual(auto.payload, {"windSpeedAutoSwitch": 1, "windSpeed7Gear": 0})
        self.assertEqual(gear.payload, {"windSpeedAutoSwitch": 0, "windSpeed7Gear": 6})
        self.assertEqual(swing.payload, {"verticalDirection": 1, "horizontalDirection": 8})
        self.assertEqual(clean.payload, {"selfClean": 1})
        self.assertEqual(clean.expected_status, {"self_clean": True})
        self.assertEqual(fresh_air.payload, {"newWindPercentage": 33})
        for bundle in (auto, gear, swing, clean, fresh_air):
            self.assertEqual(bundle.transport, self.profiles.CommandTransport.TSL_PROPERTY)
            self.assertEqual(bundle.source_type, "2")

    def test_tsl_invalid_fan_gear_is_rejected(self) -> None:
        profile = self.profiles.resolve_protocol_profile("45816970")

        for value in ("low", "0", "8"):
            with self.subTest(value=value), self.assertRaises(
                self.profiles.UnsupportedModeError
            ):
                profile.build_fan_command(value)

    def test_legacy_fan_command_has_capture_evidence(self) -> None:
        profile = self.profiles.resolve_protocol_profile("2743138")
        bundle = profile.build_mode_command(self.const.MODE_FAN)

        self.assertEqual(bundle.payload["baseMode"], "0")
        self.assertEqual(bundle.evidence.level, "capture-supported")
        self.assertEqual(bundle.expected_status["mode"], self.const.MODE_FAN)

    def test_legacy_auto_is_explicitly_unsupported(self) -> None:
        profile = self.profiles.resolve_protocol_profile("2743138")

        with self.assertRaises(self.profiles.UnsupportedModeError):
            profile.build_mode_command(self.const.MODE_AUTO)

    def test_default_profile_preserves_old_non_legacy_mapping(self) -> None:
        profile = self.profiles.resolve_protocol_profile("other")
        bundle = profile.build_mode_command(self.const.MODE_FAN)

        self.assertEqual(bundle.payload, {"turnOn": "1", "baseMode": "7"})

    def test_profile_centralizes_hvac_and_switch_capabilities(self) -> None:
        legacy = self.profiles.resolve_protocol_profile("2743138")
        default = self.profiles.resolve_protocol_profile("other")

        self.assertEqual(
            legacy.capabilities.verified_hvac_modes,
            (self.const.MODE_COOL, self.const.MODE_DEHUMI, self.const.MODE_HEAT),
        )
        self.assertEqual(
            legacy.capabilities.experimental_hvac_modes,
            (self.const.MODE_FAN,),
        )
        self.assertEqual(
            default.capabilities.experimental_hvac_modes,
            (self.const.MODE_FAN, self.const.MODE_AUTO),
        )
        self.assertEqual(
            legacy.capabilities.switches["aux_heat"].available_modes,
            frozenset({self.const.MODE_HEAT}),
        )
        self.assertTrue(legacy.capabilities.switches["aux_heat"].requires_power)


if __name__ == "__main__":
    unittest.main()
