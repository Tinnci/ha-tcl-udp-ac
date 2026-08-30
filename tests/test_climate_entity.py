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

    async def async_set_power_mode(
        self, *, power: bool, mode_str: str | None = None
    ) -> None:
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
        entry_data: dict | None = None,
        options: dict | None = None,
    ) -> None:
        self.data = data or {}
        self.client = FakeClient()
        self.refresh_count = 0
        self.config_entry = SimpleNamespace(
            entry_id="entry-1",
            domain="tcl_udp_ac",
            data=entry_data or {},
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

    def test_exposes_over_climate_contract_for_versatile_thermostat(self) -> None:
        entity = self.climate.TclUdpClimate(FakeCoordinator())
        features = entity._attr_supported_features

        self.assertIn(self.climate.HVACMode.OFF, entity.hvac_modes)
        self.assertIn(self.climate.HVACMode.COOL, entity.hvac_modes)
        self.assertTrue(features & self.climate.ClimateEntityFeature.TARGET_TEMPERATURE)
        self.assertTrue(features & self.climate.ClimateEntityFeature.TURN_ON)
        self.assertTrue(features & self.climate.ClimateEntityFeature.TURN_OFF)
        self.assertIsNotNone(entity.hvac_action)

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

    def test_hvac_action_reports_off_when_powered_off(self) -> None:
        entity = self.climate.TclUdpClimate(FakeCoordinator({"power": False}))

        self.assertEqual(entity.hvac_action, self.climate.HVACAction.OFF)

    def test_legacy_profile_blocks_unsupported_auto_even_if_option_enabled(
        self,
    ) -> None:
        entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                entry_data={"cloud_tid": "2743138"},
                options={
                    "enable_fan_only_mode": True,
                    "enable_auto_mode": True,
                },
            )
        )

        self.assertIn(self.climate.HVACMode.FAN_ONLY, entity.hvac_modes)
        self.assertNotIn(self.climate.HVACMode.AUTO, entity.hvac_modes)

    def test_tsl_product_key_exposes_seven_gear_fan_and_swing_features(self) -> None:
        entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                entry_data={
                    "cloud_tid": "other-device",
                    "cloud_product_key": "1112013595N",
                }
            )
        )
        features = entity._attr_supported_features

        self.assertTrue(features & self.climate.ClimateEntityFeature.FAN_MODE)
        self.assertTrue(features & self.climate.ClimateEntityFeature.SWING_MODE)
        self.assertEqual(
            entity._attr_fan_modes, ["auto", "1", "2", "3", "4", "5", "6", "7"]
        )
        self.assertEqual(
            entity._attr_swing_modes, ["off", "vertical", "horizontal", "both"]
        )

    def test_tsl_seven_gear_fan_round_trips_without_legacy_compression(self) -> None:
        coordinator = FakeCoordinator(
            {"fan_speed": "6"},
            entry_data={
                "cloud_tid": "45816970",
                "cloud_product_key": "1112013595N",
            },
        )
        entity = self.climate.TclUdpClimate(coordinator)

        self.assertEqual(entity.fan_mode, "6")
        asyncio.run(entity.async_set_fan_mode("7"))

        self.assertIn(
            ("async_set_fan_speed", {"speed_str": "7"}), coordinator.client.calls
        )

    def test_entity_uses_modern_ha_naming_and_stable_device_identifier(self) -> None:
        entity = self.climate.TclUdpClimate(
            FakeCoordinator(entry_data={"cloud_tid": "2743138"})
        )

        self.assertTrue(entity._attr_has_entity_name)
        self.assertIsNone(entity._attr_name)
        self.assertEqual(entity._attr_unique_id, "2743138_climate")
        self.assertEqual(
            entity._attr_device_info["identifiers"],
            {("tcl_udp_ac", "2743138")},
        )

    def test_descriptor_presentation_does_not_change_stable_identifier(self) -> None:
        entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                entry_data={
                    "cloud_tid": "45816970",
                    "device_name": "Living room AC",
                    "device_room": "Living room",
                    "device_model": "KFRd-35G/D-STA22Bp(B1)",
                }
            )
        )

        self.assertEqual(entity._attr_unique_id, "45816970_climate")
        self.assertEqual(entity._attr_device_info["name"], "Living room AC")
        self.assertEqual(entity._attr_device_info["suggested_area"], "Living room")
        self.assertEqual(entity._attr_device_info["model"], "KFRd-35G/D-STA22Bp(B1)")

    def test_climate_does_not_fabricate_humidity_properties(self) -> None:
        entity = self.climate.TclUdpClimate(FakeCoordinator())

        self.assertFalse(hasattr(entity, "current_humidity"))
        self.assertFalse(hasattr(entity, "target_humidity"))

    def test_hvac_action_reports_cooling_when_above_cooling_setpoint(self) -> None:
        entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                {
                    "power": True,
                    "mode": "cool",
                    "current_temp": 27.0,
                    "target_temp": 24.0,
                }
            )
        )

        self.assertEqual(entity.hvac_action, self.climate.HVACAction.COOLING)

    def test_hvac_action_reports_heating_when_below_heating_setpoint(self) -> None:
        entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                {
                    "power": True,
                    "mode": "heat",
                    "current_temp": 20.0,
                    "target_temp": 24.0,
                }
            )
        )

        self.assertEqual(entity.hvac_action, self.climate.HVACAction.HEATING)

    def test_hvac_action_reports_idle_when_setpoint_is_reached(self) -> None:
        cool_entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                {
                    "power": True,
                    "mode": "cool",
                    "current_temp": 23.0,
                    "target_temp": 24.0,
                }
            )
        )
        heat_entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                {
                    "power": True,
                    "mode": "heat",
                    "current_temp": 25.0,
                    "target_temp": 24.0,
                }
            )
        )

        self.assertEqual(cool_entity.hvac_action, self.climate.HVACAction.IDLE)
        self.assertEqual(heat_entity.hvac_action, self.climate.HVACAction.IDLE)

    def test_hvac_action_reports_mode_actions_for_dry_and_fan(self) -> None:
        dry_entity = self.climate.TclUdpClimate(
            FakeCoordinator({"power": True, "mode": "dehumi"})
        )
        fan_entity = self.climate.TclUdpClimate(
            FakeCoordinator(
                {"power": True, "mode": "fan"},
                options={"enable_fan_only_mode": True},
            )
        )

        self.assertEqual(dry_entity.hvac_action, self.climate.HVACAction.DRYING)
        self.assertEqual(fan_entity.hvac_action, self.climate.HVACAction.FAN)

    def test_set_temperature_while_on_uses_grouped_current_mode_profile(self) -> None:
        coordinator = FakeCoordinator({"power": True, "mode": "cool"})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_set_temperature(temperature=23.5))

        self.assertEqual(
            coordinator.client.calls,
            [
                (
                    "async_set_mode_profile",
                    {"mode_str": "cool", "target_temperature": 23.5},
                )
            ],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_set_temperature_without_current_mode_uses_temperature_service(
        self,
    ) -> None:
        coordinator = FakeCoordinator({"power": False})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(entity.async_set_temperature(temperature=23.5))

        self.assertEqual(
            coordinator.client.calls,
            [("async_set_temperature", {"temperature": 23.5})],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_set_temperature_with_hvac_mode_uses_grouped_mode_profile(self) -> None:
        coordinator = FakeCoordinator({"power": False})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(
            entity.async_set_temperature(
                temperature=23.5,
                hvac_mode=self.climate.HVACMode.COOL,
            )
        )

        self.assertEqual(
            coordinator.client.calls,
            [
                (
                    "async_set_mode_profile",
                    {"mode_str": "cool", "target_temperature": 23.5},
                )
            ],
        )
        self.assertEqual(coordinator.refresh_count, 1)

    def test_set_temperature_with_off_hvac_mode_turns_off_without_temp_write(
        self,
    ) -> None:
        coordinator = FakeCoordinator({"power": True, "mode": "cool"})
        entity = self.climate.TclUdpClimate(coordinator)

        asyncio.run(
            entity.async_set_temperature(
                temperature=23.5,
                hvac_mode=self.climate.HVACMode.OFF,
            )
        )

        self.assertEqual(
            coordinator.client.calls,
            [("async_set_power", {"power": False})],
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
