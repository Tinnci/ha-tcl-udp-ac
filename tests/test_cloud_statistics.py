"""Tests for TCL+ electricity/runtime report parsing."""

from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


def _header_profile(api_mod):
    return api_mod.CloudHeaderProfile(
        platform="android",
        user_agent="ua",
        app_package="pkg",
        system_version="16",
        brand="brand",
        app_version="4.0.9",
        sdk_version="6.0.3",
        channel="xiaomi",
        app_build_version="4.0.9.0",
        t_app_version="4.0.9.0",
        t_platform_type="Android",
        t_store_uuid="TCL+",
        origin="https://h5.zx.tcljd.com",
        x_requested_with="com.tcl.tclplus",
        accept="text/plain",
        accept_encoding="gzip",
        accept_language="zh-CN",
    )


class CloudStatisticsTest(unittest.TestCase):
    """Cloud statistics should parse into HA-safe report values."""

    def setUp(self) -> None:
        self.api_mod = load_integration_module("api")
        self.sensor_mod = load_integration_module("sensor")

    def make_client(self):
        return self.api_mod.CloudClient(
            session=object(),
            enabled=True,
            tid="45816970",
            token="token",
            from_jid=None,
            to_jid=None,
            base_url="https://io.zx.tcljd.com",
            product_key="1112013595N",
            user_id="14427826",
            control_enabled=False,
            headers=_header_profile(self.api_mod),
        )

    def test_parse_current_month_electricity_summary(self) -> None:
        client = self.make_client()
        payload = {
            "data": {
                "ecoDetails": [
                    {
                        "electricity": "14",
                        "runningHours": "444",
                        "dataList": [
                            {"time": "2026-05-01"},
                            {"time": "2026-05-31"},
                        ],
                    },
                    {
                        "electricity": "3.4",
                        "electricityBill": "1.97",
                        "runningHours": "163.3",
                        "ecoHours": "0",
                        "carbonEmission": "0",
                        "dataList": [
                            {"time": "2026-06-01"},
                            {"time": "2026-06-30"},
                        ],
                    },
                ]
            }
        }

        stats = client._parse_electricity_summary(payload, today=date(2026, 6, 16))

        self.assertEqual(
            stats,
            {
                "period_start": "2026-06-01",
                "period_end": "2026-06-30",
                "energy_kwh": 3.4,
                "running_hours": 163.3,
                "eco_hours": 0.0,
                "electricity_bill": 1.97,
                "carbon_emission": 0.0,
            },
        )

    def test_statistics_headers_include_device_context(self) -> None:
        client = self.make_client()

        headers = client._build_statistics_headers()

        self.assertTrue(client.statistics_enabled)
        self.assertEqual(headers["accesstoken"], "token")
        self.assertEqual(headers["deviceid"], "45816970")
        self.assertEqual(headers["productkey"], "1112013595N")
        self.assertEqual(headers["userid"], "14427826")

    def test_statistics_requires_product_key(self) -> None:
        client = self.api_mod.CloudClient(
            session=object(),
            enabled=True,
            tid="45816970",
            token="token",
            from_jid=None,
            to_jid=None,
            base_url="https://io.zx.tcljd.com",
            control_enabled=False,
            headers=_header_profile(self.api_mod),
        )

        self.assertFalse(client.statistics_enabled)

    def test_statistics_sensors_expose_values_and_report_period(self) -> None:
        coordinator = SimpleNamespace(
            data={
                "energy_statistics": {
                    "period_start": "2026-06-01",
                    "period_end": "2026-06-30",
                    "energy_kwh": 3.4,
                    "running_hours": 163.3,
                }
            },
            config_entry=SimpleNamespace(entry_id="entry-1", domain="tcl_udp_ac"),
        )

        energy = self.sensor_mod.TclUdpCurrentMonthEnergySensor(coordinator)
        runtime = self.sensor_mod.TclUdpCurrentMonthRuntimeSensor(coordinator)

        self.assertEqual(energy.native_value, 3.4)
        self.assertEqual(energy._attr_device_class, "energy")
        self.assertEqual(energy._attr_state_class, "total")
        self.assertEqual(energy._attr_native_unit_of_measurement, "kWh")
        self.assertEqual(
            energy.extra_state_attributes,
            {"period_start": "2026-06-01", "period_end": "2026-06-30"},
        )
        self.assertEqual(energy.last_reset.isoformat(), "2026-06-01T00:00:00+00:00")
        self.assertEqual(runtime.native_value, 163.3)
        self.assertEqual(runtime._attr_device_class, "duration")
        self.assertEqual(runtime._attr_state_class, "total")
        self.assertEqual(runtime._attr_native_unit_of_measurement, "h")


if __name__ == "__main__":
    unittest.main()
