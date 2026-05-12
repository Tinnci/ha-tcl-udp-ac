#!/usr/bin/env python3
"""Analyze TCL+ legacy AC mode commands from mitmproxy JSONL captures."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


MODE_RELEVANT_FIELDS = {
    "turnOn",
    "baseMode",
    "setTemp",
    "degreeH",
    "windSpd",
    "optSuper",
    "optECO",
    "optHealthy",
    "directH",
    "directV",
    "optSolidWd",
}


@dataclass(frozen=True)
class ObservedCommand:
    """One observed convertMqtt command packet."""

    capture_file: str
    line: int
    timestamp_ms: int | None
    timestamp_local: str | None
    device_id: str
    command: str
    message_type: str
    seq: str | None
    payload: dict[str, str]
    evidence_level: str = "observed"


@dataclass(frozen=True)
class InferredModeProfile:
    """A capture-supported but not live-verified mode profile inference."""

    mode: str
    payload: dict[str, str]
    source_lines: list[str]
    evidence_level: str
    rationale: str


def _timestamp_local(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")[
        :-3
    ]


def _extract_payload(params_xml: str) -> tuple[str, str, str | None, dict[str, str]]:
    root = ET.fromstring(params_xml)
    msg = root.find(".//msg")
    if msg is None:
        return "", "", None, {}
    payload: dict[str, str] = {}
    for child in list(msg):
        value = child.get("value")
        if value is None:
            value = (child.text or "").strip()
        payload[child.tag] = value
    return (
        msg.get("cmd") or "",
        msg.get("type") or "",
        msg.get("seq"),
        payload,
    )


def parse_capture(path: Path, device_id: str) -> list[ObservedCommand]:
    """Parse one capture file into observed convertMqtt commands."""
    commands: list[ObservedCommand] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        url = record.get("url", "")
        if record.get("type") != "request":
            continue
        if f"/v1/control/convertMqtt/{device_id}" not in url:
            continue

        try:
            body = json.loads(record.get("body") or "{}")
            params = body.get("params", "")
            command, message_type, seq, payload = _extract_payload(params)
        except (json.JSONDecodeError, ET.ParseError, TypeError):
            continue

        commands.append(
            ObservedCommand(
                capture_file=path.name,
                line=line_no,
                timestamp_ms=record.get("ts"),
                timestamp_local=_timestamp_local(record.get("ts")),
                device_id=device_id,
                command=command,
                message_type=message_type,
                seq=seq,
                payload=payload,
            )
        )
    return commands


def _line_ref(command: ObservedCommand) -> str:
    return f"{command.capture_file}:{command.line}"


def infer_profiles(commands: list[ObservedCommand]) -> list[InferredModeProfile]:
    """Infer mode profiles from observed command shapes."""
    profiles: list[InferredModeProfile] = []

    fan_candidates = [
        cmd
        for cmd in commands
        if cmd.payload.get("baseMode") == "0"
        and {"setTemp", "degreeH", "windSpd"}.issubset(cmd.payload)
    ]
    if fan_candidates:
        preferred = [cmd for cmd in fan_candidates if cmd.payload.get("optSuper") == "0"]
        chosen = preferred[-1] if preferred else fan_candidates[-1]
        profiles.append(
            InferredModeProfile(
                mode="fan_only",
                payload={
                    key: chosen.payload[key]
                    for key in ("turnOn", "baseMode", "setTemp", "degreeH", "windSpd", "optSuper")
                    if key in chosen.payload
                },
                source_lines=[_line_ref(cmd) for cmd in fan_candidates],
                evidence_level="capture-supported",
                rationale=(
                    "User-reported Fan action aligns with observed baseMode=0 "
                    "bundle; no supported baseMode=7 Fan command was observed."
                ),
            )
        )

    dry_candidates = [
        cmd
        for cmd in commands
        if cmd.payload.get("baseMode") == "2"
        and {"setTemp", "windSpd", "optSuper"}.issubset(cmd.payload)
    ]
    if dry_candidates:
        chosen = dry_candidates[-1]
        profiles.append(
            InferredModeProfile(
                mode="dry",
                payload={
                    key: chosen.payload[key]
                    for key in ("turnOn", "baseMode", "setTemp", "degreeH", "windSpd", "optSuper")
                    if key in chosen.payload
                },
                source_lines=[_line_ref(cmd) for cmd in dry_candidates],
                evidence_level="capture-supported",
                rationale="Observed app-style dry bundle uses baseMode=2 with temp/fan/super fields.",
            )
        )

    cool_candidates = [
        cmd for cmd in commands if cmd.payload.get("baseMode") == "3" and "turnOn" in cmd.payload
    ]
    if cool_candidates:
        chosen = cool_candidates[-1]
        profiles.append(
            InferredModeProfile(
                mode="cool",
                payload={
                    key: chosen.payload[key]
                    for key in ("turnOn", "baseMode", "setTemp", "degreeH", "windSpd", "optSuper")
                    if key in chosen.payload
                },
                source_lines=[_line_ref(cmd) for cmd in cool_candidates],
                evidence_level="capture-supported",
                rationale="Observed app startup/cool bundle uses grouped power/mode/temp/fan fields.",
            )
        )

    return profiles


def build_summary(paths: list[Path], device_id: str) -> dict[str, Any]:
    """Build the machine-readable analysis summary."""
    commands: list[ObservedCommand] = []
    for path in paths:
        commands.extend(parse_capture(path, device_id))

    set_commands = [
        command
        for command in commands
        if command.command == "set" and command.message_type == "control"
    ]
    profiles = infer_profiles(set_commands)
    supported_base_modes = {
        profile.payload.get("baseMode")
        for profile in profiles
        if profile.evidence_level == "capture-supported"
    }
    observed_base_modes = sorted(
        {
            command.payload["baseMode"]
            for command in set_commands
            if "baseMode" in command.payload
        },
        key=lambda value: int(value) if value.isdigit() else value,
    )
    field_evidence = {
        field: [
            _line_ref(command)
            for command in set_commands
            if field in command.payload
        ]
        for field in sorted(MODE_RELEVANT_FIELDS)
    }

    return {
        "deviceId": device_id,
        "captureFiles": [str(path) for path in paths],
        "observedCommands": [asdict(command) for command in commands],
        "inferredProfiles": [asdict(profile) for profile in profiles],
        "unsupportedCandidates": [
            {
                "mode": "fan_only_old_assumption",
                "baseMode": "7",
                "evidence_level": "unsupported",
                "reason": "No capture-supported Fan profile uses baseMode=7.",
            },
            {
                "mode": "auto_ai_old_assumption",
                "baseMode": "8",
                "evidence_level": "unsupported",
                "reason": "No capture-supported Auto/AI profile uses baseMode=8.",
            },
        ],
        "fieldEvidence": field_evidence,
        "evidenceLevels": {
            "observed": "Direct packet payload from capture.",
            "inferred": "Timeline/user-action interpretation, not a packet fact.",
            "capture-supported": "Implemented candidate backed by observed packet shape.",
            "unsupported": "Old assumption not supported by these captures.",
            "experimental": "Needs live verification before being called verified.",
        },
        "observedBaseModes": observed_base_modes,
        "supportedBaseModes": sorted(mode for mode in supported_base_modes if mode is not None),
    }


def assert_legacy_mode_facts(summary: dict[str, Any]) -> None:
    """Assert the key capture-derived legacy mode facts."""
    profiles = {profile["mode"]: profile for profile in summary["inferredProfiles"]}
    fan = profiles.get("fan_only")
    dry = profiles.get("dry")

    errors: list[str] = []
    if not fan or fan["payload"].get("baseMode") != "0":
        errors.append("Fan candidate must contain baseMode=0.")
    if not dry or dry["payload"].get("baseMode") != "2":
        errors.append("Dry candidate must contain baseMode=2.")

    supported_base_modes = set(summary["supportedBaseModes"])
    if "7" in supported_base_modes:
        errors.append("No supported legacy Fan profile may use baseMode=7.")
    if "8" in supported_base_modes:
        errors.append("No supported legacy Auto/AI profile may use baseMode=8.")

    if not any(
        {"setTemp", "windSpd", "optSuper"}.issubset(command["payload"])
        for command in summary["observedCommands"]
        if command["command"] == "set"
    ):
        errors.append("Expected app-style bundles with setTemp + windSpd + optSuper.")

    if any(profile["evidence_level"] == "verified" for profile in summary["inferredProfiles"]):
        errors.append("Capture analysis must not label inferred profiles as live verified.")

    if errors:
        raise SystemExit("\n".join(errors))


def write_outputs(summary: dict[str, Any], out_dir: Path) -> None:
    """Write JSON and Markdown reports."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "legacy_2743138_mode_capture_summary.json"
    report_path = out_dir / "legacy_2743138_mode_capture_report.md"

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Legacy TCL 2743138 Mode Capture Report",
        "",
        f"Device ID: `{summary['deviceId']}`",
        "",
        "## Capture Files",
        "",
        *[f"- `{path}`" for path in summary["captureFiles"]],
        "",
        "## Inferred Profiles",
        "",
    ]
    for profile in summary["inferredProfiles"]:
        lines.extend(
            [
                f"### {profile['mode']}",
                "",
                f"- Evidence level: `{profile['evidence_level']}`",
                f"- Source lines: {', '.join(profile['source_lines'])}",
                f"- Payload: `{json.dumps(profile['payload'], ensure_ascii=False)}`",
                f"- Rationale: {profile['rationale']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Unsupported Old Assumptions",
            "",
            "- `baseMode=7` is not capture-supported as Fan for legacy `2743138`.",
            "- `baseMode=8` is not capture-supported as Auto/AI for legacy `2743138`.",
            "",
            "## Evidence Levels",
            "",
        ]
    )
    for name, description in summary["evidenceLevels"].items():
        lines.append(f"- `{name}`: {description}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_timeline(summary: dict[str, Any]) -> None:
    """Print a compact command timeline."""
    for command in summary["observedCommands"]:
        if command["command"] != "set":
            continue
        payload = ", ".join(f"{key}={value}" for key, value in command["payload"].items())
        print(
            f"{command['capture_file']}:{command['line']} "
            f"{command['timestamp_local']} seq={command['seq']} {payload}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="+", type=Path)
    parser.add_argument("--device-id", default="2743138")
    parser.add_argument("--out-dir", type=Path, default=Path("docs/capture_analysis"))
    parser.add_argument("--assert-legacy-mode-facts", action="store_true")
    parser.add_argument("--json", action="store_true", help="print summary JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    missing = [str(path) for path in args.captures if not path.exists()]
    if missing:
        print(f"Missing capture files: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(2)

    summary = build_summary(args.captures, args.device_id)
    if args.assert_legacy_mode_facts:
        assert_legacy_mode_facts(summary)
    write_outputs(summary, args.out_dir)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print_timeline(summary)


if __name__ == "__main__":
    main()
