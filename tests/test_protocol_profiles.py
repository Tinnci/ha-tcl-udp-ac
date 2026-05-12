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

    def test_resolver_uses_default_for_other_devices(self) -> None:
        profile = self.profiles.resolve_protocol_profile("45816970")

        self.assertNotIsInstance(profile, self.profiles.Legacy2743138Profile)
        self.assertEqual(profile.name, "default")

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


if __name__ == "__main__":
    unittest.main()
