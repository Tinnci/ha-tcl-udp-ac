"""Tests for config entry settings resolution."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from tests.test_protocol_commands import load_integration_module


class ConfigSettingsTest(unittest.TestCase):
    """Config entry settings should centralize data/options precedence."""

    def setUp(self) -> None:
        self.settings_mod = load_integration_module("config_settings")

    def test_token_values_prefer_data_over_stale_options(self) -> None:
        entry = SimpleNamespace(
            data={"cloud_access_token": "fresh"},
            options={"cloud_access_token": "stale"},
        )

        self.assertEqual(
            self.settings_mod.entry_value(entry, "cloud_access_token", ""),
            "fresh",
        )

    def test_non_token_values_prefer_options_over_data(self) -> None:
        entry = SimpleNamespace(
            data={"cloud_tid": "data-device"},
            options={"cloud_tid": "option-device"},
        )

        self.assertEqual(
            self.settings_mod.entry_value(entry, "cloud_tid", ""),
            "option-device",
        )

    def test_auth_settings_use_effective_options_during_reauth(self) -> None:
        entry = SimpleNamespace(
            data={"account_base_url": "https://old.example"},
            options={
                "account_base_url": "https://new.example",
                "account_app_id": "option-app",
            },
        )

        settings = self.settings_mod.AuthSettings.from_entry(entry)

        self.assertEqual(settings.base_url, "https://new.example")
        self.assertEqual(settings.app_id, "option-app")

    def test_product_key_resolves_tsl_profile_without_known_device_id(self) -> None:
        entry = SimpleNamespace(
            data={
                "cloud_tid": "other-device",
                "cloud_product_key": "1112013595N",
            },
            options={},
        )

        profile = self.settings_mod.profile_for_entry(entry)

        self.assertEqual(profile.name, "tsl_1112013595N")
        self.assertFalse(profile.legacy_transport_enabled)

    def test_api_client_kwargs_keep_account_as_cloud_user_id(self) -> None:
        entry = SimpleNamespace(
            data={
                "account": "account-id",
                "cloud_tid": "45816970",
                "device_mac": "AA:BB:CC:DD:EE:FF",
            },
            options={"cloud_access_token": "stale-token"},
        )

        settings = self.settings_mod.ConfigEntrySettings.from_entry(entry)
        kwargs = settings.api_client_kwargs()

        self.assertEqual(kwargs["account"], "account-id")
        self.assertEqual(kwargs["cloud_user_id"], "account-id")
        self.assertEqual(kwargs["cloud_token"], "stale-token")
        self.assertEqual(kwargs["device_mac"], "AA:BB:CC:DD:EE:FF")


if __name__ == "__main__":
    unittest.main()
