"""Home Assistant switch entity behavior tests."""

from __future__ import annotations

import asyncio
import sys
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module


install_homeassistant_stubs()


class FakeClient:
    """Record switch client calls."""

    def __init__(self) -> None:
        self.calls = []

    async def async_set_sleep_mode(self, *, enabled: bool) -> None:
        self.calls.append(("async_set_sleep_mode", {"enabled": enabled}))

    async def async_set_aux_heat(self, *, enabled: bool) -> None:
        self.calls.append(("async_set_aux_heat", {"enabled": enabled}))


class FakeCoordinator:
    """Minimal coordinator for switch tests."""

    def __init__(
        self,
        data: dict | None = None,
        *,
        entry_data: dict | None = None,
    ) -> None:
        self.data = data or {}
        self.client = FakeClient()
        self.refresh_count = 0
        self.config_entry = SimpleNamespace(
            entry_id="entry-1",
            domain="tcl_udp_ac",
            data=entry_data or {},
            options={},
            runtime_data=SimpleNamespace(client=self.client),
        )

    async def async_request_refresh(self) -> None:
        self.refresh_count += 1


class SwitchEntityTest(unittest.TestCase):
    """Switches should route to the correct client keyword arguments."""

    def setUp(self) -> None:
        self.switch = load_integration_module("switch")

    def test_setup_does_not_create_duplicate_power_switch(self) -> None:
        coordinator = FakeCoordinator()
        entry = SimpleNamespace(runtime_data=SimpleNamespace(coordinator=coordinator))
        added = []

        def add_entities(entities):
            added.extend(entities)

        asyncio.run(self.switch.async_setup_entry(None, entry, add_entities))

        unique_ids = {entity._attr_unique_id for entity in added}
        self.assertNotIn("entry-1_power", unique_ids)
        self.assertIn("entry-1_eco_mode", unique_ids)

    def test_setup_uses_profile_switch_capabilities_and_translated_names(self) -> None:
        coordinator = FakeCoordinator(entry_data={"cloud_tid": "2743138"})
        entry = SimpleNamespace(runtime_data=SimpleNamespace(coordinator=coordinator))
        added = []

        def add_entities(entities):
            added.extend(entities)

        asyncio.run(self.switch.async_setup_entry(None, entry, add_entities))

        aux_heat = next(entity for entity in added if entity._data_key == "aux_heat")
        eco = next(entity for entity in added if entity._data_key == "eco_mode")

        self.assertEqual(aux_heat._available_modes, frozenset({"heat"}))
        self.assertTrue(aux_heat._requires_power)
        self.assertEqual(aux_heat._attr_unique_id, "2743138_aux_heat")
        self.assertTrue(aux_heat._attr_has_entity_name)
        self.assertIsNone(aux_heat._attr_name)
        self.assertEqual(aux_heat._attr_translation_key, "aux_heat")
        self.assertEqual(eco._attr_translation_key, "eco_mode")

    def test_feature_switch_uses_enabled_keyword(self) -> None:
        coordinator = FakeCoordinator({"sleep_mode": False})
        entity = self.switch.TclUdpSwitch(
            coordinator,
            "optSleepMd",
            "sleep_mode",
            "Sleep Mode",
            "mdi:sleep",
        )

        asyncio.run(entity.async_turn_on())
        asyncio.run(entity.async_turn_off())

        self.assertEqual(
            coordinator.client.calls,
            [
                ("async_set_sleep_mode", {"enabled": True}),
                ("async_set_sleep_mode", {"enabled": False}),
            ],
        )
        self.assertEqual(coordinator.refresh_count, 2)

    def test_aux_heat_is_only_available_when_powered_heat_mode(self) -> None:
        cool_entity = self.switch.TclUdpSwitch(
            FakeCoordinator({"power": True, "mode": "cool"}),
            "optHeat",
            "aux_heat",
            "Aux Heat",
            "mdi:radiator",
            available_modes={"heat"},
            requires_power=True,
        )
        heat_entity = self.switch.TclUdpSwitch(
            FakeCoordinator({"power": True, "mode": "heat"}),
            "optHeat",
            "aux_heat",
            "Aux Heat",
            "mdi:radiator",
            available_modes={"heat"},
            requires_power=True,
        )
        off_entity = self.switch.TclUdpSwitch(
            FakeCoordinator({"power": False, "mode": "heat"}),
            "optHeat",
            "aux_heat",
            "Aux Heat",
            "mdi:radiator",
            available_modes={"heat"},
            requires_power=True,
        )

        self.assertFalse(cool_entity.available)
        self.assertTrue(heat_entity.available)
        self.assertFalse(off_entity.available)

    def test_aux_heat_turn_on_is_blocked_when_mode_unavailable(self) -> None:
        coordinator = FakeCoordinator({"power": True, "mode": "cool"})
        entity = self.switch.TclUdpSwitch(
            coordinator,
            "optHeat",
            "aux_heat",
            "Aux Heat",
            "mdi:radiator",
            available_modes={"heat"},
            requires_power=True,
        )
        exceptions = sys.modules["homeassistant.exceptions"]

        with self.assertRaises(exceptions.HomeAssistantError):
            asyncio.run(entity.async_turn_on())

        self.assertEqual(coordinator.client.calls, [])
        self.assertEqual(coordinator.refresh_count, 0)

    def test_sleep_and_turbo_remain_available_in_cool_mode(self) -> None:
        coordinator = FakeCoordinator({"power": True, "mode": "cool"})

        sleep = self.switch.TclUdpSwitch(
            coordinator,
            "optSleepMd",
            "sleep_mode",
            "Sleep Mode",
            "mdi:sleep",
        )
        turbo = self.switch.TclUdpSwitch(
            coordinator,
            "optSuper",
            "turbo_mode",
            "Turbo Mode",
            "mdi:rocket",
        )

        self.assertTrue(sleep.available)
        self.assertTrue(turbo.available)


if __name__ == "__main__":
    unittest.main()
