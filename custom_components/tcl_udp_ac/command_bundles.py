"""Command bundle models for TCL protocol profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CaptureEvidence:
    """Traceability from implementation behavior back to capture evidence."""

    level: str
    source: str
    rationale: str


@dataclass(frozen=True)
class TclCommandBundle:
    """A grouped TCL command payload produced by a protocol profile."""

    intent: str
    payload: dict[str, str]
    evidence: CaptureEvidence
    requires_power_on: bool
    expected_status: dict[str, Any]

    def to_command_items(self) -> list[tuple[str, str]]:
        """Convert protocol fields to integration command item names."""
        command_map = {
            "turnOn": "TurnOn",
            "baseMode": "BaseMode",
            "setTemp": "SetTemp",
            "degreeH": "DegreeH",
            "windSpd": "WindSpeed",
            "optSuper": "Opt_super",
            "optECO": "Opt_ECO",
            "optHealthy": "OptHealthy",
            "optSleepMd": "Opt_sleepMode",
            "optHeat": "OptHeat",
            "directH": "WindDirection_H",
            "directV": "WindDirection_V",
            "optSolidWd": "OptSolidWd",
        }
        return [
            (command_map.get(key, key), value)
            for key, value in self.payload.items()
        ]
