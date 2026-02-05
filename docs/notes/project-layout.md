# Project Layout

## Core integration
- `custom_components/tcl_udp_ac/` — Home Assistant integration code.

## Test suite
- `tests/` — Unit tests for protocol and capture comparisons.

## Tools
- `tools/` — Local developer utilities (pcap analysis, UDP tests). Excluded from linting.

## Scripts
- `scripts/` — Pre-commit helpers and automation.

## Captures (local only)
- `tcl_*.jsonl` — Local network captures, ignored by Git.
