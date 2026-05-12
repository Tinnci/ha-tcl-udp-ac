# Home Assistant Integration Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable Home Assistant integration test pipeline that catches entity, config, coordinator, and protocol regressions without accidentally controlling the real AC.

**Architecture:** Keep protocol tests pure and fast; test Home Assistant entity behavior with fake coordinators/clients; reserve live AC checks for an explicit `--allow-live` harness. Do not create a new worktree for this repo.

**Tech Stack:** Python 3.12 via `/usr/local/bin/uv`, stdlib `unittest` unless Home Assistant test dependencies are added later, custom integration files under `custom_components/tcl_udp_ac/`, and helper scripts under `tools/`.

---

## File Structure

- Modify: `/Users/driezy/ha-tcl-udp-ac/tests/test_protocol_commands.py`
  - Keep pure protocol command mapping and grouped command regression tests.
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/ha_stubs.py`
  - Provide small Home Assistant module stubs for entity imports when full HA test deps are not installed.
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_climate_entity.py`
  - Verify `TclUdpClimate` calls the client correctly for power, mode, fan, swing, and temperature.
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_switch_entity.py`
  - Verify switch routing, especially Power using `power=...` and feature switches using `enabled=...`.
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_coordinator.py`
  - Verify update flow requests UDP status, fetches cloud fallback, merges status, and returns last status after errors.
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_config_metadata.py`
  - Validate manifest metadata, translation coverage for config/options fields, and HACS structure.
- Modify: `/Users/driezy/ha-tcl-udp-ac/tools/test_control_api.py`
  - Keep live tests opt-in and use only as a final manual smoke test.
- Modify: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/manifest.json`
  - Add `integration_type` once tests pin expected metadata.
- Modify: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/translations/en.json`
  - Add labels/descriptions for config and options fields.

---

### Task 1: Lock Protocol Command Groups

**Files:**
- Modify: `/Users/driezy/ha-tcl-udp-ac/tests/test_protocol_commands.py`
- Modify only if tests fail: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/api.py`

- [ ] **Step 1: Add regression tests for verified command groups**

Add tests that assert:

```python
asyncio.run(client.async_set_power(power=False))
assert calls == [[
    ("Opt_sleepMode", "0"),
    ("Opt_ECO", "off"),
    ("OptHealthy", "off"),
    ("Opt_super", "off"),
    ("OptHeat", "off"),
    ("TurnOn", "off"),
]]
```

Also assert heat maps to `baseMode=4`, fan clears sleep/turbo, and swing clears `OptSolidWd`.

- [ ] **Step 2: Run the protocol tests**

```bash
/usr/local/bin/uv run python -m unittest tests.test_protocol_commands
```

Expected: pass. Any failure means the integration drifted away from live-verified protocol behavior.

---

### Task 2: Add Home Assistant Import Stubs

**Files:**
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/ha_stubs.py`
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_climate_entity.py`

- [ ] **Step 1: Write a failing climate import test**

Create a test that imports `custom_components.tcl_udp_ac.climate` through stubs and constructs `TclUdpClimate` with a fake coordinator.

- [ ] **Step 2: Implement only the needed stubs**

Stub these minimum symbols:

```python
homeassistant.components.climate.ClimateEntity
homeassistant.components.climate.ClimateEntityFeature
homeassistant.components.climate.HVACMode
homeassistant.components.climate.FAN_AUTO/FAN_LOW/FAN_MEDIUM/FAN_HIGH
homeassistant.components.climate.SWING_OFF/SWING_VERTICAL/SWING_HORIZONTAL/SWING_BOTH
homeassistant.const.ATTR_TEMPERATURE
homeassistant.const.UnitOfTemperature
homeassistant.helpers.update_coordinator.CoordinatorEntity
```

- [ ] **Step 3: Run the import test**

```bash
/usr/local/bin/uv run python -m unittest tests.test_climate_entity
```

Expected: pass without requiring full Home Assistant installed.

---

### Task 3: Test Climate Entity Behavior

