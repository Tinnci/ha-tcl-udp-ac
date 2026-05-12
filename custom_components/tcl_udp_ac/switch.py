"""Switch platform for TCL UDP AC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from .const import LOGGER, MODE_HEAT
from .entity import TclUdpEntity
from .log_utils import log_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TclUdpDataUpdateCoordinator
    from .data import TclUdpConfigEntry


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TclUdpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            TclUdpSwitch(coordinator, "optECO", "eco_mode", "Eco Mode", "mdi:leaf"),
            TclUdpSwitch(
                coordinator,
                "optDisplay",
                "display",
                "Display",
                "mdi:led-on",
                EntityCategory.CONFIG,
            ),
            TclUdpSwitch(
                coordinator, "optHealthy", "health_mode", "Health Mode", "mdi:doctor"
            ),
            TclUdpSwitch(
                coordinator, "optSleepMd", "sleep_mode", "Sleep Mode", "mdi:sleep"
            ),
            TclUdpSwitch(
                coordinator, "optSuper", "turbo_mode", "Turbo Mode", "mdi:rocket"
            ),
            TclUdpSwitch(
                coordinator,
                "optHeat",
                "aux_heat",
                "Aux Heat",
                "mdi:radiator",
                available_modes={MODE_HEAT},
                requires_power=True,
            ),
            TclUdpSwitch(
                coordinator,
                "beepEn",
                "beep",
                "Beep",
                "mdi:volume-high",
                EntityCategory.CONFIG,
            ),
        ]
    )


class TclUdpSwitch(TclUdpEntity, SwitchEntity):
    """TCL UDP Switch class."""

    def __init__(  # noqa: PLR0913
        self,
        coordinator: TclUdpDataUpdateCoordinator,
        api_key: str,
        data_key: str,
        name: str,
        icon: str,
        category: EntityCategory | None = None,
        available_modes: set[str] | None = None,
        requires_power: bool = False,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._api_key = api_key
        self._key = api_key
        self._data_key = data_key
        self._attr_name = f"TCL AC {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{data_key}"
        self._attr_icon = icon
        self._available_modes = available_modes
        self._requires_power = requires_power
        if category:
            self._attr_entity_category = category

    @property
    def available(self) -> bool:
        """Return if this switch is valid in the current device state."""
        base_available = getattr(super(), "available", True)
        if not base_available:
            return False

        data = self.coordinator.data or {}
        if self._requires_power and data.get("power") is not True:
            return False

        if self._available_modes is not None and data.get("mode") not in self._available_modes:
            return False

        return True

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._data_key)
        return None

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn the switch on."""
        if not self.available:
            raise HomeAssistantError(
                f"{self._attr_name} is not available in the current HVAC mode"
            )
        log_info(
            LOGGER,
            "entity_switch_turn_on",
            entity=self.entity_id,
            key=self._key,
        )
        await self._async_set_enabled(True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the switch off."""
        log_info(
            LOGGER,
            "entity_switch_turn_off",
            entity=self.entity_id,
            key=self._key,
        )
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        """Route switch actions to the matching client setter."""
        client = self.coordinator.config_entry.runtime_data.client
        method_name = f"async_set_{self._data_key}"
        if hasattr(client, method_name):
            await getattr(client, method_name)(enabled=enabled)
            await self.coordinator.async_request_refresh()
