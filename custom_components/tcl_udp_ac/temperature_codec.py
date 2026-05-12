"""Temperature encoding helpers for TCL legacy protocol."""

from __future__ import annotations


class LegacyTemperatureCodec:
    """Encode Home Assistant Celsius values into legacy setTemp/degreeH fields."""

    MIN_CELSIUS = 16.0
    MAX_CELSIUS = 31.0

    @staticmethod
    def fahrenheit_to_celsius(temp_f: float) -> float:
        """Convert Fahrenheit-style protocol temperature to Celsius."""
        return (temp_f - 32.0) / 1.8

    @staticmethod
    def celsius_to_fahrenheit(temp_c: float) -> float:
        """Convert Celsius to Fahrenheit-style protocol temperature."""
        return temp_c * 1.8 + 32.0

    @classmethod
    def is_valid_celsius(cls, temp_c: float | None) -> bool:
        """Return true when the target is valid for TCL AC controls."""
        if temp_c is None:
            return False
        return cls.MIN_CELSIUS <= float(temp_c) <= cls.MAX_CELSIUS

    @classmethod
    def encode(cls, temp_c: float | None, *, fallback_celsius: float) -> tuple[str, str]:
        """Encode a Celsius target, using fallback when target is missing/invalid."""
        target = float(temp_c) if cls.is_valid_celsius(temp_c) else fallback_celsius
        desired_c_rounded = round(target * 2) / 2
        base_f = round(cls.celsius_to_fahrenheit(target))

        best: tuple[float, float, float, int, int] | None = None
        for f_int in range(base_f - 3, base_f + 4):
            for degree_half in (0, 1):
                c_val = cls.fahrenheit_to_celsius(f_int) + 0.5 * degree_half
                c_rounded = round(c_val * 2) / 2
                diff = abs(c_rounded - desired_c_rounded)
                diff_raw = abs(c_val - target)
                diff_f = abs(f_int - cls.celsius_to_fahrenheit(target))
                candidate = (diff, diff_raw, diff_f, f_int, degree_half)
                if best is None or candidate < best:
                    best = candidate

        if best is None:
            return str(round(cls.celsius_to_fahrenheit(target))), "0"
        return str(best[3]), str(best[4])
