"""Privacy and content tests for Home Assistant diagnostics."""

from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


class DiagnosticsTest(unittest.TestCase):
    """Diagnostics should explain behavior without disclosing identity."""

    def test_config_entry_diagnostics_are_useful_and_redacted(self) -> None:
        diagnostics = load_integration_module("diagnostics")

        class FakeSession:
            def get_last_status(self):
                return {
                    "power": True,
                    "target_temp": 24.0,
                    "device_name": "secret-bedroom-name",
                }

            def pending_command_confirmation(self):
                return None

            def last_command_attempt(self):
                return {
                    "intent": "temperature:24",
                    "expected_status": {"target_temp": 24.0},
                    "transport_outcome": "accepted_by_cloud",
                    "transport_attempts": {
                        "cloud": "accepted",
                        "udp": "skipped",
                    },
                }

        coordinator = SimpleNamespace(
            last_update_success=True,
            last_exception=None,
            last_command_result={
                "entry_id": "secret-entry-id",
                "entity_id": "climate.secret-bedroom",
                "context_id": "secret-context-id",
                "outcome": "applied",
            },
        )
        entry = SimpleNamespace(
            data={
                "cloud_tid": "secret-device-tid",
                "cloud_access_token": "secret-access-token",
                "cloud_refresh_token": "secret-refresh-token",
                "cloud_account_id": "secret-account-id",
                "cloud_product_key": "1112013595N",
                "device_protocol": "1",
                "device_mac": "secret-device-mac",
                "device_name": "secret-device-name",
                "device_room": "secret-room",
                "cloud_enabled": True,
                "cloud_control": True,
            },
            options={},
            runtime_data=SimpleNamespace(
                integration=SimpleNamespace(version="0.10.0"),
                coordinator=coordinator,
                session=FakeSession(),
            ),
        )

        report = asyncio.run(
            diagnostics.async_get_config_entry_diagnostics(None, entry)
        )
        serialized = json.dumps(report)

        for secret in (
            "secret-device-tid",
            "secret-access-token",
            "secret-refresh-token",
            "secret-account-id",
            "secret-device-mac",
            "secret-device-name",
            "secret-bedroom-name",
            "secret-room",
            "secret-entry-id",
            "climate.secret-bedroom",
            "secret-context-id",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(report["integration"]["version"], "0.10.0")
        self.assertTrue(report["configuration"]["access_token_configured"])
        self.assertTrue(report["configuration"]["refresh_token_configured"])
        self.assertFalse(report["configuration"]["manual_token_mode"])
        self.assertEqual(report["protocol_profile"]["profile"], "tsl_1112013595N")
        self.assertFalse(report["protocol_profile"]["local_transport_enabled"])
        self.assertEqual(report["state"]["power"], True)
        self.assertEqual(
            report["commands"]["last_attempt"]["transport_outcome"],
            "accepted_by_cloud",
        )


if __name__ == "__main__":
    unittest.main()
