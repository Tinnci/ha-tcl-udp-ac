# Findings: Home Assistant Integration Search

## Translation Expansion
- Official Home Assistant custom integration localization docs say custom integrations read translation JSON from the integration-adjacent `translations` directory, named `<language_code>.json`, with BCP47 language codes.
- The same docs say custom integrations must not use `strings.json` or Home Assistant Core placeholder syntax; each translation file needs full text for each key.
- Added eight locale files beyond English: German `de`, Spanish `es`, French `fr`, Italian `it`, Japanese `ja`, Korean `ko`, Brazilian Portuguese `pt-BR`, and Simplified Chinese `zh-Hans`.

## HA 2026 Climate Paradigm Review
- Home Assistant 2026.1 release notes say Labs purpose-specific climate triggers now cover HVAC mode changes, target temperature changes/crossing thresholds, current temperature/humidity changes, and target humidity changes.
- Home Assistant 2026.5 release notes say purpose-specific state-based triggers and entity conditions now support duration/`for` behavior across climate and many other domains.
- Impact for this integration: the important contract is no longer only "can set mode and target temperature"; HA now benefits strongly from accurate `hvac_mode`, `hvac_action`, `current_temperature`, `target_temperature`, availability, and stable device/entity metadata because the automation UI builds higher-level climate triggers/conditions from those surfaces.
- Current code already moved in the right direction: climate exposes Celsius metadata, `hvac_action`, verified default modes, opt-in experimental Fan Only/Auto, grouped mode+setpoint writes, and a 1-minute backup poll; switches are mode-aware for Aux Heat; outdoor placeholder readings become unavailable.
- No immediate paradigm shift is required. The integration should remain a thin Home Assistant entity layer over a protocol-profile/command-bundle layer, with the coordinator as status truth.
- Main architecture risk remains capability modeling. Switches and HVAC modes are partly static/option-based, while TCL capability differs by device/profile. A future deepening opportunity is to promote "device capability profile" into the shared interface used by climate, switch, config/options, translations, and command building.
- Another improvement candidate is setup/config UX: the current config flow exposes many low-level cloud headers in the main user form and uses a single static unique ID. This works for one personal AC but does not align well with HA's device-oriented setup, multi-device flows, or localized selector option labels.
- Do not add humidity support unless the protocol provides reliable humidity fields; HA 2026 climate humidity triggers only help if `current_humidity` / target humidity are real. Fabricating humidity would be worse than omitting it.
- Implementation pass: `ProtocolProfile.capabilities` now centralizes verified/experimental HVAC modes and switch constraints; climate and switch entities consume that profile instead of owning separate capability rules.
- Entity registry pass: climate/switch/sensor entities now use `has_entity_name`, translation keys, and stable device identifiers from cloud TID when available, falling back only when no stable ID is known.
- Config flow pass: initial setup is now basic cloud/device controls; advanced capture headers are separated into an advanced step and remain available in options.

## Mode-Aware Switch Controls
- User confirmed Aux Heat should not be usable while cooling, but Turbo and Sleep may still be valid in Dry/Fan or other modes depending on device behavior.
- Implemented conservative mode-awareness in switch entities: switches can now declare `available_modes` and `requires_power`; Aux Heat declares `available_modes={"heat"}` and `requires_power=True`.
- Sleep and Turbo intentionally remain unrestricted until live captures prove narrower mode constraints.

## Outdoor Temperature Placeholder Handling
- Home Assistant official guidance says if an integration cannot fetch data, mark the entity unavailable; if the device/service is reached but an individual data field is missing, the entity state should be unknown rather than a fabricated value.
- The TCL protocol can report `outTemp=32°F`, which converts to `0.0°C`; for this device that is a placeholder when outdoor temperature cannot be read, not a trustworthy outdoor reading.
- Added parser-level filtering so cloud and UDP status parsers do not store placeholder outdoor readings, and sensor-level availability so Home Assistant/HomeKit receive unavailable/unknown instead of fake `0°C`.

