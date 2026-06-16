"""Switch platform for TCL UDP AC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_CLOUD_TID, LOGGER
from .entity import TclUdpEntity
from .log_utils import log_info
from .protocol_profiles import SwitchCapability, resolve_protocol_profile

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
    config_entry = coordinator.config_entry
    device_id = getattr(config_entry, "options", {}).get(CONF_CLOUD_TID) or getattr(
        config_entry, "data", {}
    ).get(CONF_CLOUD_TID)
    capabilities = resolve_protocol_profile(device_id).capabilities
    async_add_entities(
        [
            TclUdpSwitch(coordinator, capability)
            for capability in capabilities.switches.values()
        ]
    )


async def _async_after_command(coordinator: TclUdpDataUpdateCoordinator) -> None:
    """Confirm command application when the coordinator supports it."""
    confirm = getattr(coordinator, "async_confirm_pending_command", None)
    if confirm is not None:
        await confirm()
        return
    await coordinator.async_request_refresh()


class TclUdpSwitch(TclUdpEntity, SwitchEntity):
    """TCL UDP Switch class."""

    def __init__(
        self,
        coordinator: TclUdpDataUpdateCoordinator,
        capability_or_api_key: SwitchCapability | str,
        data_key: str | None = None,
        _name: str | None = None,
        icon: str | None = None,
        *,
        category: EntityCategory | None = None,
        available_modes: set[str] | None = None,
        requires_power: bool = False,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        if isinstance(capability_or_api_key, SwitchCapability):
            capability = capability_or_api_key
        else:
            if data_key is None or icon is None:
                msg = "data_key and icon are required for switch capability"
                raise ValueError(msg)
            capability = SwitchCapability(
                api_key=capability_or_api_key,
                data_key=data_key,
                translation_key=data_key,
                icon=icon,
                entity_category=category,
                available_modes=(
                    frozenset(available_modes) if available_modes is not None else None
                ),
                requires_power=requires_power,
            )

        self._api_key = capability.api_key
        self._key = capability.api_key
        self._data_key = capability.data_key
        self._attr_name = None
        self._attr_translation_key = capability.translation_key
        self._attr_unique_id = self._entity_unique_id(capability.data_key)
        self._attr_icon = capability.icon
        self._available_modes = capability.available_modes
        self._requires_power = capability.requires_power
        entity_category = capability.entity_category or category
        if entity_category == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        elif isinstance(entity_category, EntityCategory):
            self._attr_entity_category = entity_category

    @property
    def available(self) -> bool:
        """Return if this switch is valid in the current device state."""
        base_available = getattr(super(), "available", True)
        if not base_available:
            return False

        data = self.coordinator.data or {}
        if self._requires_power and data.get("power") is not True:
            return False

        if (
            self._available_modes is not None
            and data.get("mode") not in self._available_modes
        ):
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
            msg = f"{self._attr_name} is not available in the current HVAC mode"
            raise HomeAssistantError(msg)
        log_info(
            LOGGER,
            "entity_switch_turn_on",
            entity=self.entity_id,
            key=self._key,
        )
        await self._async_set_enabled(enabled=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the switch off."""
        log_info(
            LOGGER,
            "entity_switch_turn_off",
            entity=self.entity_id,
            key=self._key,
        )
        await self._async_set_enabled(enabled=False)

    async def _async_set_enabled(self, *, enabled: bool) -> None:
        """Route switch actions to the matching client setter."""
        client = self.coordinator.config_entry.runtime_data.client
        method_name = f"async_set_{self._data_key}"
        if hasattr(client, method_name):
            await getattr(client, method_name)(enabled=enabled)
            await _async_after_command(self.coordinator)
