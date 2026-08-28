# Changelog

## Unreleased

- Preserve transient refresh failures after an explicit cloud authentication
  rejection instead of retrying the already-rejected access token and
  incorrectly prompting for reauthentication.
- Classify TCL account authentication, rate-limit, protocol, and transient
  failures before interpreting token payloads, and retry cloud requests once
  only when the server explicitly rejects authentication.
- Serialize refreshes per TCL account, reuse account clients and public keys,
  and synchronize rotated credentials across every device entry for that
  account without reloading otherwise unchanged runtimes.
- Apply the same token-freshness boundary to status, statistics, and control
  requests, preserve updated account IDs, and use effective advanced account
  settings during password or SMS reauthentication.
- Return immutable command receipts from transport operations and atomically
  register accepted commands in each device session, eliminating the shared
  pending slot that could mix concurrent commands.
- Report cloud and UDP delivery outcomes separately from final status matching,
  and skip confirmation for commands no transport accepted.
- Scope command-confirmation Repairs issues to each config entry and prevent
  integration-derived statistics from overwriting device control state.

## 0.6.0

- Add a per-device `DeviceSession` boundary with source-aware state
  reconciliation and independent command IDs.
- Add a protocol driver contract and ordered registry while preserving the
  existing profile resolver as a compatibility alias.
- Share one UDP hub across config entries and route packets by discovered MAC
  or an unambiguous learned IP instead of creating one listener per entry.
- Persist TCL+ discovered device MAC metadata for deterministic local routing.
- Preserve existing config keys, entity IDs, command event name, cloud fallback,
  and guarded unsupported-device behavior.

## 0.5.0

- Add a TSL property-control profile for product `1112013595N` / device `45816970`, covering power, mode, and target-temperature writes.
- Parse protocol 1 TCL+ status fields for power, mode, temperatures, fan telemetry, swing telemetry, and common feature state.
- Disable unconfirmed fan speed, swing, and feature-switch writes for the TSL profile until their write payloads are verified.
- Centralize config-entry settings/profile resolution so setup, entities, and token refresh use the same data/options precedence.
- Add a GitHub Actions release workflow that packages the integration zip for version tags.

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
