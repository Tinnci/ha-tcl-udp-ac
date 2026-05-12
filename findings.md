# Findings: Home Assistant Integration Search

## Initial Discovery
- Repository path: `/Users/driezy/ha-tcl-udp-ac`
- File inventory contains a Home Assistant-style custom integration directory: `custom_components/tcl_udp_ac/`.
- The repo also contains `hacs.json`, which usually marks a repository as installable through HACS.
- `config/configuration.yaml` exists, likely example or development Home Assistant configuration.
- Git status shows modified integration files: `custom_components/tcl_udp_ac/api.py`, `custom_components/tcl_udp_ac/climate.py`, and `custom_components/tcl_udp_ac/udp_client.py`.

## To Confirm
- Read `custom_components/tcl_udp_ac/manifest.json`.
- Read `hacs.json`.
- Read `README.md`.
- Check integration platforms and config flow.
- Search for HomeKit, Apple Home, and bridge references.

## Confirmed Home Assistant Integration
- `custom_components/tcl_udp_ac/manifest.json` declares Home Assistant domain `tcl_udp_ac`, name `TCL UDP Air Conditioner`, `config_flow: true`, `iot_class: local_push`, documentation/issue tracker URLs, and version `0.1.0`.
- `hacs.json` declares HACS metadata with name `TCL UDP Air Conditioner` and minimum Home Assistant `2024.1.0`.
- `README.md` explicitly describes this as a "TCL UDP Air Conditioner Integration for Home Assistant" with HACS and manual installation instructions.
- `custom_components/tcl_udp_ac/__init__.py` forwards three Home Assistant platforms: `climate`, `switch`, and `sensor`.
- `custom_components/tcl_udp_ac/config_flow.py` implements UI setup and options flow for the integration.
- `custom_components/tcl_udp_ac/climate.py` implements a `ClimateEntity` with HVAC modes, fan modes, swing modes, and temperature control.
- `custom_components/tcl_udp_ac/switch.py` implements switches for power, eco, display, health, sleep, turbo, aux heat, and beep.
- `custom_components/tcl_udp_ac/sensor.py` implements an outdoor temperature sensor.
- `config/configuration.yaml` is a local/dev Home Assistant config enabling debug logs for `custom_components.tcl_udp_ac`.
- `docs/notes/project-layout.md` says `custom_components/tcl_udp_ac/` is the Home Assistant integration code.

## Apple Home / HomeKit Check
- Repo-wide text search found no direct HomeKit, Apple Home, or bridge implementation outside generic Apple assets in the vendored/extra `brands_repo`.
- This project appears to expose Home Assistant entities; Apple Home would likely be handled by Home Assistant's built-in HomeKit Bridge integration, not by this repository.

## App Emulation / Protocol Clues
- `custom_components/tcl_udp_ac/udp_client.py` implements local UDP traffic on ports `10074` and `10075`, parses XML status messages, discovers device IP/MAC/port, and sends status/control messages.
- `custom_components/tcl_udp_ac/api.py` contains cloud HTTP fallback/control code using TCL app-like headers and endpoints such as `io.zx.tcljd.com`.
- `tests/test_jsonl_capture_compare.py` contains tests around captured app/cloud GET status and POST control traffic.
- Ignored/local capture files exist: `tcl_1770274357.jsonl` and `tcl_1770274433.jsonl`.

## Protocol Diagnosis
- `/Users/driezy/Downloads/tcl/tools/*.py` contains reverse-engineering helpers, not another Home Assistant integration.
- `/Users/driezy/Downloads/tcl/captures/tcl_1770274433.jsonl` contains 21 captured cloud `convertMqtt` POST requests and status responses for `tid=2743138`.
- Captured app commands use lowercase cloud tags with `value` attributes, for example `setTemp value="75"`, `degreeH value="0"`, `optSuper value="0"`, `windSpd value="1"`, `directH value="0"`, `directV value="1"`, and `optSleepMd value="0"`.
- Captured status reports heat as `baseMode="4"`. The integration previously sent heat as cloud `baseMode="1"`.
- Captured sleep mode uses numeric `optSleepMd` values `0`, `1`, `2`, and `3`. The integration previously exposed sleep as a boolean switch and sent cloud value `on`/`off`, which does not match the app protocol.
- Captured swing changes include `optSolidWd` alongside `directH` and `directV`. The integration previously did not know how to map `OptSolidWd`.
- Patched command mapping so heat maps to `baseMode=4`, sleep switch emits numeric `1`/`0`, `OptSolidWd` maps to cloud `optSolidWd`, swing clears solid-wind mode, and fan speed clears sleep/turbo overrides.

