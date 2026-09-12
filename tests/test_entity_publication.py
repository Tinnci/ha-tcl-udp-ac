"""Entity publication must preserve physical transitions and bounded freshness."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import Mock, patch

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module
from tests.test_tsl_entities import FakeCoordinator, setup_entities

install_homeassistant_stubs()


class EntityPublicationTest(unittest.TestCase):
    def setUp(self):
        self.module = load_integration_module("entity")
        self.entity = self.module.TclUdpEntity(FakeCoordinator())
        self.entity.hass = Mock()
        self.entity.available = True
        self.entity.state = "cool"
        self.entity.state_attributes = {
            "temperature": 25.0,
            "current_temperature": 26.01,
        }
        self.entity.extra_state_attributes = {"hvac_mode_observed_at": "original"}
        self.entity.async_write_ha_state = Mock()

    def test_identical_feedback_coalesces_but_small_temperature_changes_publish(self):
        cancel = Mock()
        with (
            patch.object(self.module.time, "monotonic", return_value=100) as clock,
            patch.object(self.module, "async_call_later", return_value=cancel) as later,
        ):
            self.entity._handle_coordinator_update()
            clock.return_value = 105
            self.entity.extra_state_attributes["hvac_mode_observed_at"] = "latest"
            self.entity._handle_coordinator_update()
            self.assertEqual(self.entity.async_write_ha_state.call_count, 1)
            later.assert_called_once()

            self.entity.state_attributes["temperature"] = 25.01
            self.entity._handle_coordinator_update()
            self.assertEqual(self.entity.async_write_ha_state.call_count, 2)
            cancel.assert_called_once()
            self.entity.available = False
            self.entity._handle_coordinator_update()
            self.assertEqual(self.entity.async_write_ha_state.call_count, 3)

    def test_pending_flush_retains_original_report_time_and_unload_cancels_it(self):
        cancel = Mock()
        with (
            patch.object(self.module.time, "monotonic", return_value=100) as clock,
            patch.object(self.module, "async_call_later", return_value=cancel) as later,
        ):
            self.entity._handle_coordinator_update()
            clock.return_value = 105
            self.entity.extra_state_attributes["hvac_mode_observed_at"] = (
                "received-at-105"
            )
            self.entity._handle_coordinator_update()
            clock.return_value = 220
            later.call_args.args[2](None)
            self.assertEqual(self.entity.async_write_ha_state.call_count, 2)
            self.assertEqual(
                self.entity.extra_state_attributes["hvac_mode_observed_at"],
                "received-at-105",
            )
            clock.return_value = 225
            self.entity._handle_coordinator_update()
            asyncio.run(self.entity.async_will_remove_from_hass())
            self.assertEqual(cancel.call_count, 2)

    def test_only_protocol_metadata_is_disabled_by_default(self):
        entities = setup_entities("sensor", FakeCoordinator())
        diagnostics = {
            entity._capability.data_key: entity
            for entity in entities
            if hasattr(entity, "_capability")
        }
        for key in ("tsl_version", "tsl_request_version", "tsl_query_time"):
            self.assertFalse(diagnostics[key]._attr_entity_registry_enabled_default)
        for key in ("compressor_frequency", "expansion_valve", "external_current"):
            self.assertTrue(diagnostics[key]._attr_entity_registry_enabled_default)
        for key in ("expansion_valve", "internal_fan_speed", "external_fan_speed"):
            self.assertEqual(diagnostics[key]._attr_state_class, "measurement")
            self.assertIsNone(diagnostics[key]._attr_native_unit_of_measurement)


if __name__ == "__main__":
    unittest.main()
