"""Configuration metadata and translation tests."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS_DIR = ROOT / "custom_components/tcl_udp_ac/translations"
PRIMARY_TRANSLATION_LANGUAGES = {
    "de",
    "es",
    "fr",
    "it",
    "ja",
    "ko",
    "pt-BR",
    "zh-Hans",
}
CONFIG_KEYS = {
    "action_jid",
    "action_source",
    "account",
    "cloud_enabled",
    "cloud_tid",
    "cloud_access_token",
    "cloud_from",
    "cloud_to",
    "cloud_base_url",
    "cloud_control",
    "cloud_user_agent",
    "cloud_platform",
    "cloud_app_package",
    "cloud_system_version",
    "cloud_brand",
    "cloud_app_version",
    "cloud_sdk_version",
    "cloud_channel",
    "cloud_app_build_version",
    "cloud_t_app_version",
    "cloud_t_platform_type",
    "cloud_t_store_uuid",
    "cloud_origin",
    "cloud_x_requested_with",
    "cloud_accept",
    "cloud_accept_encoding",
    "cloud_accept_language",
    "enable_fan_only_mode",
    "enable_auto_mode",
}


class ConfigMetadataTest(unittest.TestCase):
    """Home Assistant metadata should be explicit and setup UI should be labeled."""

    def test_manifest_declares_device_integration_type(self) -> None:
        manifest = json.loads(
            (ROOT / "custom_components/tcl_udp_ac/manifest.json").read_text()
        )

        self.assertEqual(manifest["domain"], "tcl_udp_ac")
        self.assertEqual(manifest["integration_type"], "device")
        self.assertEqual(manifest["iot_class"], "local_push")
        self.assertTrue(manifest["config_flow"])

    def test_hacs_metadata_exists(self) -> None:
        hacs = json.loads((ROOT / "hacs.json").read_text())

        self.assertEqual(hacs["name"], "TCL UDP Air Conditioner")
        self.assertIn("homeassistant", hacs)

    def test_config_fields_have_translation_labels(self) -> None:
        translations = json.loads(
            (TRANSLATIONS_DIR / "en.json").read_text()
        )
        data = translations["config"]["step"]["user"]["data"]
        options_data = translations["options"]["step"]["init"]["data"]

        self.assertEqual(CONFIG_KEYS - set(data), set())
        self.assertEqual(CONFIG_KEYS - set(options_data), set())

    def test_primary_translation_files_match_english_shape(self) -> None:
        english = json.loads((TRANSLATIONS_DIR / "en.json").read_text())
        translation_files = {
            path.stem for path in TRANSLATIONS_DIR.glob("*.json") if path.stem != "en"
        }

        self.assertEqual(translation_files, PRIMARY_TRANSLATION_LANGUAGES)

        english_keys = self._leaf_paths(english)
        for language in PRIMARY_TRANSLATION_LANGUAGES:
            with self.subTest(language=language):
                path = TRANSLATIONS_DIR / f"{language}.json"
                data = json.loads(path.read_text())
                self.assertEqual(self._leaf_paths(data), english_keys)
                self.assert_no_placeholder_syntax(data)

    def test_no_strings_json_for_custom_integration_translations(self) -> None:
        self.assertFalse((ROOT / "custom_components/tcl_udp_ac/strings.json").exists())

    @classmethod
    def _leaf_paths(cls, value: object, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
        if isinstance(value, dict):
            paths: set[tuple[str, ...]] = set()
            for key, child in value.items():
                paths |= cls._leaf_paths(child, (*prefix, key))
            return paths
        return {prefix}

    def assert_no_placeholder_syntax(self, value: object) -> None:
        if isinstance(value, dict):
            for child in value.values():
                self.assert_no_placeholder_syntax(child)
        elif isinstance(value, str):
            self.assertNotIn("[%key:", value)

    def test_backup_poll_interval_is_short_enough_for_external_state_changes(self) -> None:
        init_text = (ROOT / "custom_components/tcl_udp_ac/__init__.py").read_text()
        match = re.search(r"SCAN_INTERVAL\s*=\s*timedelta\(minutes=(\d+)\)", init_text)

        self.assertIsNotNone(match)
        self.assertLessEqual(int(match.group(1)), 1)


if __name__ == "__main__":
    unittest.main()
