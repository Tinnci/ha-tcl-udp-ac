"""Legacy TCL temperature codec tests."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module


class LegacyTemperatureCodecTest(unittest.TestCase):
    """Legacy mode profiles should encode Celsius targets deterministically."""

    def setUp(self) -> None:
        self.codec = load_integration_module("temperature_codec").LegacyTemperatureCodec

    def test_fan_fallback_encodes_to_captured_temp(self) -> None:
        self.assertEqual(
            self.codec.encode(None, fallback_celsius=23.0),
            ("73", "0"),
        )

    def test_dry_fallback_encodes_to_captured_temp(self) -> None:
        self.assertEqual(
            self.codec.encode(None, fallback_celsius=28.0),
            ("82", "0"),
        )

    def test_valid_current_target_is_used(self) -> None:
        self.assertEqual(
            self.codec.encode(24.0, fallback_celsius=28.0),
            ("75", "0"),
        )

    def test_invalid_target_uses_fallback(self) -> None:
        self.assertEqual(
            self.codec.encode(40.0, fallback_celsius=23.0),
            ("73", "0"),
        )

    def test_half_degree_targets_are_preserved(self) -> None:
        set_temp, degree_h = self.codec.encode(23.5, fallback_celsius=23.0)
        round_trip = round(
            self.codec.fahrenheit_to_celsius(int(set_temp)) + 0.5 * int(degree_h),
            1,
        )

        self.assertLessEqual(abs(round_trip - 23.5), 0.25)


if __name__ == "__main__":
    unittest.main()
