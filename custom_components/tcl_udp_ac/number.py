"""Writable numeric controls for TCL protocol profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory

from .config_settings import capabilities_for_entry
from .entity import TclUdpEntity
from .protocol_profiles import NumberCapability

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
    """Set up profile-described numeric controls."""
    coordinator = entry.runtime_data.coordinator
    capabilities = capabilities_for_entry(coordinator.config_entry)
    async_add_entities(
        [TclUdpNumber(coordinator, capability) for capability in capabilities.numbers]
    )


class TclUdpNumber(TclUdpEntity, NumberEntity):
    """One bounded numeric TSL property."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: TclUdpDataUpdateCoordinator,
        capability: NumberCapability,
    ) -> None:
        """Initialize the number from its protocol capability."""
        super().__init__(coordinator)
        self._capability = capability
        self._attr_translation_key = capability.translation_key
        self._attr_unique_id = self._entity_unique_id(capability.data_key)
        self._attr_icon = capability.icon
        self._attr_native_min_value = capability.native_min
        self._attr_native_max_value = capability.native_max
        self._attr_native_step = capability.native_step
        self._attr_native_unit_of_measurement = capability.native_unit

    @property
    def native_value(self) -> float | None:
        """Return the latest value reported by the device."""
        value = (self.coordinator.data or {}).get(self._capability.data_key)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the numeric property and confirm it through refreshed state."""
        runtime = self.coordinator.config_entry.runtime_data
        client: Any = getattr(runtime, "session", None) or runtime.client
        command_id = await client.async_set_number(self._capability.data_key, value)
        confirm = getattr(self.coordinator, "async_confirm_pending_command", None)
        if confirm is not None and command_id is not None:
            await confirm(command_id=command_id)
        else:
            await self.coordinator.async_request_refresh()
