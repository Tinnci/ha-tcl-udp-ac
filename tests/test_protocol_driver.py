"""Protocol driver contract and registry tests."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module


class ProtocolDriverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.drivers = load_integration_module("protocol_driver")

    def test_registry_returns_runtime_checkable_driver(self) -> None:
        driver = self.drivers.resolve_protocol_driver("2743138")

        self.assertIsInstance(driver, self.drivers.ProtocolDriver)
        self.assertEqual(driver.name, "legacy_2743138")
        self.assertEqual(driver.cloud_status_family, "legacy")

    def test_product_key_selects_tsl_driver(self) -> None:
        driver = self.drivers.resolve_protocol_driver(
            "unknown", product_key="1112013595N"
        )

        self.assertEqual(driver.name, "tsl_1112013595N")
        self.assertEqual(driver.cloud_status_family, "tsl")
        self.assertFalse(driver.legacy_transport_enabled)

    def test_unknown_device_uses_compatibility_driver(self) -> None:
        driver = self.drivers.resolve_protocol_driver("unknown")

        self.assertEqual(driver.name, "default")
        self.assertEqual(driver.cloud_status_family, "hybrid")


if __name__ == "__main__":
    unittest.main()