## Coordinator / Orchestrator Review
- Review started 2026-05-12 for current Home Assistant integration orchestration: setup entry, coordinator refresh, UDP listener callbacks, client lifecycle, and entity command refresh paths.
- Current orchestration is simple and mostly coherent: `async_setup_entry()` creates one `TclUdpApiClient`, one `TclUdpDataUpdateCoordinator`, stores both in `entry.runtime_data`, starts the UDP listener, sends discovery, performs first refresh, then forwards climate/switch/sensor platforms.
- Coordinator refresh is UDP-first, then cloud-status merge when cloud is configured. UDP push callbacks call `async_set_updated_data()` directly.
- Entity command paths are centralized through the runtime client, then they request a coordinator refresh. Climate owns power; feature switches route to specific `async_set_*` client methods.
- Finding: setup/refresh has weak failure semantics. With no UDP discovery/status and no usable cloud status, `_async_update_data()` returns stale or empty last status instead of raising an update failure. That allows first setup to succeed with default/off-looking entities even when the device was never reached.
- Finding: listener startup failures bubble as `TclUdpApiClientCommunicationError`, not Home Assistant `ConfigEntryNotReady`. A port bind failure or temporary network setup issue will likely be treated as setup failure rather than a retryable not-ready state.
- Finding: unload order closes the client before unloading platforms. If platform unload fails, the config entry can remain partially loaded with a closed UDP client. Safer order is unload platforms first, then close the client only after successful platform unload.
- Finding: UDP push handling passes the mutable `_last_status` dictionary to the async coordinator callback. Subsequent merges mutate the same object reference. Passing a copy would make update boundaries clearer and reduce stale/diff ambiguity.
- Finding: sensor unit is now inconsistent with parsed data. Cloud and UDP parsers convert outdoor temperature to Celsius, but `TclUdpOutdoorTempSensor` still declares `UnitOfTemperature.FAHRENHEIT` and validates against Fahrenheit bounds.
- Test coverage note: the unit suite passes, but coordinator tests bypass real `DataUpdateCoordinator` initialization with `object.__new__()` and the Home Assistant stubs do not currently cover setup-entry retry semantics, unload ordering, or the sensor module.
- Fix pass: added lifecycle/sensor/UDP regression coverage in `tests/test_orchestrator_lifecycle.py`, expanded Home Assistant stubs for setup and sensor imports, mapped listener startup communication failures to `ConfigEntryNotReady`, made empty coordinator refreshes raise `UpdateFailed`, changed unload to close the client only after platform unload succeeds, passed UDP status snapshots to callbacks, changed outdoor sensor metadata/range to Celsius, and removed deprecated XML element truthiness checks.

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
- Superseded: the old `turnOn=1 + baseMode=3` run reflected status but later Cool captures and temperature tests show `baseMode=3` is not HA Cool for legacy `2743138`.
- Live grouped fan command `windSpd=1 + optSleepMd=0 + optSuper=0` verified.
- Live grouped swing command `directV=1 + directH=1 + optSolidWd=0` verified.
- Live heat mode command `baseMode=4` verified. This makes old tool mapping `heat=1` stale for the active device.
- Live bare power-off `turnOn=0` returned API success but did not change status; the AC remained on. The app-captured shutdown group `optSleepMd=0 + optECO=0 + optHealthy=0 + optSuper=0 + optHeat=0 + turnOn=0` verified as off.
- Live temperature command `setTemp=75 + degreeH=0 + optSuper=0` returned API success but did not change verified status from `setTemp=73`; temperature needs further capture or a narrower live test before claiming fixed.

