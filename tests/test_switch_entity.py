"""Home Assistant switch entity behavior tests."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module


install_homeassistant_stubs()


class FakeClient:
    """Record switch client calls."""

    def __init__(self) -> None:
        self.calls = []

    async def async_set_power(self, *, power: bool) -> None:
        self.calls.append(("async_set_power", {"power": power}))

    async def async_set_sleep_mode(self, *, enabled: bool) -> None:
        self.calls.append(("async_set_sleep_mode", {"enabled": enabled}))


class FakeCoordinator:
    """Minimal coordinator for switch tests."""

    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {}
        self.client = FakeClient()
        self.refresh_count = 0
        self.config_entry = SimpleNamespace(
            entry_id="entry-1",
            domain="tcl_udp_ac",
            runtime_data=SimpleNamespace(client=self.client),
        )

    async def async_request_refresh(self) -> None:
        self.refresh_count += 1


class SwitchEntityTest(unittest.TestCase):
    """Switches should route to the correct client keyword arguments."""

    def setUp(self) -> None:
        self.switch = load_integration_module("switch")

    def test_power_switch_uses_power_keyword(self) -> None:
        coordinator = FakeCoordinator({"power": False})
        entity = self.switch.TclUdpSwitch(
            coordinator,
            "turnOn",
            "power",
            "Power",
            "mdi:power",
        )

        self.assertFalse(entity._attr_entity_registry_enabled_default)

        asyncio.run(entity.async_turn_on())
        asyncio.run(entity.async_turn_off())

        self.assertEqual(
            coordinator.client.calls,
            [
                ("async_set_power", {"power": True}),
                ("async_set_power", {"power": False}),
            ],
        )
        self.assertEqual(coordinator.refresh_count, 2)

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


if __name__ == "__main__":
    unittest.main()
