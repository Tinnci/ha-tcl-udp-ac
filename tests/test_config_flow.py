"""Tests for the Home Assistant config flow helpers."""

from __future__ import annotations

import asyncio
import unittest

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
        self.assertEqual(data[self.config_flow.CONF_CLOUD_TOKEN], "access.jwt.sig")
        self.assertEqual(
            data[self.config_flow.CONF_CLOUD_REFRESH_TOKEN], "refresh.jwt.sig"
        )
        self.assertEqual(data[self.config_flow.CONF_CLOUD_ACCOUNT_ID], "121517358")

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


if __name__ == "__main__":
    unittest.main()
