"""Device descriptor and account inventory tests."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


class DeviceDescriptorTest(unittest.TestCase):
    """The device semantic layer should keep identity and presentation precise."""

    def setUp(self) -> None:
        self.descriptors = load_integration_module("device_descriptor")
        self.inventory = load_integration_module("device_inventory")

    def descriptor(self, device_id: str, **kwargs):
        return self.descriptors.DeviceDescriptor(
            device_id=device_id, category="AC", **kwargs
        )

    def test_descriptor_generates_device_config_without_auth_data(self) -> None:
        descriptor = self.descriptor(
            "45816970",
            master_id="14427826",
            product_key="1112013595N",
            name="空调",
            room="客厅",
            mac="e0:01:c7:05:b3:ca",
            model="KFRd-35G/D-STA22Bp(B1)",
            protocol="1",
        )

        patch = descriptor.config_patch()

        self.assertEqual(descriptor.routing_identities, ("45816970", "e0:01:c7:05:b3:ca"))
        self.assertEqual(descriptor.title, "空调 - 客厅")
        self.assertEqual(patch["cloud_tid"], "45816970")
        self.assertEqual(patch["device_name"], "空调")
        self.assertEqual(patch["device_room"], "客厅")
        self.assertNotIn("cloud_access_token", patch)

    def test_inventory_excludes_only_already_configured_device_ids(self) -> None:
        first = self.descriptor("2743138")
        second = self.descriptor("45816970")
        inventory = self.inventory.AccountDeviceInventory(
            account_id="121517358",
            devices=(first, second),
            configured_device_ids=frozenset({"2743138"}),
        )

        self.assertEqual(inventory.available_devices, (second,))
        self.assertIs(inventory.find("2743138"), first)

    def test_catalog_uses_token_manager_and_rereads_rotated_token(self) -> None:
        entry = SimpleNamespace(
            data={"cloud_access_token": "old"}, options={}
        )
        calls: list[str] = []
        discovered = self.descriptor("45816970")
        account_module = load_integration_module("account_client")
        inventory_module = self.inventory

        class AccountClient:
            async def async_list_devices(self, token):
                calls.append(token)
                if token == "old":
                    raise account_module.TclAccountAuthError("expired")
                return [discovered]

        class TokenManager:
            async def async_authenticated_request(self, operation):
                try:
                    return await operation()
                except inventory_module.CloudAuthRejectedError:
                    entry.data["cloud_access_token"] = "rotated"
                    return await operation()

        catalog = self.inventory.AccountDeviceCatalog(
            AccountClient(), TokenManager(), entry
        )

        result = asyncio.run(
            catalog.async_load(
                account_id="121517358", configured_device_ids=frozenset()
            )
        )

        self.assertEqual(calls, ["old", "rotated"])
        self.assertEqual(result.available_devices[0].device_id, "45816970")


if __name__ == "__main__":
    unittest.main()
