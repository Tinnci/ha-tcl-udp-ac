"""Protocol profiles for TCL AC devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .command_bundles import CaptureEvidence, TclCommandBundle
from .const import MODE_AUTO, MODE_COOL, MODE_DEHUMI, MODE_FAN, MODE_HEAT
from .temperature_codec import LegacyTemperatureCodec


class UnsupportedModeError(ValueError):
    """Raised when a protocol profile explicitly does not support a mode."""


@dataclass(frozen=True)
class ProtocolProfile:
    """Base TCL protocol profile."""

    device_id: str | None = None
    name: str = "default"

    def build_mode_command(
        self,
        mode: str,
        *,
        target_temperature: float | None = None,
    ) -> TclCommandBundle:
        """Build a mode command bundle for the profile."""
        base_mode = {
            MODE_HEAT: "4",
            MODE_DEHUMI: "2",
            MODE_COOL: "3",
            MODE_FAN: "7",
            MODE_AUTO: "8",
        }.get(mode)
        if base_mode is None:
            raise UnsupportedModeError(f"Unsupported mode: {mode}")
        return TclCommandBundle(
            intent=f"mode:{mode}",
            payload={"turnOn": "1", "baseMode": base_mode},
            evidence=CaptureEvidence(
                level="existing-default",
                source="pre-profile integration behavior",
                rationale="Default profile preserves existing non-legacy mode mapping.",
            ),
            requires_power_on=True,
            expected_status={"power": True, "mode": mode},
        )

    def parse_base_mode(self, base_mode: Any) -> str | None:
        """Parse a protocol baseMode into an integration mode string."""
        return {
            "1": MODE_HEAT,
            "2": MODE_DEHUMI,
            "3": MODE_COOL,
            "4": MODE_HEAT,
            "7": MODE_FAN,
            "8": MODE_AUTO,
        }.get(str(base_mode))


class Legacy2743138Profile(ProtocolProfile):
    """Capture-derived profile for legacy TCL device 2743138."""

    def __init__(self, device_id: str | None = "2743138") -> None:
        super().__init__(device_id=device_id, name="legacy_2743138")

    def _evidence(self, mode: str) -> CaptureEvidence:
        return CaptureEvidence(
            level="capture-supported",
            source=(
                "newly_captured/tcl_1778556941.jsonl and "
                "newly_captured/tcl_1778557400.jsonl"
            ),
            rationale=f"Legacy {mode} bundle shape was derived from observed app packets.",
        )

    def build_mode_command(
        self,
        mode: str,
        *,
        target_temperature: float | None = None,
    ) -> TclCommandBundle:
        """Build a capture-derived legacy mode command bundle."""
        if mode == MODE_AUTO:
            raise UnsupportedModeError(
                "Auto/AI is not capture-supported for legacy device 2743138."
            )

        if mode == MODE_FAN:
            payload = {
                "turnOn": "1",
                "baseMode": "0",
                "setTemp": "73",
                "degreeH": "0",
                "windSpd": "0",
                "optSuper": "0",
            }
            return TclCommandBundle(
                intent="mode:fan_only",
                payload=payload,
                evidence=self._evidence("fan_only"),
                requires_power_on=True,
                expected_status={"power": True, "mode": MODE_FAN},
            )

        if mode == MODE_DEHUMI:
            set_temp, degree_h = LegacyTemperatureCodec.encode(
                target_temperature,
                fallback_celsius=28.0,
            )
            payload = {
                "turnOn": "1",
                "baseMode": "2",
                "setTemp": set_temp,
                "degreeH": degree_h,
                "windSpd": "0",
                "optSuper": "0",
            }
            return TclCommandBundle(
                intent="mode:dry",
                payload=payload,
                evidence=self._evidence("dry"),
                requires_power_on=True,
                expected_status={"power": True, "mode": MODE_DEHUMI},
            )

        if mode in {MODE_COOL, MODE_HEAT}:
            base_mode = "3" if mode == MODE_COOL else "4"
            fallback = 23.0 if mode == MODE_COOL else 28.0
            set_temp, degree_h = LegacyTemperatureCodec.encode(
                target_temperature,
                fallback_celsius=fallback,
            )
            payload = {
                "turnOn": "1",
                "baseMode": base_mode,
                "setTemp": set_temp,
                "degreeH": degree_h,
                "windSpd": "0",
            }
            return TclCommandBundle(
                intent=f"mode:{mode}",
                payload=payload,
                evidence=self._evidence(mode),
                requires_power_on=True,
                expected_status={"power": True, "mode": mode},
            )

        raise UnsupportedModeError(f"Unsupported legacy mode: {mode}")

    def parse_base_mode(self, base_mode: Any) -> str | None:
        """Parse legacy status baseMode values."""
        return {
            "0": MODE_FAN,
            "2": MODE_DEHUMI,
            "3": MODE_COOL,
            "4": MODE_HEAT,
        }.get(str(base_mode))


def resolve_protocol_profile(device_id: str | None) -> ProtocolProfile:
    """Resolve a TCL protocol profile for a configured device id."""
    if str(device_id or "") == "2743138":
        return Legacy2743138Profile(device_id="2743138")
    return ProtocolProfile(device_id=device_id)
