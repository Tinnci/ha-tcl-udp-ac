# TCL AC Tooling

Use these tools with the same caution as a physical remote control. The cloud
control endpoints mutate the real air conditioner state.

## Safe Read-Only Check

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --status
```

## Live Control Tests

Live tests require `--allow-live`. By default the harness stops on the first
state mismatch and sends the app-captured shutdown group at the end:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --allow-live \
  --test combined-on-cool
```

Only use `--leave-on` when you intentionally want the AC to remain on after a
test. Only use `--continue-on-failure` when intentionally collecting failure
data across multiple controls.

Mode confirmation should use the matrix test. It sends capture-derived profile
bundles because live testing showed bare `baseMode=2` was acknowledged but
ignored while the device was already on:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --allow-live \
  --test mode-matrix \
  --delay 5
```

Temperature diagnosis should use the focused experiment. It sends only the
known legacy `convertMqtt` temperature command and reports captured
`targetTemperature`/TSL metadata separately; it does not invent an unknown TSL
write request:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --allow-live \
  --test temp-experiment \
  --delay 20
```

For the next temperature investigation, prefer the transaction matrix first.
It is dry-run by default unless you pass `--allow-live`, prints every outgoing
payload, and checks live status after 2s, 5s, and 10s for each candidate:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file newly_captured/tcl_1778556941.jsonl \
  --device-id 2743138 \
  --dry-run \
  --test temp-matrix
```

## Verified Command Rules

- Reliable power-off is not a bare `turnOn=0`. Use the app-captured shutdown
  group: `optSleepMd=0`, `optECO=0`, `optHealthy=0`, `optSuper=0`,
  `optHeat=0`, then `turnOn=0` in one message.
- Cool mode is `baseMode=1` for legacy `tid=2743138`.
- Heat mode is `baseMode=4` for this device.
- Mode changes should use profile bundles, not bare `baseMode` writes. For
  legacy `tid=2743138`, current capture-supported profiles are documented in
  `docs/protocol_truth/legacy_2743138_mode_profiles.md`.
- Default Home Assistant HVAC modes are cool, dry, and heat. Fan Only stays
  hidden by default, but when enabled for legacy `2743138` it uses
  `baseMode=0` with the captured Fan bundle. Auto/AI stays unsupported because
  no supported `baseMode=8` app request was observed.
- Fan changes should clear sleep/turbo overrides in the same message.
- Swing changes should send horizontal, vertical, and `optSolidWd=0` together.
- Temperature writes must run in a known Cool or Heat context. App captures
  show the slider sends `setTemp + degreeH + optSuper=0`; do not send naked
  temperature writes while the mode is unknown, Dry, Fan, or Off.
- `degreeH=0` is observed in captures. `degreeH=1` remains a protocol
  hypothesis until a half-degree app capture or guarded live test confirms it.
