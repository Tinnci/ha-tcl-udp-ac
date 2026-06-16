"""Capture analysis tests for legacy TCL mode evidence."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.analyze_legacy_mode_capture import (
    assert_legacy_mode_facts,
    build_summary,
)

CAPTURES = [
    Path("newly_captured/tcl_1778556941.jsonl"),
    Path("newly_captured/tcl_1778557400.jsonl"),
    Path("newly_captured/tcl_1778569147.jsonl"),
]


class LegacyModeCaptureAnalysisTest(unittest.TestCase):
    """Analyzer should turn new captures into explicit evidence."""

    @classmethod
    def setUpClass(cls) -> None:
        if not all(path.exists() for path in CAPTURES):
            raise unittest.SkipTest(
                "local capture fixtures (newly_captured/*.jsonl) are gitignored; "
                "run locally with captures present"
            )
        cls.summary = build_summary(CAPTURES, "2743138")

    def test_parser_loads_both_capture_files(self) -> None:
        self.assertEqual(
            self.summary["captureFiles"],
            [str(path) for path in CAPTURES],
        )
        self.assertGreater(len(self.summary["observedCommands"]), 10)

    def test_fan_candidate_uses_base_mode_zero(self) -> None:
        profiles = {
            profile["mode"]: profile for profile in self.summary["inferredProfiles"]
        }

        self.assertEqual(profiles["fan_only"]["payload"]["baseMode"], "0")
        self.assertTrue(profiles["fan_only"]["source_lines"])

    def test_no_supported_profile_uses_old_fan_or_auto_modes(self) -> None:
        supported_modes = set(self.summary["supportedBaseModes"])

        self.assertNotIn("7", supported_modes)
        self.assertNotIn("8", supported_modes)

    def test_dry_candidate_uses_base_mode_two(self) -> None:
        profiles = {
            profile["mode"]: profile for profile in self.summary["inferredProfiles"]
        }

        self.assertEqual(profiles["dry"]["payload"]["baseMode"], "2")
        self.assertIn("setTemp", profiles["dry"]["payload"])

    def test_cool_and_heat_candidates_use_current_mode_numbers(self) -> None:
        profiles = {
            profile["mode"]: profile for profile in self.summary["inferredProfiles"]
        }

        self.assertEqual(profiles["cool"]["payload"]["baseMode"], "1")
        self.assertEqual(profiles["heat"]["payload"]["baseMode"], "4")

    def test_evidence_levels_separate_observed_from_inferred(self) -> None:
        self.assertTrue(
            all(
                command["evidence_level"] == "observed"
                for command in self.summary["observedCommands"]
            )
        )
        self.assertTrue(
            all(
                profile["evidence_level"] == "capture-supported"
                for profile in self.summary["inferredProfiles"]
            )
        )
        self.assertTrue(self.summary["unsupportedCandidates"])

    def test_assert_legacy_mode_facts_passes(self) -> None:
        assert_legacy_mode_facts(self.summary)


if __name__ == "__main__":
    unittest.main()
