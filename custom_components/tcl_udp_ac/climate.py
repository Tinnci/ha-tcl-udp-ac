"""Climate platform for TCL UDP AC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .config_settings import capabilities_for_entry, entry_value
from .const import (
    COMMAND_NOT_SENT_MESSAGE,
    CONF_ENABLE_AUTO_MODE,
    CONF_ENABLE_FAN_ONLY_MODE,
    DEFAULT_ENABLE_AUTO_MODE,
    DEFAULT_ENABLE_FAN_ONLY_MODE,
    LOGGER,
)
from .const import (
    FAN_AUTO as TCL_FAN_AUTO,
)
from .const import (
    FAN_HIGH as TCL_FAN_HIGH,
)
from .const import (
    FAN_LOW as TCL_FAN_LOW,
)
from .const import (
    FAN_MIDDLE as TCL_FAN_MIDDLE,
)
from .const import (
    MODE_AUTO as TCL_MODE_AUTO,
)
from .const import (
    MODE_COOL as TCL_MODE_COOL,
)
from .const import (
    MODE_DEHUMI as TCL_MODE_DEHUMI,
)
from .const import (
    MODE_FAN as TCL_MODE_FAN,
)
from .const import (
    MODE_HEAT as TCL_MODE_HEAT,
)
from .entity import TclUdpEntity
from .log_utils import log_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TclUdpDataUpdateCoordinator
    from .data import TclUdpConfigEntry
    from .protocol_profiles import DeviceCapabilities

# Protocol mappings
# Fan Speed
FAN_MODE_MAP = {
    FAN_AUTO: TCL_FAN_AUTO,
    FAN_LOW: TCL_FAN_LOW,
    FAN_MEDIUM: TCL_FAN_MIDDLE,
    FAN_HIGH: TCL_FAN_HIGH,
}
FAN_MODE_MAP_REV = {v: k for k, v in FAN_MODE_MAP.items()}

# mode: HA Mode -> API String
HVAC_MODE_MAP = {
    HVACMode.AUTO: TCL_MODE_AUTO,
    HVACMode.COOL: TCL_MODE_COOL,
    HVACMode.DRY: TCL_MODE_DEHUMI,
    HVACMode.FAN_ONLY: TCL_MODE_FAN,
    HVACMode.HEAT: TCL_MODE_HEAT,
}
HVAC_MODE_MAP_REV = {v: k for k, v in HVAC_MODE_MAP.items()}


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TclUdpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    async_add_entities([TclUdpClimate(entry.runtime_data.coordinator)])


def _device_api(coordinator: TclUdpDataUpdateCoordinator) -> Any:
    """Return the migrated device session or the compatibility client."""
    runtime = coordinator.config_entry.runtime_data
    return getattr(runtime, "session", None) or runtime.client


async def _async_after_command(
    coordinator: TclUdpDataUpdateCoordinator,
    command_id: str | None = None,
    *,
    entity_id: str | None = None,
    context_id: str | None = None,
) -> None:
    """Confirm command application when the coordinator supports it."""
    client = _device_api(coordinator)
    annotate = getattr(client, "annotate_pending_command", None)
    if annotate is not None:
        annotate(
            command_id,
            entity_id=entity_id,
            context_id=context_id,
        )
    confirm = getattr(coordinator, "async_confirm_pending_command", None)
    if confirm is not None:
        if command_id is not None:
            await confirm(command_id=command_id)
        elif (
            getattr(coordinator.config_entry.runtime_data, "session", None) is not None
        ):
            reporter = getattr(
                coordinator, "async_report_command_delivery_failure", None
            )
            if reporter is not None and await reporter(
                entity_id=entity_id,
                context_id=context_id,
            ):
                raise HomeAssistantError(COMMAND_NOT_SENT_MESSAGE)
            await coordinator.async_request_refresh()
        else:
            await confirm()
        return
    await coordinator.async_request_refresh()


class TclUdpClimate(TclUdpEntity, ClimateEntity):
    """TCL UDP AC Climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_fan_modes: ClassVar[list[str]] = [
        FAN_AUTO,
        FAN_LOW,
        FAN_MEDIUM,
        FAN_HIGH,
    ]
    _attr_swing_modes: ClassVar[list[str]] = [
        SWING_OFF,
        SWING_VERTICAL,
        SWING_HORIZONTAL,
        SWING_BOTH,
    ]
    _attr_min_temp = 16
    _attr_max_temp = 31
    _attr_target_temperature_step = 0.5
    _attr_precision = 0.1

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_name = None
        self._attr_unique_id = self._entity_unique_id("climate")
        capabilities = self._capabilities()
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if capabilities.supports_fan_speed:
            features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = list(capabilities.fan_modes)
        else:
            self._attr_fan_modes = []
        if capabilities.supports_swing:
            features |= ClimateEntityFeature.SWING_MODE
        else:
            self._attr_swing_modes = []
        self._attr_supported_features = features
        self._attr_hvac_modes = self._build_hvac_modes()

    def _capabilities(self) -> DeviceCapabilities:
        """Return profile capabilities for this config entry."""
        return capabilities_for_entry(self.coordinator.config_entry)

    async def _async_after_device_command(self, command_id: str | None) -> None:
        """Confirm a command with its HA entity and service-call context."""
        context = getattr(self, "_context", None)
        await _async_after_command(
            self.coordinator,
            command_id,
            entity_id=self.entity_id,
            context_id=getattr(context, "id", None),
        )

    def _entry_option(self, key: str, *, default: bool) -> bool:
        """Return boolean option from config entry options or data."""
        return bool(entry_value(self.coordinator.config_entry, key, default))

    def _build_hvac_modes(self) -> list[HVACMode]:
        """Build supported HVAC modes from verified modes plus opt-ins."""
        capabilities = self._capabilities()
        modes = [HVACMode.OFF]
        modes.extend(
            HVAC_MODE_MAP_REV[mode]
            for mode in capabilities.verified_hvac_modes
            if mode in HVAC_MODE_MAP_REV
        )
        if TCL_MODE_FAN in capabilities.experimental_hvac_modes and self._entry_option(
            CONF_ENABLE_FAN_ONLY_MODE, default=DEFAULT_ENABLE_FAN_ONLY_MODE
        ):
            modes.append(HVACMode.FAN_ONLY)
        if TCL_MODE_AUTO in capabilities.experimental_hvac_modes and self._entry_option(
            CONF_ENABLE_AUTO_MODE, default=DEFAULT_ENABLE_AUTO_MODE
        ):
            modes.append(HVACMode.AUTO)
        return modes

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return supported HVAC modes."""
        return self._attr_hvac_modes

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self._reported_state().get("current_temp")
        if value is not None:
            return float(value)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        value = self._reported_state().get("target_temp")
        if value is not None:
            return float(value)
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the reported power and mode without guessing missing feedback."""
        data = self._reported_state()
        if data.get("power") is False:
            return HVACMode.OFF
        if data.get("power") is True:
            return HVAC_MODE_MAP_REV.get(data.get("mode"))
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return conclusive mode feedback without a thermostat-derived action."""
        mode = self.hvac_mode
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        # Indoor temperature and target do not observe compressor operation.
        # Keep separately reported TSL diagnostics available in their own entities.
        return None

    @property
    def extra_state_attributes(self) -> dict[str, bool | str | float | None]:
        """Let consumers distinguish this feedback from older temperature estimates."""
        capabilities = self._capabilities()
        attrs: dict[str, bool | str | float | None] = {
            "hvac_action_is_estimated": False,
            "target_temp_step_c": capabilities.target_temp_step_c,
            "target_temp_tolerance_c": capabilities.target_temp_tolerance_c,
        }
        snapshot = self._state_snapshot()
        if snapshot is not None:
            required = (
                ("power",)
                if snapshot.values.get("power") is False
                else ("power", "mode")
            )
            attrs["hvac_mode_observed_at"] = snapshot.observed_at(*required)
            attrs["hvac_action_observed_at"] = (
                attrs["hvac_mode_observed_at"]
                if self.hvac_action in (HVACAction.OFF, HVACAction.FAN)
                else None
            )
        return attrs

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        data = self._reported_state()
        if not data:
            return None
        speed_val = data.get("fan_speed")
        if speed_val in self._attr_fan_modes:
            return str(speed_val)
        return FAN_MODE_MAP_REV.get(speed_val)

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        data = self._reported_state()
        if "swing_h" not in data or "swing_v" not in data:
            return None

        swing_h = data["swing_h"]
        swing_v = data["swing_v"]

        if swing_h and swing_v:
            return SWING_BOTH
        if swing_h:
            return SWING_HORIZONTAL
        if swing_v:
            return SWING_VERTICAL
        return SWING_OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get("hvac_mode")
        client = _device_api(self.coordinator)

        # A same-mode temperature adjustment must not replay a mode bundle:
        # legacy mode bundles reset fan speed, undoing a quiet fan selection.
        current_mode = self.hvac_mode
        if (
            temperature is not None
            and current_mode in (HVACMode.COOL, HVACMode.HEAT)
            and (hvac_mode is None or hvac_mode == current_mode)
        ):
            command_id = await client.async_set_temperature(float(temperature))
            await self._async_after_device_command(command_id)
            return

        if hvac_mode is not None:
            try:
                ha_mode = HVACMode(hvac_mode)
            except ValueError:
                return

            if ha_mode == HVACMode.OFF:
                command_id = await client.async_set_power(power=False)
                await self._async_after_device_command(command_id)
                return

            udp_mode = HVAC_MODE_MAP.get(ha_mode)
            if udp_mode is None:
                return

            target_temperature = (
                float(temperature)
                if temperature is not None
                else self.target_temperature
            )
            command_id = await client.async_set_mode_profile(
                udp_mode,
                target_temperature=target_temperature,
            )
            await self._async_after_device_command(command_id)
            return

        if temperature is not None:
            log_info(
                LOGGER,
                "entity_set_temperature",
                entity=self.entity_id,
                temperature=temperature,
            )
            udp_mode = HVAC_MODE_MAP.get(self.hvac_mode)
            if self.hvac_mode != HVACMode.OFF and udp_mode is not None:
                command_id = await client.async_set_mode_profile(
                    udp_mode,
                    target_temperature=float(temperature),
                )
                await self._async_after_device_command(command_id)
                return

            command_id = await client.async_set_temperature(float(temperature))
            await self._async_after_device_command(command_id)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        log_info(
            LOGGER,
            "entity_set_hvac_mode",
            entity=self.entity_id,
            hvac_mode=hvac_mode,
        )
        client = _device_api(self.coordinator)

        if hvac_mode == HVACMode.OFF:
            command_id = await client.async_set_power(power=False)
        else:
            udp_mode = HVAC_MODE_MAP.get(hvac_mode)
            is_on = bool(self.coordinator.data and self.coordinator.data.get("power"))

            if not is_on or udp_mode is not None:
                command_id = await client.async_set_mode_profile(
                    udp_mode,
                    target_temperature=self.target_temperature,
                )
            else:
                command_id = None

        await self._async_after_device_command(command_id)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        log_info(
            LOGGER,
            "entity_set_fan_mode",
            entity=self.entity_id,
            fan_mode=fan_mode,
        )
        client = _device_api(self.coordinator)

        speed_val = FAN_MODE_MAP.get(
            fan_mode,
            fan_mode if fan_mode in self._attr_fan_modes else None,
        )
        if speed_val is not None:
            command_id = await client.async_set_fan_speed(speed_val)
            await self._async_after_device_command(command_id)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        log_info(
            LOGGER,
            "entity_set_swing_mode",
            entity=self.entity_id,
            swing_mode=swing_mode,
        )
        client = _device_api(self.coordinator)

        vertical = swing_mode in (SWING_VERTICAL, SWING_BOTH)
        horizontal = swing_mode in (SWING_HORIZONTAL, SWING_BOTH)

        command_id = await client.async_set_swing(
            vertical=vertical, horizontal=horizontal
        )
        await self._async_after_device_command(command_id)

    async def async_turn_on(self) -> None:
        """Turn on the AC."""
        log_info(LOGGER, "entity_turn_on", entity=self.entity_id)
        # Restore last known mode, or default to COOL if unknown
        data = self.coordinator.data
        last_mode = data.get("mode") if data else None
        ha_mode = (
            HVAC_MODE_MAP_REV.get(last_mode, HVACMode.COOL)
            if last_mode
            else HVACMode.COOL
        )
        if ha_mode not in self.hvac_modes or ha_mode == HVACMode.OFF:
            ha_mode = HVACMode.COOL
        await self.async_set_hvac_mode(ha_mode)

    async def async_turn_off(self) -> None:
        """Turn off the AC."""
        log_info(LOGGER, "entity_turn_off", entity=self.entity_id)
        await self.async_set_hvac_mode(HVACMode.OFF)
