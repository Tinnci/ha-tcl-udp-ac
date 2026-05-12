"""Command bundle to status parser reconciliation tests."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module


class CommandStatusReconciliationTest(unittest.TestCase):
    """Legacy command expected statuses should agree with parser mappings."""

    def setUp(self) -> None:
        self.profiles = load_integration_module("protocol_profiles")
        self.const = load_integration_module("const")
        self.profile = self.profiles.resolve_protocol_profile("2743138")

    def test_supported_command_bundles_parse_to_expected_modes(self) -> None:
        for mode in (
            self.const.MODE_FAN,
            self.const.MODE_DEHUMI,
            self.const.MODE_COOL,
            self.const.MODE_HEAT,
        ):
            bundle = self.profile.build_mode_command(mode)

            parsed_mode = self.profile.parse_base_mode(bundle.payload["baseMode"])

            self.assertEqual(parsed_mode, bundle.expected_status["mode"])

    def test_unknown_base_modes_do_not_become_supported_modes(self) -> None:
        self.assertEqual(self.profile.parse_base_mode("1"), self.const.MODE_COOL)
        self.assertIsNone(self.profile.parse_base_mode("7"))
        self.assertIsNone(self.profile.parse_base_mode("8"))
        self.assertIsNone(self.profile.parse_base_mode("99"))


if __name__ == "__main__":
    unittest.main()
