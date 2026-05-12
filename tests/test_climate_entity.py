"""Home Assistant climate entity behavior tests."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module


install_homeassistant_stubs()


class FakeClient:
    """Record client calls from entity methods."""

    def __init__(self) -> None:
        self.calls = []

    async def async_set_power(self, *, power: bool) -> None:
        self.calls.append(("async_set_power", {"power": power}))

    async def async_set_power_mode(self, *, power: bool, mode_str: str | None = None) -> None:
        self.calls.append(
            ("async_set_power_mode", {"power": power, "mode_str": mode_str})
        )

    async def async_set_mode_profile(
        self,
        mode_str: str,
        *,
        target_temperature: float | None = None,
    ) -> None:
        self.calls.append(
            (
                "async_set_mode_profile",
                {"mode_str": mode_str, "target_temperature": target_temperature},
            )
        )

    async def async_set_mode(self, mode_str: str) -> None:
        self.calls.append(("async_set_mode", {"mode_str": mode_str}))

    async def async_set_fan_speed(self, speed_str: str) -> None:
        self.calls.append(("async_set_fan_speed", {"speed_str": speed_str}))

    async def async_set_swing(self, *, vertical: bool, horizontal: bool) -> None:
        self.calls.append(
            ("async_set_swing", {"vertical": vertical, "horizontal": horizontal})
        )

    async def async_set_temperature(self, temperature: float) -> None:
        self.calls.append(("async_set_temperature", {"temperature": temperature}))


class FakeCoordinator:
    """Minimal coordinator for entity tests."""

    def __init__(
        self,
        data: dict | None = None,
        *,
        options: dict | None = None,
    ) -> None:
        self.data = data or {}
        self.client = FakeClient()
        self.refresh_count = 0
        self.config_entry = SimpleNamespace(
            entry_id="entry-1",
            domain="tcl_udp_ac",
            data={},
            options=options or {},
            runtime_data=SimpleNamespace(client=self.client),
        )

    async def async_request_refresh(self) -> None:
        self.refresh_count += 1


class ClimateEntityTest(unittest.TestCase):
    """Climate entity should present Celsius and route controls correctly."""

    def setUp(self) -> None:
        self.climate = load_integration_module("climate")

    def test_temperature_attrs_are_celsius_for_home_assistant_ui(self) -> None:
        entity = self.climate.TclUdpClimate(FakeCoordinator())

        self.assertEqual(entity._attr_temperature_unit.value, "°C")
        self.assertEqual(entity._attr_min_temp, 16)
        self.assertEqual(entity._attr_max_temp, 31)
        self.assertEqual(entity._attr_target_temperature_step, 0.5)

    def test_default_hvac_modes_exclude_unverified_fan_and_auto(self) -> None:
        entity = self.climate.TclUdpClimate(FakeCoordinator())

        self.assertEqual(
            entity.hvac_modes,
            [
                self.climate.HVACMode.OFF,
                self.climate.HVACMode.COOL,
                self.climate.HVACMode.DRY,
                self.climate.HVACMode.HEAT,
            ],
        )

    def test_options_can_enable_unverified_fan_and_auto_modes(self) -> None:
        entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                options={
                    "enable_fan_only_mode": True,
                    "enable_auto_mode": True,
                }
            )
        )

        self.assertEqual(
            entity.hvac_modes,
            [
                self.climate.HVACMode.OFF,
                self.climate.HVACMode.COOL,
                self.climate.HVACMode.DRY,
                self.climate.HVACMode.HEAT,
                self.climate.HVACMode.FAN_ONLY,
                self.climate.HVACMode.AUTO,
            ],
        )

    def test_set_temperature_passes_celsius_to_client(self) -> None:
        coordinator = FakeCoordinator({"power": True})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_set_temperature(temperature=23.5))

        self.assertEqual(
            coordinator.client.calls,
            [("async_set_temperature", {"temperature": 23.5})],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_turning_on_from_off_sends_combined_power_and_mode(self) -> None:
        coordinator = FakeCoordinator({"power": False})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_set_hvac_mode(self.climate.HVACMode.COOL))

        self.assertEqual(
            coordinator.client.calls,
            [
                (
                    "async_set_mode_profile",
                    {"mode_str": "cool", "target_temperature": None},
                )
            ],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_turn_on_does_not_restore_disabled_experimental_mode(self) -> None:
        coordinator = FakeCoordinator({"power": False, "mode": "fan"})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_turn_on())

        self.assertEqual(
            coordinator.client.calls,
            [
                (
                    "async_set_mode_profile",
                    {"mode_str": "cool", "target_temperature": None},
                )
            ],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_mode_change_while_on_uses_combined_power_and_mode(self) -> None:
        coordinator = FakeCoordinator({"power": True, "mode": "cool"})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_set_hvac_mode(self.climate.HVACMode.DRY))

        self.assertEqual(
            coordinator.client.calls,
            [
                (
                    "async_set_mode_profile",
                    {"mode_str": "dehumi", "target_temperature": None},
                )
            ],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_turning_off_routes_to_power_off(self) -> None:
        coordinator = FakeCoordinator({"power": True, "mode": "cool"})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_set_hvac_mode(self.climate.HVACMode.OFF))

        self.assertEqual(
            coordinator.client.calls,
            [("async_set_power", {"power": False})],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_fan_and_swing_route_to_grouped_client_methods(self) -> None:
        coordinator = FakeCoordinator({"power": True})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_set_fan_mode(self.climate.FAN_HIGH))
        asyncio.run(entity.async_set_swing_mode(self.climate.SWING_BOTH))

        self.assertEqual(
            coordinator.client.calls,
            [
                ("async_set_fan_speed", {"speed_str": "high"}),
                ("async_set_swing", {"vertical": True, "horizontal": True}),
            ],
        )
        self.assertEqual(coordinator.refresh_count, 2)


if __name__ == "__main__":
    unittest.main()