## Home Assistant / HACS Best-Practice Notes
- HACS structure is broadly correct: one integration under `custom_components/tcl_udp_ac`, root `README.md`, root `hacs.json`, and integration `manifest.json`.
- Manifest has the HACS-required keys: `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, and `version`.
- Manifest should explicitly add `integration_type`, likely `device` for one AC per config entry or `hub` if this integration will manage multiple ACs from one entry.
- Integration correctly uses `ConfigEntry.runtime_data`.
- Entity unique IDs exist, but they are based on `config_entry.entry_id`; better practice is to use a stable device identifier such as discovered MAC/TCL ID once available.
- Config flow exists, but it does not validate connectivity or cloud credentials during setup. That is below current Home Assistant quality guidance.
- `translations/en.json` has no labels/descriptions for the many config fields, making the UI setup poor for users.
- No direct HomeKit/Apple Home bridge code exists; this integration should expose HA climate/switch/sensor entities and rely on Home Assistant HomeKit Bridge.
- The climate entity previously exposed `UnitOfTemperature.FAHRENHEIT`, 60.8-87.8°F bounds, and 0.9°F steps. That mismatched the TCL+ app/status data, which exposes `celsiusSetTemp` and a 16-31°C, 0.5°C user-facing control model.

## Live Control Findings - Fresh Token
- Fresh capture file `/Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl` contains usable `convertMqtt` credentials for `tid=2743138`.
- Initial live status on 2026-05-12 showed `LINE_STATUS=2`, `turnOn=0`, `baseMode=0`, `setTemp=73`, `degreeH=0`, `windSpd=0`, `directH=0`, `directV=0`.
- Live combined cloud command `turnOn=1 + baseMode=3` in one `convertMqtt` message returned success and status verified as `turnOn=1`, `baseMode=3`.
- Live grouped fan command `windSpd=1 + optSleepMd=0 + optSuper=0` verified.
- Live grouped swing command `directV=1 + directH=1 + optSolidWd=0` verified.
- Live heat mode command `baseMode=4` verified. This makes old tool mapping `heat=1` stale for the active device.
- Live bare power-off `turnOn=0` returned API success but did not change status; the AC remained on. The app-captured shutdown group `optSleepMd=0 + optECO=0 + optHealthy=0 + optSuper=0 + optHeat=0 + turnOn=0` verified as off.
- Live temperature command `setTemp=75 + degreeH=0 + optSuper=0` returned API success but did not change verified status from `setTemp=73`; temperature needs further capture or a narrower live test before claiming fixed.

## Home Assistant Testing Improvements
- Added lightweight Home Assistant stubs so climate/switch/coordinator entity behavior can be tested without installing full Home Assistant test dependencies.
- Added climate tests for Celsius UI metadata and routing of temperature, power/mode, fan, and swing controls.
- Added switch tests to prevent the previous Power switch regression where `enabled=...` was sent to `async_set_power()` instead of `power=...`.
- Added coordinator tests for UDP-first refresh, cloud fallback, and UDP error fallback.
- Added metadata tests for `manifest.json`, HACS metadata, and config/options translation labels.
- Normalized Home Assistant-facing temperatures to Celsius while still translating command temperatures to TCL protocol `setTemp`/`degreeH` values.
- Fresh `user_devices` captures contain two AC devices: current legacy control target `2743138` with protocol `0`, `setTemp`, `degreeH`, and empty `listControl`; newer device `45816970` with protocol `1`, `targetTemperature`, and work modes `1=cool`, `2=dry`, `3=fan`, `4=heat`, `5=AI`.
- Because the capture has no proven TSL write endpoint for `targetTemperature`, the temperature experiment must not send an invented TSL mutation. It should report comparable metadata and only mutate through the known legacy `convertMqtt/setTemp` path.
- The live harness should not advertise `baseMode=7` or `baseMode=8` as supported legacy profiles for `2743138`. Later captures supersede the older Fan assumption and show Fan as `baseMode=0`.
- Live mode matrix showed bare `baseMode=2` for dry returned API success but did not change status from cool after 5 seconds. Grouped `turnOn=1 + baseMode=2` did apply dry mode.
- Grouped `turnOn=1 + baseMode=3`, `turnOn=1 + baseMode=2`, and `turnOn=1 + baseMode=4` verified for cool, dry, and heat respectively.
- Grouped `turnOn=1 + baseMode=7` and `turnOn=1 + baseMode=8` returned API success but status stayed in heat. Treat `baseMode=7/8` as unsupported for legacy device `2743138`; Fan Only is now capture-supported through the newer `baseMode=0` profile bundle.
- Live `temp-experiment` on 2026-05-12 with a 20-second wait still failed for legacy temperature control: `setTemp=75` was acknowledged but status stayed at `setTemp=73`, `celsiusSetTemp=23.0`, `degreeH=0`.
