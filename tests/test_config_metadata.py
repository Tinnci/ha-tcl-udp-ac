"""Configuration metadata and translation tests."""

from __future__ import annotations

import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "custom_components/tcl_udp_ac/manifest.json"
HACS_PATH = ROOT / "hacs.json"
README_PATH = ROOT / "README.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
TRANSLATIONS_DIR = ROOT / "custom_components/tcl_udp_ac/translations"
STRINGS_PATH = ROOT / "custom_components/tcl_udp_ac/strings.json"
BRAND_DIR = ROOT / "custom_components/tcl_udp_ac/brand"
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
BASIC_CONFIG_KEYS = {
    "cloud_enabled",
    "cloud_tid",
    "cloud_access_token",
    "cloud_control",
    "enable_fan_only_mode",
    "enable_auto_mode",
}


class ConfigMetadataTest(unittest.TestCase):
    """Home Assistant metadata should be explicit and setup UI should be labeled."""

    def test_manifest_declares_device_integration_type(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())

        self.assertEqual(manifest["domain"], "tcl_udp_ac")
        self.assertEqual(manifest["integration_type"], "device")
        self.assertEqual(manifest["iot_class"], "local_push")
        self.assertTrue(manifest["config_flow"])
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")

    def test_hacs_metadata_exists(self) -> None:
        hacs = json.loads(HACS_PATH.read_text())

        self.assertEqual(hacs["name"], "TCL UDP Air Conditioner")
        self.assertFalse(hacs["content_in_root"])
        self.assertIn("hacs", hacs)
        self.assertIn("homeassistant", hacs)

    def test_local_brand_images_follow_home_assistant_dimensions(self) -> None:
        icon = self._png_dimensions(BRAND_DIR / "icon.png")
        icon_2x = self._png_dimensions(BRAND_DIR / "icon@2x.png")
        logo = self._png_dimensions(BRAND_DIR / "logo.png")
        logo_2x = self._png_dimensions(BRAND_DIR / "logo@2x.png")

        self.assertEqual(icon, (256, 256))
        self.assertEqual(icon_2x, (512, 512))
        self.assertGreater(logo[0], logo[1])
        self.assertGreater(logo_2x[0], logo_2x[1])
        self.assertLessEqual(128, min(logo))
        self.assertLessEqual(min(logo), 256)
        self.assertLessEqual(256, min(logo_2x))
        self.assertLessEqual(min(logo_2x), 512)
        self.assertLessEqual(abs(logo_2x[0] - 2 * logo[0]), 1)
        self.assertLessEqual(abs(logo_2x[1] - 2 * logo[1]), 1)

        self.assertFalse((ROOT / "custom_components/tcl_udp_ac/icon.png").exists())
        self.assertIn(
            "custom_components/tcl_udp_ac/brand/logo.png", README_PATH.read_text()
        )

    def test_release_version_is_consistent_across_user_facing_metadata(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        version = manifest["version"]
        readme = README_PATH.read_text()
        changelog = CHANGELOG_PATH.read_text()

        self.assertIn(f"version-{version}-blue", readme)
        self.assertIn(f"## {version}", changelog)

    def test_config_fields_have_translation_labels(self) -> None:
        translations = json.loads((TRANSLATIONS_DIR / "en.json").read_text())
        data = translations["config"]["step"]["manual"]["data"]
        advanced_data = translations["config"]["step"]["advanced"]["data"]
        options_data = translations["options"]["step"]["init"]["data"]

        self.assertEqual(BASIC_CONFIG_KEYS - set(data), set())
        self.assertEqual(CONFIG_KEYS - set(data) - set(advanced_data), set())
        self.assertEqual(CONFIG_KEYS - set(options_data), set())

    def test_config_flow_splits_basic_setup_from_advanced_options(self) -> None:
        config_flow = (ROOT / "custom_components/tcl_udp_ac/config_flow.py").read_text()

        self.assertIn("BASIC_CONFIG_KEYS", config_flow)
        self.assertIn("ADVANCED_CONFIG_KEYS", config_flow)
        self.assertIn("OPTIONS_CONFIG_KEYS", config_flow)
        self.assertIn("async_step_advanced", config_flow)
        self.assertIn("key != CONF_CLOUD_TOKEN", config_flow)
        self.assertNotIn(
            "vol.Optional(CONF_CLOUD_USER_AGENT",
            config_flow.split("async_step_manual", 1)[1].split(
                "async_step_advanced", 1
            )[0],
        )

    def test_login_and_reauth_steps_exist(self) -> None:
        config_flow = (ROOT / "custom_components/tcl_udp_ac/config_flow.py").read_text()

        for step in (
            "async_step_login_password",
            "async_step_login_sms",
            "async_step_sms_code",
            "async_step_reauth",
            "async_step_reauth_confirm",
            "async_step_reauth_sms",
            "async_step_reauth_sms_code",
        ):
            self.assertIn(step, config_flow)

    def test_basic_and_advanced_translation_labels_are_complete(self) -> None:
        translations = json.loads((TRANSLATIONS_DIR / "en.json").read_text())

        user_data = translations["config"]["step"]["manual"]["data"]
        advanced_data = translations["config"]["step"]["advanced"]["data"]
        options_data = translations["options"]["step"]["init"]["data"]

        self.assertEqual(BASIC_CONFIG_KEYS - set(user_data), set())
        self.assertEqual(CONFIG_KEYS - BASIC_CONFIG_KEYS - set(advanced_data), set())
        self.assertEqual(CONFIG_KEYS - set(options_data), set())

    def test_entity_translation_labels_exist(self) -> None:
        translations = json.loads((TRANSLATIONS_DIR / "en.json").read_text())
        entities = translations["entity"]

        self.assertIn("outdoor_temperature", entities["sensor"])
        self.assertIn("current_month_energy", entities["sensor"])
        self.assertIn("current_month_runtime", entities["sensor"])
        for key in (
            "eco_mode",
            "display",
            "health_mode",
            "sleep_mode",
            "turbo_mode",
            "aux_heat",
            "beep",
        ):
            self.assertIn(key, entities["switch"])

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

    def test_strings_json_is_the_canonical_english_translation_source(self) -> None:
        strings = json.loads(STRINGS_PATH.read_text())
        english = json.loads((TRANSLATIONS_DIR / "en.json").read_text())

        self.assertEqual(strings, english)

    @classmethod
    def _leaf_paths(
        cls, value: object, prefix: tuple[str, ...] = ()
    ) -> set[tuple[str, ...]]:
        if isinstance(value, dict):
            paths: set[tuple[str, ...]] = set()
            for key, child in value.items():
                paths |= cls._leaf_paths(child, (*prefix, key))
            return paths
        return {prefix}

    @staticmethod
    def _png_dimensions(path: Path) -> tuple[int, int]:
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise AssertionError(f"{path} is not a PNG image")
        width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
        if bit_depth != 8 or color_type not in {4, 6}:
            raise AssertionError(f"{path} must be an 8-bit PNG with transparency")
        return width, height

    def assert_no_placeholder_syntax(self, value: object) -> None:
        if isinstance(value, dict):
            for child in value.values():
                self.assert_no_placeholder_syntax(child)
        elif isinstance(value, str):
            self.assertNotIn("[%key:", value)

    def test_backup_poll_interval_is_short_enough_for_external_state_changes(
        self,
    ) -> None:
        init_text = (ROOT / "custom_components/tcl_udp_ac/__init__.py").read_text()
        match = re.search(r"SCAN_INTERVAL\s*=\s*timedelta\(minutes=(\d+)\)", init_text)

        self.assertIsNotNone(match)
        self.assertLessEqual(int(match.group(1)), 1)


if __name__ == "__main__":
    unittest.main()
