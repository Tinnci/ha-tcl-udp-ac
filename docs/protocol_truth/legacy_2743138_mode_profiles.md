# Legacy 2743138 Mode Profiles

This is the active truth registry for legacy TCL AC device `2743138`.

## Evidence Sources

- `newly_captured/tcl_1778556941.jsonl`
- `newly_captured/tcl_1778557400.jsonl`
- Analyzer: `tools/analyze_legacy_mode_capture.py`
- Generated summary: `docs/capture_analysis/legacy_2743138_mode_capture_summary.json`
- Generated report: `docs/capture_analysis/legacy_2743138_mode_capture_report.md`

Evidence levels:

- Observed: packet fields are present in capture.
- Inferred: packet is associated with a user action by timeline and context.
- Capture-supported: implementation follows observed fields and an inferred profile.
- Implemented: code can generate the profile bundle.
- Verified: unit tests, replay tests, status parsing tests, or guarded live checks close the loop.

## Capture-Supported Profiles

Fan Only:

```json
{
  "turnOn": "1",
  "baseMode": "0",
  "setTemp": "73",
  "degreeH": "0",
  "windSpd": "0",
  "optSuper": "0"
}
```

Status mapping: legacy `baseMode=0` parses as Fan.

Dry:

```json
{
  "turnOn": "1",
  "baseMode": "2",
  "setTemp": "82",
  "degreeH": "0",
  "windSpd": "0",
  "optSuper": "0"
}
```

Status mapping: legacy `baseMode=2` parses as Dry / Dehumidify.

Cool:

```json
{
  "turnOn": "1",
  "baseMode": "3",
  "setTemp": "<encoded target, fallback 23C>",
  "degreeH": "<encoded half-degree flag>",
  "windSpd": "0"
}
```

Status mapping: legacy `baseMode=3` parses as Cool.

Heat:

```json
{
  "turnOn": "1",
  "baseMode": "4",
  "setTemp": "<encoded target, fallback 28C>",
  "degreeH": "<encoded half-degree flag>",
  "windSpd": "0"
}
```

Status mapping: legacy `baseMode=4` parses as Heat.

## Do Not Assume

- Do not map legacy Fan for `2743138` to `baseMode=7`.
- Do not map legacy Auto/AI for `2743138` to `baseMode=8`.
- Do not silently fallback to generic mode writes when a legacy profile rejects a mode.
- Do not mix standalone temperature experiments into the mode profile path.
- Do not add `optSuper=0` to Cool or Heat unless capture evidence marks it profile-required.

## Home Assistant Behavior

- The native climate entity is the primary UI and HomeKit Bridge target.
- Default HVAC modes remain Off, Cool, Dry, and Heat.
- Fan Only remains hidden by default. If explicitly enabled for legacy `2743138`, it uses the Fan profile above with `baseMode=0`.
- Auto/AI remains hidden by default and unsupported for legacy `2743138`.
- Duplicate Power switch stays compatibility-only and disabled by default.
- Temperatures are exposed in Celsius. Legacy protocol encoding stays internal as `setTemp` plus `degreeH`.

## Temperature Warning

Standalone legacy temperature control is still unresolved. A live command such as `setTemp=75`, `degreeH=0`, `optSuper=0` returned API success in earlier testing but verified status stayed at `setTemp=73`. Treat `targetTemperature` / TSL-style writes as a separate experiment until a safe captured mutation exists.

## Rerun Commands

Analyzer:

```bash
/usr/local/bin/uv run python tools/analyze_legacy_mode_capture.py \
  newly_captured/tcl_1778556941.jsonl \
  newly_captured/tcl_1778557400.jsonl \
  --device-id 2743138 \
  --assert-legacy-mode-facts \
  --out-dir docs/capture_analysis
```

Unit tests:

```bash
/usr/local/bin/uv run python -m unittest discover -s tests
```

Dry-run matrix:

```bash
/usr/local/bin/uv run python tools/test_control_api.py --device-id 2743138 --dry-run --test mode-matrix
```

Live matrix requires explicit `--allow-live` and must finish with final power-off cleanup.
