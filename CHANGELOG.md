# Changelog

## 0.4.0

- Add TCL+ electricity/runtime report parsing and diagnostic sensors for current-month energy and runtime.
- Store discovered TCL+ product keys internally so statistics requests include the device context seen in app traffic.
- Keep TCL+ access/refresh token maintenance hidden from options while preserving HA reauth prompts when refresh can no longer continue.
- Use HA sensor semantics for report totals: energy/duration device classes with total state class, not total-increasing energy-dashboard meters.
- Confirm supported commands against refreshed device state, emit a `tcl_udp_ac_command_result` event, and create a Home Assistant Repairs issue when a command is not reflected in state within the timeout.

## 0.3.0

- Add TCL+ post-login AC discovery so users can select a device instead of manually entering the cloud TID and JIDs.
- Derive legacy cloud-control JIDs from captured TCL+ account metadata and keep the manual fallback for accounts where discovery is unavailable.
- Preserve protocol metadata from TCL+ device discovery and default legacy cloud control more cautiously for newer protocol 1 devices.
- Document the captured electricity/runtime statistics APIs and why they are not exposed as HA energy sensors yet.

## 0.2.1

- Align HACS metadata with the repository layout so custom repository installs resolve the integration content explicitly.
- Document the HACS update and removal flow for users installing from releases.
- Keep the README release badge synchronized with the Home Assistant manifest version.

## 0.2.0

- Add Home Assistant validation and unit-test workflows.
- Add TCL+ account login and automatic cloud token refresh support.
- Update the integration manifest to version 0.2.0.
