"""Home Assistant entities generated from the protocol-1 capability model."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


class FakeClient:
    """Record generic numeric control calls."""

    def __init__(self) -> None:
        self.calls = []

    async def async_set_number(self, data_key, value):
        self.calls.append((data_key, value))


class FakeCoordinator:
    """Provide one TSL config entry and state snapshot."""

    def __init__(self, data=None) -> None:
        self.data = data or {}
        self.client = FakeClient()
        self.refreshes = 0
        self.config_entry = SimpleNamespace(
            entry_id="entry-tsl",
            domain="tcl_udp_ac",
            data={"cloud_tid": "45816970", "cloud_product_key": "1112013595N"},
            options={},
            runtime_data=SimpleNamespace(client=self.client),
        )

    async def async_request_refresh(self):
        self.refreshes += 1


def setup_entities(module_name: str, coordinator: FakeCoordinator):
    """Return entities created by one platform module."""
    module = load_integration_module(module_name)
    entities = []
    entry = SimpleNamespace(runtime_data=SimpleNamespace(coordinator=coordinator))
    asyncio.run(module.async_setup_entry(None, entry, entities.extend))
    return entities


class TslEntityTest(unittest.TestCase):
    """TSL diagnostics and controls should have stable HA semantics."""

    def test_all_diagnostic_descriptions_create_entities(self) -> None:
        coordinator = FakeCoordinator(
            {
                "error_codes": "48",
                "internal_coil_temperature": 25,
                "filter_blocked": True,
            }
        )

        sensors = setup_entities("sensor", coordinator)
        binary = setup_entities("binary_sensor", coordinator)
        sensor_ids = {entity._attr_unique_id for entity in sensors}
        binary_ids = {entity._attr_unique_id for entity in binary}

        self.assertIn("45816970_error_codes", sensor_ids)
        self.assertIn("45816970_internal_coil_temperature", sensor_ids)
        self.assertIn("45816970_tsl_query_time", sensor_ids)
        self.assertIn("45816970_filter_blocked", binary_ids)
        self.assertIn("45816970_aux_heat_active", binary_ids)
        internal = next(
            item
            for item in sensors
            if item._attr_unique_id == "45816970_internal_coil_temperature"
        )
        self.assertEqual(internal.native_value, 25)
        self.assertTrue(internal.available)

    def test_missing_diagnostic_is_unavailable_instead_of_fabricated(self) -> None:
        coordinator = FakeCoordinator()
        sensors = setup_entities("sensor", coordinator)
        query_time = next(
            item
            for item in sensors
            if item._attr_unique_id == "45816970_tsl_query_time"
        )

        self.assertFalse(query_time.available)
        self.assertIsNone(query_time.native_value)

    def test_fresh_air_number_uses_profile_range_and_generic_dispatch(self) -> None:
        coordinator = FakeCoordinator({"fresh_air_percentage": 33})
        numbers = setup_entities("number", coordinator)

        self.assertEqual(len(numbers), 1)
        entity = numbers[0]
        self.assertEqual(entity._attr_unique_id, "45816970_fresh_air_percentage")
        self.assertEqual(entity._attr_native_min_value, 0)
        self.assertEqual(entity._attr_native_max_value, 100)
        self.assertEqual(entity.native_value, 33)

        asyncio.run(entity.async_set_native_value(45))

        self.assertEqual(coordinator.client.calls, [("fresh_air_percentage", 45)])
        self.assertEqual(coordinator.refreshes, 1)


if __name__ == "__main__":
    unittest.main()
