"""Coordinator and integration lifecycle regression tests."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
import warnings
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import PACKAGE, ROOT, load_integration_module

install_homeassistant_stubs()


def load_integration_init():
    """Load the integration package `__init__` module for lifecycle tests."""
    sys.modules.pop(PACKAGE, None)
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / "tcl_udp_ac")]
    package.__package__ = PACKAGE
    sys.modules[PACKAGE] = package

    path = ROOT / "custom_components" / "tcl_udp_ac" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        PACKAGE,
        path,
        submodule_search_locations=[str(ROOT / "custom_components" / "tcl_udp_ac")],
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OrchestratorLifecycleTest(unittest.TestCase):
    """Integration setup/unload should follow Home Assistant lifecycle semantics."""

    def test_setup_listener_failure_is_retryable_config_entry_not_ready(self) -> None:
        init_mod = load_integration_init()
        exceptions = sys.modules["homeassistant.exceptions"]

        class FailingClient:
            def set_token_manager(self, _token_manager):
                pass

            async def async_start_listener(self, _callback):
                raise load_integration_module("api").TclUdpApiClientCommunicationError(
                    "port in use"
                )

            async def async_close(self):
                pass

        init_mod.TclUdpApiClient = lambda **_kwargs: FailingClient()
        hass = SimpleNamespace(config_entries=SimpleNamespace())
        entry = SimpleNamespace(data={}, options={}, domain="tcl_udp_ac")

        with self.assertRaises(exceptions.ConfigEntryNotReady):
            asyncio.run(init_mod.async_setup_entry(hass, entry))

    def test_unload_closes_client_only_after_platforms_unload_success(self) -> None:
        init_mod = load_integration_init()
        events: list[str] = []

        class Client:
            async def async_close(self):
                events.append("close")

        async def unload_platforms(_entry, _platforms):
            events.append("unload")
            return True

        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_unload_platforms=unload_platforms)
        )
        entry = SimpleNamespace(runtime_data=SimpleNamespace(client=Client()))

        result = asyncio.run(init_mod.async_unload_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(events, ["unload", "close"])

    def test_unload_failure_leaves_client_open(self) -> None:
        init_mod = load_integration_init()
        events: list[str] = []

        class Client:
            async def async_close(self):
                events.append("close")

        async def unload_platforms(_entry, _platforms):
            events.append("unload")
            return False

        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_unload_platforms=unload_platforms)
        )
        entry = SimpleNamespace(runtime_data=SimpleNamespace(client=Client()))

        result = asyncio.run(init_mod.async_unload_entry(hass, entry))

        self.assertFalse(result)
        self.assertEqual(events, ["unload"])

    def test_credential_only_update_does_not_reload_runtime(self) -> None:
        init_mod = load_integration_init()
        settings = load_integration_module("config_settings")
        reloads = []

        async def reload_entry(entry_id):
            reloads.append(entry_id)

        entry = SimpleNamespace(
            entry_id="entry-1",
            data={"cloud_access_token": "old", "cloud_tid": "device-1"},
            options={},
        )
        entry.runtime_data = SimpleNamespace(
            reload_signature=settings.reload_signature(entry)
        )
        entry.data = {"cloud_access_token": "new", "cloud_tid": "device-1"}
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_reload=reload_entry)
        )

        asyncio.run(init_mod.async_reload_entry(hass, entry))

        self.assertEqual(reloads, [])

    def test_non_credential_update_reloads_runtime(self) -> None:
        init_mod = load_integration_init()
        settings = load_integration_module("config_settings")
        reloads = []

        async def reload_entry(entry_id):
            reloads.append(entry_id)

        entry = SimpleNamespace(
            entry_id="entry-1",
            data={"cloud_tid": "device-1", "cloud_control": False},
            options={},
        )
        entry.runtime_data = SimpleNamespace(
            reload_signature=settings.reload_signature(entry)
        )
        entry.options = {"cloud_control": True}
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_reload=reload_entry)
        )

        asyncio.run(init_mod.async_reload_entry(hass, entry))

        self.assertEqual(reloads, ["entry-1"])


class CoordinatorRefreshFailureTest(unittest.TestCase):
    """Coordinator should not treat an empty refresh as reachable data."""

    def test_empty_refresh_raises_update_failed(self) -> None:
        coordinator_mod = load_integration_module("coordinator")
        update_coordinator = sys.modules["homeassistant.helpers.update_coordinator"]

        class Client:
            cloud_enabled = False
            cloud_statistics_enabled = False

            async def async_request_status(self) -> None:
                pass

            def get_last_status(self) -> dict:
                return {}

        coordinator = object.__new__(coordinator_mod.TclUdpDataUpdateCoordinator)
        coordinator.config_entry = SimpleNamespace(
            runtime_data=SimpleNamespace(client=Client())
        )

        with self.assertRaises(update_coordinator.UpdateFailed):
            asyncio.run(coordinator._async_update_data())


class UdpStatusSnapshotTest(unittest.TestCase):
    """UDP callbacks should receive snapshots, not the mutable status cache."""

    def test_status_callback_receives_copy_of_last_status(self) -> None:
        udp_mod = load_integration_module("udp_client")
        received: list[dict] = []

        async def callback(status: dict) -> None:
            received.append(status)

        async def run_case() -> None:
            client = udp_mod.UdpClient("jid", "1", "account")

            async def no_request_status():
                pass

            client.async_request_status = no_request_status
            payload = (
                b'<msg cmd="status" type="notify" seq="1" tclid="AA">'
                b"<statusUpdateMsg><turnOn>1</turnOn></statusUpdateMsg></msg>"
            )
            client._status_callback = callback
            client._handle_status_update(payload, ("192.0.2.10", 10075))
            await asyncio.sleep(0)
            client._last_status["power"] = False

        asyncio.run(run_case())

        self.assertEqual(received, [{"power": True}])

    def test_status_message_lookup_does_not_use_element_truthiness(self) -> None:
        async def run_case() -> None:
            udp_mod = load_integration_module("udp_client")
            client = udp_mod.UdpClient("jid", "1", "account")

            async def no_request_status():
                pass

            client.async_request_status = no_request_status
            payload = (
                b'<msg cmd="status" type="notify" seq="1" tclid="AA">'
                b"<statusUpdateMsg><turnOn>1</turnOn></statusUpdateMsg></msg>"
            )

            with warnings.catch_warnings():
                warnings.simplefilter("error", DeprecationWarning)
                client._handle_status_update(payload, ("192.0.2.10", 10075))

        asyncio.run(run_case())

    def test_callback_contains_only_fields_from_current_udp_packet(self) -> None:
        udp_mod = load_integration_module("udp_client")
        received: list[dict] = []

        async def callback(status: dict) -> None:
            received.append(status)

        async def run_case() -> None:
            client = udp_mod.UdpClient("jid", "1", "account")

            async def no_request_status():
                pass

            client.async_request_status = no_request_status
            client._status_callback = callback
            client._handle_status_update(
                (
                    b'<msg cmd="status" type="notify" seq="1" tclid="AA">'
                    b"<statusUpdateMsg><turnOn>1</turnOn></statusUpdateMsg></msg>"
                ),
                ("192.0.2.10", 10075),
            )
            await asyncio.sleep(0)
            client._handle_status_update(
                (
                    b'<msg cmd="status" type="notify" seq="2" tclid="AA">'
                    b"<statusUpdateMsg><WindSpeed>high</WindSpeed>"
                    b"</statusUpdateMsg></msg>"
                ),
                ("192.0.2.10", 10075),
            )
            await asyncio.sleep(0)

        asyncio.run(run_case())

        self.assertEqual(received, [{"power": True}, {"fan_speed": "high"}])


class SensorUnitTest(unittest.TestCase):
    """Outdoor sensor should expose the same units the parser stores."""

    def test_outdoor_temperature_sensor_reports_celsius(self) -> None:
        sensor_mod = load_integration_module("sensor")
        const = sys.modules["homeassistant.const"]
        coordinator = SimpleNamespace(
            data={"outdoor_temp": 30.0},
            config_entry=SimpleNamespace(entry_id="entry-1", domain="tcl_udp_ac"),
        )

        entity = sensor_mod.TclUdpOutdoorTempSensor(coordinator)

        self.assertEqual(
            entity._attr_native_unit_of_measurement, const.UnitOfTemperature.CELSIUS
        )
        self.assertEqual(entity.native_value, 30.0)


if __name__ == "__main__":
    unittest.main()
