# Task Plan: Home Assistant Integration Testing and UX Hardening

## Goal
Build a safer, repeatable Home Assistant integration testing pipeline that covers entity behavior, coordinator updates, config/options UX, protocol command grouping, and HomeKit-facing climate controls without accidental live AC mutation.

## Phases

| Phase | Status | Notes |
|---|---|---|
| Versatile over-climate standalone setpoint compatibility | complete | VTherm sends setpoint separately after mode changes; TCL now groups standalone setpoint writes with the current HVAC mode when on. |
| Combined climate service compatibility | complete | `set_temperature` now respects supplied `hvac_mode`, including grouped Cool+setpoint and Off handling. |
| Versatile Thermostat action feedback optimization | complete | Added `hvac_action` plus contract tests so over-climate consumers can observe cooling/heating/dry/fan/idle/off action. |
| Versatile Thermostat summer-start compatibility check | complete | Interface-level HA climate contract is compatible for Cool start/stop; live legacy setpoint writes remain the main caveat. |
| Outdoor temperature placeholder handling | complete | Dropped protocol placeholder outdoor readings and made the outdoor sensor unavailable instead of exporting fake 0°C. |
| Mode-aware switch controls | complete | Added switch availability metadata and applied the first conservative policy: Aux Heat requires powered Heat mode; uncertain Sleep/Turbo behavior remains unrestricted. |
| Translation locale expansion | complete | Added eight BCP47 translation files beyond English and verified each mirrors the complete Home Assistant config/options translation shape. |
| Coordinator/orchestrator fixes | complete | Added regression coverage and fixed setup retry semantics, empty-refresh failure, unload ordering, status snapshots, sensor Celsius unit, and XML element truthiness warning. |
| Coordinator/orchestrator architecture review | complete | Found coherent one-client/one-coordinator shape, plus risks in setup failure semantics, unload order, mutable status payloads, sensor units, and HA-realistic tests. |
| Baseline review | complete | Existing findings show real HA issues: duplicate Power control, grouped command mismatches, weak config UI, entry_id unique IDs, and no HA entity tests. |
| Plan testing strategy | complete | Defined layers: pure protocol tests, fake-client entity tests, coordinator tests, config-flow/options tests, dry-run/live harness split. |
| Implement HA test scaffolding | complete | Added lightweight Home Assistant stubs for entity/coordinator tests without full HA deps. |
| Entity behavior tests | complete | Climate and switch tests cover Celsius UI, power/mode, temperature, fan, swing, switch routing, and absence of a duplicate Power switch. |
| Coordinator/config tests | complete | Added coordinator fallback tests and metadata/translation tests. |
| UX/API improvements | complete | Climate now exposes Celsius; manifest has `integration_type`; translations label config/options fields. |
| Live harness refinements | complete | Added grouped mode matrix, known-limitation handling, and temperature experiment metadata reporting. |
| Verification | complete | 33 unit tests, compile check, live-refusal/dry-run checks, live mode/temp experiments, final read-only status, and diff check passed where expected. |
| Final report | complete | Final response summarizes fixed HA behavior, remaining live protocol uncertainty, and how to run the new pipeline. |
| HA 2026 climate paradigm review | complete | No immediate rewrite required; future deepening should center on a device capability profile and a cleaner config/options interface. |
| Capability/entity/config architecture implementation | complete | Central capability profile, translated entity names, Basic/Advanced config flow, no humidity, and stable device IDs implemented and verified. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| `python3 -m pytest tests` failed: `No module named pytest` | Tried local tests during first pass | Need install deps or use alternate static/harness checks. |
| `python3 -m compileall` failed on system Python 3.9 due `type TclUdpConfigEntry = ...` syntax | Used default macOS/Xcode Python | Re-ran compile check with bundled Python 3.12.13 successfully. |
| `ruff` unavailable | Tried bundled Python `-m ruff` and searched `command -v ruff` | Report as not run; no local ruff binary/module available. |
