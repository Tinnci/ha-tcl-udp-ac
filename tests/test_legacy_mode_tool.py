"""Legacy mode dry-run tool tests."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from tests.test_protocol_commands import load_integration_module

load_integration_module("const")
load_integration_module("protocol_profiles")
from tools import test_control_api


class LegacyModeToolTest(unittest.TestCase):
    """The operator tool should expose capture-derived legacy profiles."""

    def _runner(self) -> test_control_api.TestRunner:
        return test_control_api.TestRunner(
            test_control_api.HttpClient(),
            {
                "tid": "2743138",
                "from": "user@tcl.com/PH-android-zx01-2",
                "to": "2743138@tcl.com",
                "status_headers": {},
            },
            dry_run=True,
        )

    def test_dry_run_matrix_emits_captured_profiles(self) -> None:
        runner = self._runner()
        calls: list[tuple[str, list[tuple[str, str]]]] = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_mode_matrix()

        payloads = {label: dict(items) for label, items in calls}
        self.assertEqual(payloads["mode-matrix-fan"]["baseMode"], "0")
        self.assertEqual(payloads["mode-matrix-fan"]["setTemp"], "73")
        self.assertEqual(payloads["mode-matrix-fan"]["optSuper"], "0")
        self.assertEqual(payloads["mode-matrix-dehumi"]["baseMode"], "2")
        self.assertEqual(payloads["mode-matrix-dehumi"]["setTemp"], "82")
        supported_base_modes = {
            payload["baseMode"]
            for payload in payloads.values()
            if "baseMode" in payload
        }
        self.assertNotIn("7", supported_base_modes)
        self.assertNotIn("8", supported_base_modes)

    def test_auto_is_reported_unsupported_without_payload(self) -> None:
        runner = self._runner()
        calls: list[tuple[str, list[tuple[str, str]]]] = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_grouped_mode("auto", label_prefix="mode")

        self.assertEqual(calls, [])

    def test_dry_run_output_names_capture_profiles_and_temperature_experiment(
        self,
    ) -> None:
        runner = self._runner()
        stream = io.StringIO()
        with redirect_stdout(stream):
            runner.test_mode_matrix()

        output = stream.getvalue()
        self.assertIn("capture-derived protocol profiles", output)
        self.assertIn("Temperature-only experiments remain separate", output)
        self.assertIn("capture-derived bundle", output)

    def test_temperature_matrix_dry_run_prints_contextual_candidates(self) -> None:
        runner = self._runner()
        calls: list[tuple[str, list[tuple[str, str]]]] = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_temperature_matrix(temp_f=75, degree_h="0")

        labels = [label for label, _ in calls]
        self.assertEqual(
            labels,
            [
                "temp-matrix-A-field-only",
                "temp-matrix-B-power-temp",
                "temp-matrix-C-mode-temp",
                "temp-matrix-D-mode-temp-auto-fan",
                "temp-matrix-E-mode-temp-current-fan",
                "temp-matrix-F-mode-temp-super-clear",
            ],
        )
        payloads = {label: dict(items) for label, items in calls}
        self.assertEqual(
            payloads["temp-matrix-A-field-only"], {"setTemp": "75", "degreeH": "0"}
        )
        self.assertEqual(payloads["temp-matrix-C-mode-temp"]["baseMode"], "1")
        self.assertEqual(
            payloads["temp-matrix-F-mode-temp-super-clear"]["optSuper"], "0"
        )

    def test_temperature_matrix_accepts_forced_mode_context(self) -> None:
        runner = self._runner()
        calls: list[tuple[str, list[tuple[str, str]]]] = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_temperature_matrix(temp_f=75, degree_h="0", mode="heat")

        payloads = {label: dict(items) for label, items in calls}
        self.assertEqual(payloads["temp-matrix-C-mode-temp"]["baseMode"], "4")

    def test_temperature_matrix_can_run_single_candidate(self) -> None:
        runner = self._runner()
        calls: list[tuple[str, list[tuple[str, str]]]] = []
        runner.cloud_control = lambda items, label="control": (
            calls.append((label, items)) or True
        )

        runner.test_temperature_matrix(
            temp_f=77,
            degree_h="0",
            mode="cool",
            candidate="C",
        )

        self.assertEqual([label for label, _ in calls], ["temp-matrix-C-mode-temp"])
        self.assertEqual(
            dict(calls[0][1]),
            {"turnOn": "1", "baseMode": "1", "setTemp": "77", "degreeH": "0"},
        )

    def test_target_celsius_encoding_for_cli_matrix(self) -> None:
        encoded_temp, encoded_degree_h = test_control_api.LegacyTemperatureCodec.encode(
            24.0,
            fallback_celsius=24.0,
        )

        self.assertEqual((encoded_temp, encoded_degree_h), ("75", "0"))


if __name__ == "__main__":
    unittest.main()
