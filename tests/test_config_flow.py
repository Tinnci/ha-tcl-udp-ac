"""Tests for the Home Assistant config flow helpers."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


class ConfigFlowTest(unittest.TestCase):
    """Config flow should use discovered TCL+ device metadata."""

    def setUp(self) -> None:
        self.account_client = load_integration_module("account_client")
        self.config_flow = load_integration_module("config_flow")

    def test_device_step_uses_discovered_device_ids_and_jids(self) -> None:
        flow = self.config_flow.TclUdpFlowHandler()
        flow._login_tokens = self.account_client.TclTokens(
            access_token="access.jwt.sig",
            refresh_token="refresh.jwt.sig",
            account_id="121517358",
        )
        flow._login_devices = [
            self.account_client.TclCloudDevice(
                device_id="45816970",
                category="AC",
                product_key="1112013595N",
                master_id="14427826",
                name="Living room AC",
                room="Living room",
                protocol="1",
                is_online=True,
                energy=True,
            )
        ]

        form = asyncio.run(flow.async_step_device())

        self.assertEqual(form["type"], "form")
        self.assertEqual(form["step_id"], "device")
        validated = form["data_schema"]({})
        self.assertEqual(validated[self.config_flow.CONF_CLOUD_TID], "45816970")
        # Protocol 1 devices now have a mapped TSL property-control path.
        self.assertTrue(validated[self.config_flow.CONF_CLOUD_CONTROL])

        entry = asyncio.run(flow.async_step_device(validated))

        self.assertEqual(entry["type"], "create_entry")
        self.assertEqual(entry["title"], "Living room AC - Living room")
        data = entry["data"]
        self.assertEqual(data[self.config_flow.CONF_CLOUD_TID], "45816970")
        self.assertEqual(
            data[self.config_flow.CONF_CLOUD_FROM],
            "14427826@tcl.com/PH-android-zx01-2",
        )
        self.assertEqual(
            data[self.config_flow.CONF_CLOUD_TO],
            "45816970@tcl.com/AC-linux-zx01-1",
        )
        self.assertEqual(data[self.config_flow.CONF_ACCOUNT], "14427826")
        self.assertEqual(data[self.config_flow.CONF_CLOUD_PRODUCT_KEY], "1112013595N")
        self.assertEqual(data[self.config_flow.CONF_DEVICE_NAME], "Living room AC")
        self.assertEqual(data[self.config_flow.CONF_DEVICE_ROOM], "Living room")
        self.assertEqual(data[self.config_flow.CONF_DEVICE_PROTOCOL], "1")
        self.assertEqual(data[self.config_flow.CONF_CLOUD_TOKEN], "access.jwt.sig")
        self.assertEqual(
            data[self.config_flow.CONF_CLOUD_REFRESH_TOKEN], "refresh.jwt.sig"
        )
        self.assertEqual(data[self.config_flow.CONF_CLOUD_ACCOUNT_ID], "121517358")
        self.assertNotIn("username", data)
        self.assertNotIn("password", data)

    def test_unknown_protocol_one_product_does_not_default_cloud_control(
        self,
    ) -> None:
        devices = [
            self.account_client.TclCloudDevice(
                device_id="99999999",
                category="AC",
                product_key="unknown",
                protocol="1",
            )
        ]

        self.assertFalse(self.config_flow._default_device_cloud_control(devices))

    def test_discovered_device_mac_is_persisted_for_udp_routing(self) -> None:
        device = self.account_client.TclCloudDevice(
            device_id="device-1",
            category="AC",
            product_key="product-1",
            master_id="account-1",
            mac="AA:BB:CC:DD:EE:FF",
        )

        data = self.config_flow._data_with_device({}, device, {})

        self.assertEqual(data["device_mac"], "AA:BB:CC:DD:EE:FF")

    def test_existing_account_data_replaces_old_device_identity_only(self) -> None:
        source = type(
            "Entry",
            (),
            {
                "data": {
                    "cloud_access_token": "access",
                    "cloud_refresh_token": "refresh",
                    "cloud_account_id": "account-id",
                    "cloud_tid": "old-device",
                    "device_mac": "old-mac",
                    "cloud_product_key": "old-product",
                },
                "options": {"cloud_accept_language": "zh-CN"},
            },
        )()
        device = self.account_client.TclCloudDevice(
            device_id="new-device",
            category="AC",
            mac="new-mac",
            product_key="new-product",
            name="New AC",
        )

        data = self.config_flow._data_from_existing_account(
            source, device, {"cloud_control": False}
        )

        self.assertEqual(data["cloud_tid"], "new-device")
        self.assertEqual(data["device_mac"], "new-mac")
        self.assertEqual(data["cloud_product_key"], "new-product")
        self.assertEqual(data["cloud_access_token"], "access")
        self.assertEqual(data["cloud_refresh_token"], "refresh")
        self.assertEqual(data["cloud_accept_language"], "zh-CN")
        self.assertFalse(data["cloud_control"])

    def test_existing_account_flow_reconciles_and_adds_available_device(self) -> None:
        first = SimpleNamespace(
            entry_id="entry-1",
            title="Bedroom AC",
            domain="tcl_udp_ac",
            data={
                "cloud_account_id": "account-id",
                "cloud_refresh_token": "refresh",
                "cloud_access_token": "access",
                "cloud_tid": "2743138",
            },
            options={},
        )

        class TokenManager:
            async def async_authenticated_request(self, operation):
                return await operation()

        first.runtime_data = SimpleNamespace(token_manager=TokenManager())

        class ConfigEntries:
            def __init__(self):
                self.updates = []

            def async_entries(self, domain):
                return [first] if domain == "tcl_udp_ac" else []

            def async_update_entry(self, entry, *, data):
                entry.data = data
                self.updates.append(entry.entry_id)

        config_entries = ConfigEntries()
        flow = self.config_flow.TclUdpFlowHandler()
        flow.hass = SimpleNamespace(config_entries=config_entries)
        devices = [
            self.account_client.TclCloudDevice(
                device_id="2743138",
                category="AC",
                mac="38:76:CA:43:69:B9",
                name="Bedroom AC",
            ),
            self.account_client.TclCloudDevice(
                device_id="45816970",
                category="AC",
                mac="e0:01:c7:05:b3:ca",
                name="Living room AC",
                room="Living room",
                protocol="1",
            ),
        ]

        class AccountClient:
            async def async_list_devices(self, token):
                self.assert_token = token
                return devices

        original_factory = self.config_flow._account_client
        self.config_flow._account_client = lambda _hass, _source: AccountClient()
        try:
            form = asyncio.run(
                flow.async_step_existing_account(
                    {self.config_flow.ACCOUNT_ENTRY_ID: "entry-1"}
                )
            )
            validated = form["data_schema"]({})
            entry = asyncio.run(flow.async_step_existing_device(validated))
        finally:
            self.config_flow._account_client = original_factory

        self.assertEqual(form["step_id"], "existing_device")
        self.assertEqual(validated["cloud_tid"], "45816970")
        self.assertEqual(entry["type"], "create_entry")
        self.assertEqual(entry["title"], "Living room AC - Living room")
        self.assertEqual(entry["data"]["cloud_account_id"], "account-id")
        self.assertEqual(entry["data"]["device_mac"], "e0:01:c7:05:b3:ca")
        self.assertEqual(first.data["device_mac"], "38:76:CA:43:69:B9")
        self.assertEqual(config_entries.updates, ["entry-1"])


if __name__ == "__main__":
    unittest.main()