## Home Assistant Testing Improvements
- Added lightweight Home Assistant stubs so climate/switch/coordinator entity behavior can be tested without installing full Home Assistant test dependencies.
- Added climate tests for Celsius UI metadata and routing of temperature, power/mode, fan, and swing controls.
- Added switch tests to prevent recreating a duplicate Power switch; on/off belongs to the climate entity.
- Added coordinator tests for UDP-first refresh, cloud fallback, and UDP error fallback.
- Added metadata tests for `manifest.json`, HACS metadata, and config/options translation labels.
- Normalized Home Assistant-facing temperatures to Celsius while still translating command temperatures to TCL protocol `setTemp`/`degreeH` values.
- Fresh `user_devices` captures contain two AC devices: current legacy control target `2743138` with protocol `0`, `setTemp`, `degreeH`, and empty `listControl`; newer device `45816970` with protocol `1`, `targetTemperature`, and work modes `1=cool`, `2=dry`, `3=fan`, `4=heat`, `5=AI`.
- Because the capture has no proven TSL write endpoint for `targetTemperature`, the temperature experiment must not send an invented TSL mutation. It should report comparable metadata and only mutate through the known legacy `convertMqtt/setTemp` path.
- The live harness should not advertise `baseMode=7` or `baseMode=8` as supported legacy profiles for `2743138`. Fan remains profile-gated as `baseMode=0`.
- Live mode matrix showed bare `baseMode=2` for dry returned API success but did not change status from cool after 5 seconds. Grouped `turnOn=1 + baseMode=2` did apply dry mode.
- Current legacy mapping: Cool is `baseMode=1`, Dry is `baseMode=2`, Heat is `baseMode=4`. Treat old `baseMode=3` Cool notes as superseded.
- Grouped `turnOn=1 + baseMode=7` and `turnOn=1 + baseMode=8` returned API success but status stayed in heat. Treat `baseMode=7/8` as unsupported for legacy device `2743138`.
- Live `temp-experiment` on 2026-05-12 with a 20-second wait still failed for legacy temperature control: `setTemp=75` was acknowledged but status stayed at `setTemp=73`, `celsiusSetTemp=23.0`, `degreeH=0`.

## Versatile Thermostat Compatibility Check
- Interpreted "versatile summer start" as Versatile Thermostat's `over_climate` / cooling auto-start use case, where this integration is the underlying climate entity.
- Versatile Thermostat's over-climate setup expects a controllable underlying thermostat/climate entity; Home Assistant climate docs define the needed contract as HVAC modes, target temperature support, turn on/off support, and set-temperature methods.
- `TclUdpClimate` exposes Celsius, `HVACMode.COOL`, `HVACMode.OFF`, `ClimateEntityFeature.TARGET_TEMPERATURE`, `TURN_ON`, and `TURN_OFF`, and implements `async_set_temperature`, `async_set_hvac_mode`, `async_turn_on`, and `async_turn_off`.
- Interface-level compatibility for summer cooling start is therefore present: Versatile Thermostat should be able to select this climate entity, turn it on, request Cool, and call set-temperature services.
- Real-device compatibility remains qualified for legacy device `2743138`: live temperature experiments show `setTemp` writes are API-accepted but not reflected in verified status, so a thermostat algorithm that depends on changing the underlying AC setpoint may not actually move the device setpoint until that protocol path is solved.
- The outdoor-temperature placeholder fix improves compatibility with thermostat/HomeKit consumers by exporting unavailable/unknown instead of a fake `0.0°C` reading when no valid outdoor reading exists.
- The mode-aware Aux Heat switch change is compatible with the summer use case because it hides heat-only auxiliary behavior during Cool instead of exposing irrelevant control state.
- Added `hvac_action` for better Versatile Thermostat over-climate feedback. It reports `off`, `cooling`, `heating`, `drying`, `fan`, or `idle` from the current mode and current/target temperature, giving VTherm a direct action signal instead of forcing it to simulate one.
- Added a contract regression test for the Versatile over-climate requirements: `COOL`, `OFF`, target-temperature feature, turn-on feature, turn-off feature, and non-null `hvac_action`.
- Optimized combined Home Assistant `climate.set_temperature` compatibility: when `hvac_mode` is supplied with the temperature, `TclUdpClimate.async_set_temperature()` now routes to the grouped mode profile, so calls such as "set Cool to 23.5°C" can power/mode the AC and carry the requested setpoint together.
- If a combined set-temperature call supplies `hvac_mode=off`, the entity now routes to power-off and does not emit a stale/irrelevant temperature write.
- Versatile Thermostat's `UnderlyingClimate` sends `climate.set_hvac_mode` and then, after a short delay, sends `climate.set_temperature` without `hvac_mode`. That meant our earlier combined `temperature + hvac_mode` optimization did not cover the actual over-climate follow-up setpoint call.
- Changed TCL `async_set_temperature()` so a standalone setpoint update while the AC is already in a mapped non-off HVAC mode also uses the grouped current-mode profile. This avoids falling back to the legacy standalone temperature write path that live tests classified as cloud-accepted but not reflected in verified status.
