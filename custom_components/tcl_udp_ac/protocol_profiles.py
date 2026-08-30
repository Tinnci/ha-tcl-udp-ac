"""Protocol profiles for TCL AC devices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .command_bundles import CaptureEvidence, CommandTransport, TclCommandBundle
from .const import MODE_AUTO, MODE_COOL, MODE_DEHUMI, MODE_FAN, MODE_HEAT
from .temperature_codec import LegacyTemperatureCodec


class UnsupportedModeError(ValueError):
    """Raised when a protocol profile explicitly does not support a mode."""


@dataclass(frozen=True)
class SwitchCapability:
    """Mode and power constraints for a feature switch."""

    api_key: str
    data_key: str
    translation_key: str
    icon: str
    entity_category: str | None = None
    available_modes: frozenset[str] | None = None
    requires_power: bool = False


@dataclass(frozen=True)
class DiagnosticSensorCapability:
    """One read-only value exposed as a Home Assistant diagnostic sensor."""

    data_key: str
    translation_key: str
    icon: str
    native_unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None


@dataclass(frozen=True)
class BinaryDiagnosticCapability:
    """One read-only boolean exposed as a diagnostic binary sensor."""

    data_key: str
    translation_key: str
    icon: str
    device_class: str | None = None


@dataclass(frozen=True)
class NumberCapability:
    """One writable numeric TSL property."""

    data_key: str
    translation_key: str
    icon: str
    native_min: float
    native_max: float
    native_step: float
    native_unit: str | None = None


@dataclass(frozen=True)
class DeviceCapabilities:
    """Home Assistant-facing capabilities for a TCL protocol profile."""

    verified_hvac_modes: tuple[str, ...] = (
        MODE_COOL,
        MODE_DEHUMI,
        MODE_HEAT,
    )
    experimental_hvac_modes: tuple[str, ...] = (
        MODE_FAN,
        MODE_AUTO,
    )
    switches: dict[str, SwitchCapability] = field(default_factory=dict)
    supports_fan_speed: bool = True
    supports_swing: bool = True
    fan_modes: tuple[str, ...] = ("auto", "low", "middle", "high")
    diagnostic_sensors: tuple[DiagnosticSensorCapability, ...] = ()
    binary_diagnostics: tuple[BinaryDiagnosticCapability, ...] = ()
    numbers: tuple[NumberCapability, ...] = ()


def _default_switch_capabilities() -> dict[str, SwitchCapability]:
    """Return the default TCL feature-switch capability map."""
    return {
        "eco_mode": SwitchCapability(
            api_key="optECO",
            data_key="eco_mode",
            translation_key="eco_mode",
            icon="mdi:leaf",
        ),
        "display": SwitchCapability(
            api_key="optDisplay",
            data_key="display",
            translation_key="display",
            icon="mdi:led-on",
            entity_category="config",
        ),
        "health_mode": SwitchCapability(
            api_key="optHealthy",
            data_key="health_mode",
            translation_key="health_mode",
            icon="mdi:doctor",
        ),
        "sleep_mode": SwitchCapability(
            api_key="optSleepMd",
            data_key="sleep_mode",
            translation_key="sleep_mode",
            icon="mdi:sleep",
        ),
        "turbo_mode": SwitchCapability(
            api_key="optSuper",
            data_key="turbo_mode",
            translation_key="turbo_mode",
            icon="mdi:rocket",
        ),
        "aux_heat": SwitchCapability(
            api_key="optHeat",
            data_key="aux_heat",
            translation_key="aux_heat",
            icon="mdi:radiator",
            available_modes=frozenset({MODE_HEAT}),
            requires_power=True,
        ),
        "beep": SwitchCapability(
            api_key="beepEn",
            data_key="beep",
            translation_key="beep",
            icon="mdi:volume-high",
            entity_category="config",
        ),
    }


DEFAULT_CAPABILITIES = DeviceCapabilities(
    switches=_default_switch_capabilities(),
)

LEGACY_2743138_CAPABILITIES = DeviceCapabilities(
    experimental_hvac_modes=(MODE_FAN,),
    switches=_default_switch_capabilities(),
)

TSL_1112013595N_CAPABILITIES = DeviceCapabilities(
    # The captured listControl exposes cool/dry/fan/heat/AI, but keep fan/AI
    # behind the existing opt-in until there is write confirmation.
    experimental_hvac_modes=(MODE_FAN, MODE_AUTO),
    switches={
        "eco_mode": SwitchCapability("ECO", "eco_mode", "eco_mode", "mdi:leaf"),
        "display": SwitchCapability(
            "screen", "display", "display", "mdi:led-on", entity_category="config"
        ),
        "health_mode": SwitchCapability(
            "healthy", "health_mode", "health_mode", "mdi:doctor"
        ),
        "sleep_mode": SwitchCapability(
            "sleep", "sleep_mode", "sleep_mode", "mdi:sleep"
        ),
        "turbo_mode": SwitchCapability(
            "turbo", "turbo_mode", "turbo_mode", "mdi:rocket"
        ),
        "aux_heat": SwitchCapability(
            "PTC",
            "aux_heat",
            "aux_heat",
            "mdi:radiator",
            available_modes=frozenset({MODE_HEAT}),
            requires_power=True,
        ),
        "beep": SwitchCapability(
            "beepSwitch", "beep", "beep", "mdi:volume-high", entity_category="config"
        ),
        "beep_temperature": SwitchCapability(
            "beepTempEn",
            "beep_temperature",
            "beep_temperature",
            "mdi:volume-medium",
            entity_category="config",
        ),
        "anti_mildew": SwitchCapability(
            "antiMoldew", "anti_mildew", "anti_mildew", "mdi:shield-check"
        ),
        "soft_wind": SwitchCapability(
            "softWind", "soft_wind", "soft_wind", "mdi:weather-windy"
        ),
        "self_clean": SwitchCapability(
            "selfClean", "self_clean", "self_clean", "mdi:air-filter"
        ),
        "fresh_air_auto": SwitchCapability(
            "newWindAutoSwitch",
            "fresh_air_auto",
            "fresh_air_auto",
            "mdi:fan-auto",
        ),
    },
    supports_fan_speed=True,
    supports_swing=True,
    fan_modes=("auto", "1", "2", "3", "4", "5", "6", "7"),
    numbers=(
        NumberCapability(
            "fresh_air_percentage",
            "fresh_air_percentage",
            "mdi:percent",
            0,
            100,
            1,
            "%",
        ),
    ),
    diagnostic_sensors=(
        DiagnosticSensorCapability("error_codes", "error_codes", "mdi:alert-circle"),
        DiagnosticSensorCapability(
            "internal_coil_temperature",
            "internal_coil_temperature",
            "mdi:thermometer",
            "°C",
            "temperature",
            "measurement",
        ),
        DiagnosticSensorCapability(
            "external_coil_temperature",
            "external_coil_temperature",
            "mdi:thermometer",
            "°C",
            "temperature",
            "measurement",
        ),
        DiagnosticSensorCapability(
            "external_exhaust_temperature",
            "external_exhaust_temperature",
            "mdi:thermometer-high",
            "°C",
            "temperature",
            "measurement",
        ),
        DiagnosticSensorCapability(
            "external_voltage",
            "external_voltage",
            "mdi:sine-wave",
            "V",
            "voltage",
            "measurement",
        ),
        DiagnosticSensorCapability(
            "external_current",
            "external_current",
            "mdi:current-ac",
            "A",
            "current",
            "measurement",
        ),
        DiagnosticSensorCapability(
            "compressor_frequency",
            "compressor_frequency",
            "mdi:sine-wave",
            "Hz",
            "frequency",
            "measurement",
        ),
        DiagnosticSensorCapability(
            "internal_fan_speed", "internal_fan_speed", "mdi:fan"
        ),
        DiagnosticSensorCapability(
            "external_fan_speed", "external_fan_speed", "mdi:fan"
        ),
        DiagnosticSensorCapability(
            "internal_fan_gear", "internal_fan_gear", "mdi:fan-speed-1"
        ),
        DiagnosticSensorCapability(
            "external_fan_gear", "external_fan_gear", "mdi:fan-speed-1"
        ),
        DiagnosticSensorCapability(
            "wind_speed_percentage",
            "wind_speed_percentage",
            "mdi:percent",
            "%",
            None,
            "measurement",
        ),
        DiagnosticSensorCapability(
            "fresh_air_mode", "fresh_air_mode", "mdi:air-purifier"
        ),
        DiagnosticSensorCapability(
            "fresh_air_percentage",
            "fresh_air_percentage",
            "mdi:percent",
            "%",
            None,
            "measurement",
        ),
        DiagnosticSensorCapability("sleep_time", "sleep_time", "mdi:timer-outline"),
        DiagnosticSensorCapability(
            "self_clean_status", "self_clean_status", "mdi:air-filter"
        ),
        DiagnosticSensorCapability("expansion_valve", "expansion_valve", "mdi:valve"),
        DiagnosticSensorCapability("tsl_version", "tsl_version", "mdi:code-tags"),
        DiagnosticSensorCapability(
            "tsl_request_version", "tsl_request_version", "mdi:code-tags"
        ),
        DiagnosticSensorCapability(
            "tsl_query_time",
            "tsl_query_time",
            "mdi:clock-outline",
            device_class="timestamp",
        ),
        DiagnosticSensorCapability(
            "ai_control_source", "ai_control_source", "mdi:robot"
        ),
    ),
    binary_diagnostics=(
        BinaryDiagnosticCapability(
            "filter_blocked", "filter_blocked", "mdi:air-filter", "problem"
        ),
        BinaryDiagnosticCapability(
            "four_way_valve_active", "four_way_valve_active", "mdi:valve"
        ),
        BinaryDiagnosticCapability(
            "aux_heat_active", "aux_heat_active", "mdi:radiator"
        ),
        BinaryDiagnosticCapability("self_learning", "self_learning", "mdi:school"),
    ),
)


@dataclass(frozen=True)
class ProtocolProfile:
    """Base TCL protocol profile."""

    device_id: str | None = None
    name: str = "default"
    capabilities: DeviceCapabilities = DEFAULT_CAPABILITIES
    legacy_transport_enabled: bool = True
    local_transport_enabled: bool = True
    cloud_status_family: str = "hybrid"

    def build_mode_command(
        self,
        mode: str,
        *,
        target_temperature: float | None = None,  # noqa: ARG002  # interface parity
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
            msg = f"Unsupported mode: {mode}"
            raise UnsupportedModeError(msg)
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

    def build_temperature_command(
        self,
        target_temperature: float,
        *,
        current_mode: str | None = None,  # noqa: ARG002  # interface parity
    ) -> TclCommandBundle:
        """Build a target-temperature command bundle for the profile."""
        set_temp, degree_h = LegacyTemperatureCodec.encode(
            target_temperature,
            fallback_celsius=target_temperature,
        )
        return TclCommandBundle(
            intent="temperature:set",
            payload={
                "setTemp": set_temp,
                "degreeH": degree_h,
                "optSuper": "0",
            },
            evidence=CaptureEvidence(
                level="existing-default",
                source="pre-profile integration behavior",
                rationale="Default profile preserves standalone temperature writes.",
            ),
            requires_power_on=True,
            expected_status={"target_temp": target_temperature},
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

    def build_power_off_command(self) -> TclCommandBundle:
        """Build a power-off command bundle for the profile."""
        return TclCommandBundle(
            intent="power:off",
            payload={
                "optSleepMd": "0",
                "optECO": "0",
                "optHealthy": "0",
                "optSuper": "0",
                "optHeat": "0",
                "turnOn": "0",
            },
            evidence=CaptureEvidence(
                level="existing-default",
                source="pre-profile integration behavior",
                rationale="Default profile preserves app shutdown group behavior.",
            ),
            requires_power_on=False,
            expected_status={"power": False},
        )

    def build_power_on_command(self) -> TclCommandBundle:
        """Build a power-on command bundle for the profile."""
        return TclCommandBundle(
            intent="power:on",
            payload={"turnOn": "1"},
            evidence=CaptureEvidence(
                level="existing-default",
                source="pre-profile integration behavior",
                rationale="Default profile preserves standalone power-on writes.",
            ),
            requires_power_on=False,
            expected_status={"power": True},
        )

    def build_fan_command(self, fan_mode: str) -> TclCommandBundle:
        """Build a legacy fan-speed transaction."""
        if fan_mode not in self.capabilities.fan_modes:
            msg = f"Unsupported fan mode: {fan_mode}"
            raise UnsupportedModeError(msg)
        return TclCommandBundle(
            intent="fan_speed:set",
            payload={"windSpd": fan_mode, "optSleepMd": "0", "optSuper": "0"},
            evidence=CaptureEvidence(
                "existing-default",
                "pre-profile integration behavior",
                "Preserves legacy grouped fan writes.",
            ),
            requires_power_on=True,
            expected_status={"fan_speed": fan_mode},
        )

    def build_swing_command(
        self, *, vertical: bool, horizontal: bool
    ) -> TclCommandBundle:
        """Build a legacy swing transaction."""
        return TclCommandBundle(
            intent="swing:set",
            payload={
                "directV": "on" if vertical else "off",
                "directH": "on" if horizontal else "off",
                "optSolidWd": "off",
            },
            evidence=CaptureEvidence(
                "existing-default",
                "pre-profile integration behavior",
                "Preserves legacy grouped swing writes.",
            ),
            requires_power_on=True,
            expected_status={"swing_v": vertical, "swing_h": horizontal},
        )

    def build_feature_command(
        self, data_key: str, *, enabled: bool
    ) -> TclCommandBundle:
        """Build one legacy feature transaction from its capability description."""
        capability = self.capabilities.switches.get(data_key)
        if capability is None:
            msg = f"Unsupported feature: {data_key}"
            raise UnsupportedModeError(msg)
        value: str | int
        if capability.api_key == "optSleepMd":
            value = "1" if enabled else "0"
        else:
            value = "on" if enabled else "off"
        return TclCommandBundle(
            intent=f"switch:{data_key}",
            payload={capability.api_key: value},
            evidence=CaptureEvidence(
                "existing-default",
                "pre-profile integration behavior",
                "Preserves legacy feature writes.",
            ),
            requires_power_on=capability.requires_power,
            expected_status={data_key: enabled},
        )

    def build_number_command(self, data_key: str, _value: float) -> TclCommandBundle:
        """Reject numeric controls not described by this profile."""
        msg = f"Unsupported numeric control: {data_key}"
        raise UnsupportedModeError(msg)


class Legacy2743138Profile(ProtocolProfile):
    """Capture-derived profile for legacy TCL device 2743138."""

    def __init__(self, device_id: str | None = "2743138") -> None:
        """Initialize the legacy 2743138 capture-derived profile."""
        super().__init__(
            device_id=device_id,
            name="legacy_2743138",
            capabilities=LEGACY_2743138_CAPABILITIES,
            cloud_status_family="legacy",
        )

    def _evidence(self, mode: str) -> CaptureEvidence:
        return CaptureEvidence(
            level="capture-supported",
            source=(
                "newly_captured/tcl_1778556941.jsonl, "
                "newly_captured/tcl_1778557400.jsonl, and "
                "newly_captured/tcl_1778569147.jsonl"
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
            msg = "Auto/AI is not capture-supported for legacy device 2743138."
            raise UnsupportedModeError(msg)

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
            base_mode = "1" if mode == MODE_COOL else "4"
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
                "optSuper": "0",
            }
            return TclCommandBundle(
                intent=f"mode:{mode}",
                payload=payload,
                evidence=self._evidence(mode),
                requires_power_on=True,
                expected_status={"power": True, "mode": mode},
            )

        msg = f"Unsupported legacy mode: {mode}"
        raise UnsupportedModeError(msg)

    def parse_base_mode(self, base_mode: Any) -> str | None:
        """Parse legacy status baseMode values."""
        return {
            "0": MODE_FAN,
            "1": MODE_COOL,
            "2": MODE_DEHUMI,
            "4": MODE_HEAT,
        }.get(str(base_mode))

    def build_temperature_command(
        self,
        target_temperature: float,
        *,
        current_mode: str | None = None,
    ) -> TclCommandBundle:
        """
        Build the legacy App-style temperature transaction.

        Captures show standalone temperature slider writes only after the App
        has placed the device in a temperature-capable mode. Do not send this
        command from dry/fan/unknown contexts.
        """
        if current_mode not in {MODE_COOL, MODE_HEAT}:
            msg = "Legacy temperature writes require a known cool or heat context."
            raise UnsupportedModeError(msg)
        set_temp, degree_h = LegacyTemperatureCodec.encode(
            target_temperature,
            fallback_celsius=target_temperature,
        )
        return TclCommandBundle(
            intent=f"temperature:set:{current_mode}",
            payload={
                "setTemp": set_temp,
                "degreeH": degree_h,
                "optSuper": "0",
            },
            evidence=self._evidence("temperature"),
            requires_power_on=True,
            expected_status={
                "mode": current_mode,
                "target_temp": target_temperature,
            },
        )

    def build_power_off_command(self) -> TclCommandBundle:
        """Build the capture-supported legacy app shutdown bundle."""
        return TclCommandBundle(
            intent="power:off",
            payload={
                "optSleepMd": "0",
                "optECO": "0",
                "optHealthy": "0",
                "optSuper": "0",
                "optHeat": "0",
                "turnOn": "0",
            },
            evidence=self._evidence("power_off"),
            requires_power_on=False,
            expected_status={"power": False},
        )


class Tsl1112013595NProfile(ProtocolProfile):
    """Static-analysis-derived TSL profile for product 1112013595N."""

    _MODE_TO_WORK_MODE = {
        MODE_COOL: 1,
        MODE_DEHUMI: 2,
        MODE_FAN: 3,
        MODE_HEAT: 4,
        MODE_AUTO: 5,
    }

    def __init__(self, device_id: str | None = "45816970") -> None:
        """Initialize the TSL profile for the captured F-series AC."""
        super().__init__(
            device_id=device_id,
            name="tsl_1112013595N",
            capabilities=TSL_1112013595N_CAPABILITIES,
            legacy_transport_enabled=False,
            local_transport_enabled=False,
            cloud_status_family="tsl",
        )

    def _evidence(self, action: str) -> CaptureEvidence:
        return CaptureEvidence(
            level="static-analysis-supported",
            source=(
                "tcl_login_1781544117.jsonl and TCL+ 6.0.4 decompiled "
                "CardACControlView/hg.a/IDevControlModule"
            ),
            rationale=(
                "Protocol 1 device exposes TSL identifiers and TCL+ wraps "
                f"{action} as property-control JSON rather than convertMqtt XML."
            ),
        )

    @staticmethod
    def _normalize_temperature(target_temperature: float) -> float:
        rounded = round(float(target_temperature) * 2) / 2
        return min(31.0, max(16.0, rounded))

    def _property_bundle(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        expected_status: dict[str, Any],
        action: str,
        module_id: str | None = None,
        source_type: str | None = None,
    ) -> TclCommandBundle:
        return TclCommandBundle(
            intent=intent,
            payload=payload,
            evidence=self._evidence(action),
            requires_power_on=False,
            expected_status=expected_status,
            transport=CommandTransport.TSL_PROPERTY,
            module_id=module_id,
            source_type=source_type,
        )

    def build_mode_command(
        self,
        mode: str,
        *,
        target_temperature: float | None = None,
    ) -> TclCommandBundle:
        """Build a TSL property-control mode transaction."""
        work_mode = self._MODE_TO_WORK_MODE.get(mode)
        if work_mode is None:
            msg = f"Unsupported TSL mode: {mode}"
            raise UnsupportedModeError(msg)

        payload: dict[str, Any] = {
            "powerSwitch": 1,
            "workMode": work_mode,
        }
        expected_status: dict[str, Any] = {"power": True, "mode": mode}
        if target_temperature is not None:
            target = self._normalize_temperature(target_temperature)
            payload["targetTemperature"] = target
            expected_status["target_temp"] = target

        return self._property_bundle(
            intent=f"mode:{mode}",
            payload=payload,
            expected_status=expected_status,
            action=f"workMode={work_mode}",
            # RN control panels call the same property bridge with sourceType=2.
            source_type="2",
        )

    def build_temperature_command(
        self,
        target_temperature: float,
        *,
        current_mode: str | None = None,  # noqa: ARG002  # interface parity
    ) -> TclCommandBundle:
        """Build the TSL targetTemperature property transaction."""
        target = self._normalize_temperature(target_temperature)
        return self._property_bundle(
            intent="temperature:set",
            payload={"targetTemperature": target},
            expected_status={"target_temp": target},
            action="targetTemperature",
        )

    def build_power_off_command(self) -> TclCommandBundle:
        """Build the TSL power-off property transaction."""
        return self._property_bundle(
            intent="power:off",
            payload={"powerSwitch": 0},
            expected_status={"power": False},
            action="powerSwitch=0",
            module_id="-100",
        )

    def build_power_on_command(self) -> TclCommandBundle:
        """Build the TSL power-on property transaction."""
        return self._property_bundle(
            intent="power:on",
            payload={"powerSwitch": 1},
            expected_status={"power": True},
            action="powerSwitch=1",
            module_id="-100",
        )

    def build_fan_command(self, fan_mode: str) -> TclCommandBundle:
        """Build the paired TSL automatic/seven-gear fan transaction."""
        if fan_mode == "auto":
            payload = {"windSpeedAutoSwitch": 1, "windSpeed7Gear": 0}
            expected = {"fan_speed": "auto", "fan_gear": 0}
        else:
            try:
                gear = int(fan_mode)
            except (TypeError, ValueError) as exc:
                msg = f"Unsupported TSL fan mode: {fan_mode}"
                raise UnsupportedModeError(msg) from exc
            if gear not in range(1, 8):
                msg = f"Unsupported TSL fan gear: {gear}"
                raise UnsupportedModeError(msg)
            payload = {"windSpeedAutoSwitch": 0, "windSpeed7Gear": gear}
            expected = {"fan_speed": str(gear), "fan_gear": gear}
        return self._property_bundle(
            intent="fan_speed:set",
            payload=payload,
            expected_status=expected,
            action=f"fan={fan_mode}",
            source_type="2",
        )

    def build_swing_command(
        self, *, vertical: bool, horizontal: bool
    ) -> TclCommandBundle:
        """Build TSL swing switches using the device's direction enums."""
        return self._property_bundle(
            intent="swing:set",
            payload={
                "verticalDirection": 1 if vertical else 8,
                "horizontalDirection": 1 if horizontal else 8,
            },
            expected_status={"swing_v": vertical, "swing_h": horizontal},
            action=f"swing vertical={vertical} horizontal={horizontal}",
            source_type="2",
        )

    def build_feature_command(
        self, data_key: str, *, enabled: bool
    ) -> TclCommandBundle:
        """Build one mapped TSL boolean-property transaction."""
        capability = self.capabilities.switches.get(data_key)
        if capability is None:
            msg = f"Unsupported TSL feature: {data_key}"
            raise UnsupportedModeError(msg)
        return self._property_bundle(
            intent=f"switch:{data_key}",
            payload={capability.api_key: 1 if enabled else 0},
            expected_status={data_key: enabled},
            action=f"{capability.api_key}={int(enabled)}",
            source_type="2",
        )

    def build_number_command(self, data_key: str, value: float) -> TclCommandBundle:
        """Build a bounded numeric TSL property transaction."""
        capability = next(
            (item for item in self.capabilities.numbers if item.data_key == data_key),
            None,
        )
        if capability is None:
            msg = f"Unsupported TSL numeric control: {data_key}"
            raise UnsupportedModeError(msg)
        normalized = (
            round(float(value) / capability.native_step) * capability.native_step
        )
        normalized = min(capability.native_max, max(capability.native_min, normalized))
        raw_key = {"fresh_air_percentage": "newWindPercentage"}[data_key]
        return self._property_bundle(
            intent=f"number:{data_key}",
            payload={raw_key: int(normalized)},
            expected_status={data_key: normalized},
            action=f"{raw_key}={normalized}",
            source_type="2",
        )


def resolve_protocol_profile(
    device_id: str | None,
    *,
    product_key: str | None = None,
) -> ProtocolProfile:
    """Compatibility alias for the protocol driver registry."""
    from .protocol_driver import resolve_protocol_driver  # noqa: PLC0415

    return resolve_protocol_driver(device_id, product_key=product_key)  # type: ignore[return-value]
