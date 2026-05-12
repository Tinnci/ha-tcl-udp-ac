# Legacy TCL Mode Mapping Fix Baseline

## Repository State

- Branch: `main`
- Target device ID: `2743138`
- New capture sources:
  - `newly_captured/tcl_1778556941.jsonl` (58K)
  - `newly_captured/tcl_1778557400.jsonl` (137K)
- Worktree was already dirty before this task; unrelated local files and caches must not be staged broadly.

## Existing Entry Points

- API command builder: `custom_components/tcl_udp_ac/api.py`
- Cloud status parser: `custom_components/tcl_udp_ac/api.py`
- UDP status/parser and sender: `custom_components/tcl_udp_ac/udp_client.py`
- Home Assistant climate mode handling: `custom_components/tcl_udp_ac/climate.py`
- Fan/Auto option visibility: `custom_components/tcl_udp_ac/config_flow.py`, `custom_components/tcl_udp_ac/const.py`
- Live/dry-run control harness: `tools/test_control_api.py`
- Existing tests: `tests/test_protocol_commands.py`, `tests/test_climate_entity.py`, `tests/test_control_tool.py`, `tests/test_temperature_units.py`

## Mode Mapping Entry Points

- `CloudClient._map_cloud_item()` maps `BaseMode` values into cloud `baseMode`.
- `CloudClient._parse_cloud_status()` maps cloud `baseMode` into HA mode strings.
- `UdpClient._parse_status()` maps local status mode tags into HA mode strings.
- `TclUdpClimate.async_set_hvac_mode()` routes HA HVAC mode changes to client methods.
- `tools/test_control_api.py` defines `MODE_MAP` and live mode matrix behavior.

## Known Stale Assumptions

- Legacy Fan for `2743138` must not be assumed to use `baseMode=7`.
- Legacy Auto/AI for `2743138` must not be assumed to use `baseMode=8`.
- Legacy HVAC mode changes are command bundles, not simple `baseMode` updates.
- Standalone temperature-only control remains an experiment and is not proven fixed.
