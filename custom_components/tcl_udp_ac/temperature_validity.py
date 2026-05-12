"""Temperature validity helpers for TCL status values."""

from __future__ import annotations

MIN_VALID_OUTDOOR_TEMP_C = -40
MAX_VALID_OUTDOOR_TEMP_C = 71
OUTDOOR_TEMP_PLACEHOLDER_C = 0.0


def is_valid_outdoor_temperature(value: float) -> bool:
    """Return true when a parsed outdoor temperature is a real reading."""
    return (
        MIN_VALID_OUTDOOR_TEMP_C <= value <= MAX_VALID_OUTDOOR_TEMP_C
        and value != OUTDOOR_TEMP_PLACEHOLDER_C
    )
