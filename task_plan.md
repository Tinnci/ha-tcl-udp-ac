# Task Plan: Home Assistant Integration Testing and UX Hardening

## Goal
Build a safer, repeatable Home Assistant integration testing pipeline that covers entity behavior, coordinator updates, config/options UX, protocol command grouping, and HomeKit-facing climate controls without accidental live AC mutation.

## Phases

| Phase | Status | Notes |
|---|---|---|
| Baseline review | complete | Existing findings show real HA issues: Power switch keyword bug, grouped command mismatches, weak config UI, entry_id unique IDs, and no HA entity tests. |
| Plan testing strategy | complete | Defined layers: pure protocol tests, fake-client entity tests, coordinator tests, config-flow/options tests, dry-run/live harness split. |
| Implement HA test scaffolding | complete | Added lightweight Home Assistant stubs for entity/coordinator tests without full HA deps. |
| Entity behavior tests | complete | Climate and switch tests cover Celsius UI, power/mode, temperature, fan, swing, and switch routing. |
| Coordinator/config tests | complete | Added coordinator fallback tests and metadata/translation tests. |
| UX/API improvements | complete | Climate now exposes Celsius; manifest has `integration_type`; translations label config/options fields. |
| Live harness refinements | complete | Added grouped mode matrix, known-limitation handling, and temperature experiment metadata reporting. |
| Verification | complete | 33 unit tests, compile check, live-refusal/dry-run checks, live mode/temp experiments, final read-only status, and diff check passed where expected. |
| Final report | complete | Final response summarizes fixed HA behavior, remaining live protocol uncertainty, and how to run the new pipeline. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| `python3 -m pytest tests` failed: `No module named pytest` | Tried local tests during first pass | Need install deps or use alternate static/harness checks. |
| `python3 -m compileall` failed on system Python 3.9 due `type TclUdpConfigEntry = ...` syntax | Used default macOS/Xcode Python | Re-ran compile check with bundled Python 3.12.13 successfully. |
| `ruff` unavailable | Tried bundled Python `-m ruff` and searched `command -v ruff` | Report as not run; no local ruff binary/module available. |
