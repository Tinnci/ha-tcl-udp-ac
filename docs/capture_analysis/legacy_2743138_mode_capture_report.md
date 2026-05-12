# Legacy TCL 2743138 Mode Capture Report

Device ID: `2743138`

## Capture Files

- `newly_captured/tcl_1778556941.jsonl`
- `newly_captured/tcl_1778557400.jsonl`

## Inferred Profiles

### fan_only

- Evidence level: `capture-supported`
- Source lines: tcl_1778556941.jsonl:39, tcl_1778557400.jsonl:15
- Payload: `{"baseMode": "0", "setTemp": "73", "degreeH": "0", "windSpd": "0", "optSuper": "0"}`
- Rationale: User-reported Fan action aligns with observed baseMode=0 bundle; no supported baseMode=7 Fan command was observed.

### dry

- Evidence level: `capture-supported`
- Source lines: tcl_1778556941.jsonl:29, tcl_1778557400.jsonl:109
- Payload: `{"baseMode": "2", "setTemp": "82", "windSpd": "0", "optSuper": "0"}`
- Rationale: Observed app-style dry bundle uses baseMode=2 with temp/fan/super fields.

### cool

- Evidence level: `capture-supported`
- Source lines: tcl_1778556941.jsonl:9
- Payload: `{"turnOn": "1", "baseMode": "3", "setTemp": "73", "degreeH": "0", "windSpd": "0"}`
- Rationale: Observed app startup/cool bundle uses grouped power/mode/temp/fan fields.

## Unsupported Old Assumptions

- `baseMode=7` is not capture-supported as Fan for legacy `2743138`.
- `baseMode=8` is not capture-supported as Auto/AI for legacy `2743138`.

## Evidence Levels

- `observed`: Direct packet payload from capture.
- `inferred`: Timeline/user-action interpretation, not a packet fact.
- `capture-supported`: Implemented candidate backed by observed packet shape.
- `unsupported`: Old assumption not supported by these captures.
- `experimental`: Needs live verification before being called verified.
