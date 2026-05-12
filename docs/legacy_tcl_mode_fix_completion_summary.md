# Legacy TCL Mode Fix Completion Summary

Date: 2026-05-12

## Capture Files Used

- `newly_captured/tcl_1778556941.jsonl`
- `newly_captured/tcl_1778557400.jsonl`

## Facts Extracted

- Legacy Fan for device `2743138` is capture-supported as `baseMode=0` with `setTemp=73`, `degreeH=0`, `windSpd=0`, and `optSuper=0`.
- Legacy Dry is capture-supported as `baseMode=2` with fallback `setTemp=82`, `degreeH=0`, `windSpd=0`, and `optSuper=0`.
- Cool and Heat use grouped profile bundles with `turnOn=1`, encoded target temperature, `degreeH`, and `windSpd=0`.
- No supported legacy profile emits `baseMode=7` or `baseMode=8`.
- Auto/AI remains unsupported for legacy `2743138`.

## Code Files Changed

- `custom_components/tcl_udp_ac/command_bundles.py`
- `custom_components/tcl_udp_ac/temperature_codec.py`
- `custom_components/tcl_udp_ac/protocol_profiles.py`
- `custom_components/tcl_udp_ac/api.py`
- `custom_components/tcl_udp_ac/udp_client.py`
- `custom_components/tcl_udp_ac/climate.py`
- `tools/analyze_legacy_mode_capture.py`
- `tools/test_control_api.py`

## Tests Added Or Updated

- `tests/test_legacy_mode_capture_analysis.py`
- `tests/test_protocol_profiles.py`
- `tests/test_temperature_codec.py`
- `tests/test_legacy_capture_replay_contract.py`
- `tests/test_legacy_mode_profiles.py`
- `tests/test_legacy_mode_api.py`
- `tests/test_legacy_status_parser.py`
- `tests/test_command_status_reconciliation.py`
- `tests/test_legacy_climate_modes.py`
- `tests/test_legacy_mode_tool.py`
- Existing climate/tool protocol tests were updated for profile routing.

## Documentation Cleaned

- `README.md` links to the protocol truth registry.
- `tools/README.md` now documents profile bundles, legacy Fan `baseMode=0`, and unsupported Auto/AI.
- `findings.md` and `progress.md` mark old `baseMode=7/8` conclusions as superseded.
- `docs/protocol_truth/legacy_2743138_mode_profiles.md` is the current fact entry point.

## Remaining Unknowns

- Standalone temperature-only control is still not proven fixed.
- Auto/AI for legacy `2743138` is not capture-supported.
- Modern protocol `targetTemperature` / TSL write behavior needs a separate captured mutation before implementation.

## Rerun Commands

```bash
/usr/local/bin/uv run python -m unittest discover -s tests
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac tests tools
/usr/local/bin/uv run python tools/analyze_legacy_mode_capture.py \
  newly_captured/tcl_1778556941.jsonl \
  newly_captured/tcl_1778557400.jsonl \
  --device-id 2743138 \
  --assert-legacy-mode-facts \
  --out-dir docs/capture_analysis
/usr/local/bin/uv run python tools/test_control_api.py --device-id 2743138 --dry-run --test mode-matrix
```

Do not run live mutation unless explicitly using `--allow-live`; final cleanup must leave `turnOn=0`.