**Files:**
- Modify: `/Users/driezy/ha-tcl-udp-ac/tests/test_climate_entity.py`
- Modify if needed: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/climate.py`

- [ ] **Step 1: Test mode and power calls**

Cover:
- `async_set_hvac_mode(HVACMode.OFF)` calls `async_set_power(power=False)`.
- turning on from off calls `async_set_power_mode(power=True, mode_str=<mode>)`.
- changing mode while on calls `async_set_mode(<mode>)`.
- `async_turn_on()` restores last known mode or defaults to cool.

- [ ] **Step 2: Test fan, swing, and temperature calls**

Cover:
- fan `high/medium/low/auto` maps to TCL values.
- swing modes map to vertical/horizontal booleans.
- temperature calls `async_set_temperature(float_value)`.
- each successful command requests coordinator refresh exactly once.

- [ ] **Step 3: Run climate tests**

```bash
/usr/local/bin/uv run python -m unittest tests.test_climate_entity
```

Expected: pass.

---

### Task 4: Test Switch Entity Behavior

**Files:**
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_switch_entity.py`
- Modify if needed: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/switch.py`

- [ ] **Step 1: Test Power switch routing**

Assert Power switch on/off calls:

```python
client.async_set_power(power=True)
client.async_set_power(power=False)
```

This prevents the previous `enabled=...` regression.

- [ ] **Step 2: Test feature switch routing**

Assert sleep/turbo/display/beep switches call:

```python
client.async_set_sleep_mode(enabled=True)
client.async_set_turbo_mode(enabled=False)
```

- [ ] **Step 3: Run switch tests**

```bash
/usr/local/bin/uv run python -m unittest tests.test_switch_entity
```

Expected: pass.

---

### Task 5: Test Coordinator Behavior

**Files:**
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_coordinator.py`
- Modify if needed: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/coordinator.py`

- [ ] **Step 1: Test normal update**

Fake client should record:

```python
await client.async_request_status()
await client.async_fetch_cloud_status()
return client.get_last_status()
```

- [ ] **Step 2: Test UDP error fallback**

When `async_request_status()` raises `TclUdpApiClientError`, coordinator should still fetch cloud status if cloud is enabled and return last status.

- [ ] **Step 3: Run coordinator tests**

```bash
/usr/local/bin/uv run python -m unittest tests.test_coordinator
```

Expected: pass.

---

### Task 6: Test Config and Metadata UX

**Files:**
- Create: `/Users/driezy/ha-tcl-udp-ac/tests/test_config_metadata.py`
- Modify: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/manifest.json`
- Modify: `/Users/driezy/ha-tcl-udp-ac/custom_components/tcl_udp_ac/translations/en.json`

- [ ] **Step 1: Add metadata tests**

Assert:
- `manifest.json` has `integration_type`.
- `domain` is `tcl_udp_ac`.
- `iot_class` is appropriate.
- `hacs.json` exists and has `name`.

- [ ] **Step 2: Add translation coverage tests**

Assert every config/options key from `const.py` has a user-facing translation label or description.

- [ ] **Step 3: Patch metadata/translations**

Add missing labels/descriptions and `integration_type`. Choose `device` unless the config flow is changed to manage multiple ACs from one entry.

- [ ] **Step 4: Run metadata tests**

```bash
/usr/local/bin/uv run python -m unittest tests.test_config_metadata
```

Expected: pass.

---

### Task 7: Keep Live Experiments Separate

**Files:**
- Modify: `/Users/driezy/ha-tcl-udp-ac/tools/test_control_api.py`
- Modify: `/Users/driezy/ha-tcl-udp-ac/tools/README.md`

- [ ] **Step 1: Preserve safety rails**

Live mutation must continue to require:

```bash
--allow-live
```

Default behavior after any live mutation should remain final safe power-off cleanup.

- [ ] **Step 2: Add a no-live regression check**

Run:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --test combined-on-cool
```

Expected: exits non-zero and prints refusal without controlling the AC.

- [ ] **Step 3: Keep live smoke tests manual**

Only run this when the user explicitly wants real AC movement:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --allow-live \
  --test combined-on-cool
```

Expected: final cleanup leaves `turnOn=0`.

---

### Task 8: Final Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run all local tests**

```bash
/usr/local/bin/uv run python -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 2: Compile check**

```bash
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac tests tools
```

Expected: no output, exit 0.

- [ ] **Step 3: Diff hygiene**

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Read-only AC status check**

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --status
```

Expected: prints current status only; no control commands sent.
