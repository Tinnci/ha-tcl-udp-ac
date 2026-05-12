# Legacy 2743138 Protocol Profile

This is the active protocol note for TCL legacy device `2743138`. Older
capture-analysis files and experiment logs that treated `baseMode=3` as Cool
have been removed because later captures and live tests contradicted them.

## Evidence

- `newly_captured/tcl_1778557400.jsonl`: Cool context uses `baseMode=1`;
  temperature slider writes are `setTemp + degreeH + optSuper=0`.
- `newly_captured/tcl_1778569147.jsonl`: user sequence was Cool then Heat.
  The capture switches to `baseMode=1`, sends Cool temperature changes, then
  switches to `baseMode=4` and sends Heat temperature changes.
- `newly_captured/tcl_1778556941.jsonl`: earlier Fan/送风 bundle evidence for
  `baseMode=0` with the app-style default temperature/fan/super fields.
- Live tests with `baseMode=3` accepted cloud transport but did not apply the
  requested temperature. Treat that as a rejected old assumption, not as Cool.

## Unified Profile

The integration resolves `2743138` to `Legacy2743138Profile`. Home Assistant
climate code should not know protocol numbers directly. It should call the API,
the API should call the profile, and the profile should build the command
bundle.

Supported profile mappings:

| HA intent | Legacy payload shape | Status mapping |
| --- | --- | --- |
| Cool | `turnOn=1, baseMode=1, setTemp=<target>, degreeH=<flag>, windSpd=0, optSuper=0` | `baseMode=1 -> cool` |
| Dry | `turnOn=1, baseMode=2, setTemp=82, degreeH=0, windSpd=0, optSuper=0` | `baseMode=2 -> dry` |
| Heat | `turnOn=1, baseMode=4, setTemp=<target>, degreeH=<flag>, windSpd=0, optSuper=0` | `baseMode=4 -> heat` |
| Fan Only | `turnOn=1, baseMode=0, setTemp=73, degreeH=0, windSpd=0, optSuper=0` | `baseMode=0 -> fan` |
| Off | `optSleepMd=0, optECO=0, optHealthy=0, optSuper=0, optHeat=0, turnOn=0` | `turnOn=0` |

Unsupported or unverified:

- `baseMode=3` is not Cool for this profile. Do not use it for HA Cool.
- `baseMode=7` is not supported Fan for this profile.
- `baseMode=8` / Auto / AI is not supported for this profile.
- Dry and Fan do not expose normal temperature control.

## Temperature

Temperature control is only valid when the known current mode is Cool or Heat.
In that context, App captures show standalone temperature slider writes as:

```json
{
  "setTemp": "<encoded target>",
  "degreeH": "0",
  "optSuper": "0"
}
```

Home Assistant should therefore call the profile temperature command only when
the last known mode is Cool or Heat. Unknown, Dry, Fan, and Off contexts should
not send a naked `setTemp`.

`degreeH=0` is observed. `degreeH=1` remains unconfirmed until a half-degree
App capture or live test proves it.
