"""Tests for the standalone live-control experiment harness."""

from __future__ import annotations

import unittest

from tests.test_protocol_commands import load_integration_module

load_integration_module("const")
load_integration_module("protocol_profiles")
from tools import test_control_api

USER_DEVICES_JSONL = """
{"type":"response","url":"https://io.zx.tcljd.com/v1/tclplus/user/user_devices","body":"{\\"success\\":true,\\"data\\":[{\\"deviceId\\":\\"45816970\\",\\"protocol\\":\\"1\\",\\"identifiers\\":[{\\"identifier\\":\\"targetTemperature\\",\\"value\\":26},{\\"identifier\\":\\"workMode\\",\\"value\\":1},{\\"identifier\\":\\"powerSwitch\\",\\"value\\":0}],\\"listControl\\":[{\\"identifier\\":\\"targetTemperature\\",\\"dataType\\":{\\"type\\":\\"double\\",\\"specs\\":{\\"unit\\":\\"C\\",\\"min\\":\\"16\\",\\"max\\":\\"31\\",\\"step\\":\\"0.5\\"}}},{\\"identifier\\":\\"workMode\\",\\"dataType\\":{\\"type\\":\\"enum\\",\\"specs\\":{\\"1\\":\\"cool\\",\\"2\\":\\"dry\\",\\"3\\":\\"fan\\",\\"4\\":\\"heat\\",\\"5\\":\\"AI\\"}}}]},{\\"deviceId\\":\\"2743138\\",\\"protocol\\":\\"0\\",\\"identifiers\\":[{\\"identifier\\":\\"turnOn\\",\\"value\\":\\"0\\"},{\\"identifier\\":\\"setTemp\\",\\"value\\":\\"73\\"},{\\"identifier\\":\\"degreeH\\",\\"value\\":\\"0\\"}],\\"listControl\\":[]}]}"} 
""".strip()


class ControlToolTest(unittest.TestCase):
    """The harness should keep live experiments explicit and safe."""

    def test_extract_device_capabilities_identifies_tsl_and_legacy_devices(
        self,
    ) -> None:
        capabilities = test_control_api.extract_device_capabilities_from_capture_text(
            USER_DEVICES_JSONL
        )

        self.assertTrue(capabilities["45816970"]["has_tsl_target_temperature"])
        self.assertEqual(capabilities["45816970"]["work_mode_values"]["4"], "heat")
        self.assertFalse(capabilities["2743138"]["has_tsl_target_temperature"])
        self.assertIn("setTemp", capabilities["2743138"]["identifiers"])

    def test_temperature_experiment_plan_refuses_unknown_tsl_write_for_legacy_tid(
        self,
    ) -> None:
        capabilities = test_control_api.extract_device_capabilities_from_capture_text(
            USER_DEVICES_JSONL
        )

        plan = test_control_api.build_temperature_experiment_plan(
            "2743138", capabilities
        )

        self.assertEqual(plan["legacy_protocol"], "convertMqtt/setTemp")
        self.assertFalse(plan["current_device_has_tsl_target_temperature"])
        self.assertFalse(plan["tsl_write_safe_to_send"])
        self.assertEqual(plan["comparable_tsl_devices"], ["45816970"])

    def test_legacy_fan_profile_uses_captured_bundle(self) -> None:
        runner = test_control_api.TestRunner(
            test_control_api.HttpClient(),
            {"tid": "2743138", "status_headers": {}},
            delay=0,
            dry_run=True,
        )
        calls = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_grouped_mode("fan", label_prefix="mode")

        self.assertEqual(
            calls,
            [
                (
                    "mode-fan",
                    [
                        ("turnOn", "1"),
                        ("baseMode", "0"),
                        ("setTemp", "73"),
                        ("degreeH", "0"),
                        ("windSpd", "0"),
                        ("optSuper", "0"),
                    ],
                )
            ],
        )

    def test_mode_matrix_is_available_as_named_dispatch(self) -> None:
        self.assertEqual(
            test_control_api.TEST_DISPATCH["mode-matrix"], "test_mode_matrix"
        )

    def test_mode_matrix_uses_captured_profile_bundles(self) -> None:
        runner = test_control_api.TestRunner(
            test_control_api.HttpClient(),
            {"tid": "2743138", "status_headers": {}},
            dry_run=True,
        )
        calls = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_mode_matrix()

        self.assertIn(
            (
                "mode-matrix-dehumi",
                [
                    ("turnOn", "1"),
                    ("baseMode", "2"),
                    ("setTemp", "82"),
                    ("degreeH", "0"),
                    ("windSpd", "0"),
                    ("optSuper", "0"),
                ],
            ),
            calls,
        )
        self.assertIn(
            (
                "mode-matrix-fan",
                [
                    ("turnOn", "1"),
                    ("baseMode", "0"),
                    ("setTemp", "73"),
                    ("degreeH", "0"),
                    ("windSpd", "0"),
                    ("optSuper", "0"),
                ],
            ),
            calls,
        )
        emitted_base_modes = {
            value for _, items in calls for key, value in items if key == "baseMode"
        }
        self.assertNotIn("7", emitted_base_modes)
        self.assertNotIn("8", emitted_base_modes)

    def test_legacy_auto_profile_sends_no_command(self) -> None:
        runner = test_control_api.TestRunner(
            test_control_api.HttpClient(),
            {"tid": "2743138", "status_headers": {}},
            dry_run=True,
        )
        calls = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_grouped_mode("selffeel", label_prefix="mode")

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
