# Changelog

## 0.9.4 - 2026-08-30

- Bring the brand metadata regression test into compliance with the
  repository's complete Ruff rule set after the 0.9.3 branding release.

## 0.9.3 - 2026-08-30

- Replace the generic air-conditioner artwork with the established TCL icon
  and logo already shared by the Home Assistant Brands entries for
  `tcl_home_unofficial` and `tcl_tv_remote`.
- Package the four standard local brand assets under the Home Assistant 2026.3+
  `brand/` path, fix the README image, and enable HACS brand validation.

## 0.9.2 - 2026-08-30

- Interpret the protocol 1 F-series healthy `errorCode` byte marker `[48]` as
  no fault instead of exposing a misleading error 48.
- Render defined F-series numeric fault identifiers with their product-panel
  short codes while preserving unknown identifiers for diagnostics.

## 0.9.1 - 2026-08-30

- Bring the protocol 1 implementation and related inventory code into full
  repository Ruff and formatting compliance after the initial 0.9.0 release.

## 0.9.0 - 2026-08-30

- Give every child entity its translated semantic name, so Home Assistant shows
  labels such as “Air conditioner 2 Eco mode” instead of repeating only the
  parent device name.
- Make protocol 1 product `1112013595N` explicitly cloud-only so it no longer
  opens a UDP subscription or emits discovery/status datagrams to the device's
  closed port.
- Use the captured native `POST /v1/thing/status` response shape for protocol 1
  while preserving the authenticated request and token-refresh lifecycle.
- Add TSL property control for exact automatic/seven-gear fan, horizontal and
  vertical swing, ECO, sleep, turbo, health, display, beep, temperature beep,
  auxiliary heat, anti-mildew, soft wind, self-clean, automatic fresh air, and
  fresh-air percentage.
- Expose every observed F-series diagnostic as stable diagnostic sensor or
  binary-sensor entities, including thermal, electrical, compressor, fan,
  valve, filter, self-clean, error, TSL metadata, and AI source fields.
- Deepen the protocol capability Interface so Home Assistant entities submit
  semantic intents without owning product identifiers or transport details.

## 0.8.1 - 2026-08-30

- Skip the redundant account-selection form when exactly one loaded TCL+
  account is available, so “add from existing account” opens the unconfigured
  device selector directly.
- Verify that the live account inventory contains both ACs and presents the
  unconfigured protocol 1 device as the default addable device.

## 0.8.0 - 2026-08-30

- Add a precise `DeviceDescriptor` semantic layer for stable TID/MAC identity,
  protocol metadata, and suggested device presentation without changing
  existing config-entry or entity unique IDs.
- Add account device inventory and a config-flow path that discovers and adds
  another unconfigured AC from an existing loaded TCL+ account without storing
  or requesting the password again.
- Route inventory requests through the existing token lifecycle, including one
  refresh/retry after explicit token rejection while preserving transient
  service errors.
- Route shared UDP traffic deterministically against both TID and MAC, and drop
  conflicting or otherwise ambiguous packets instead of cross-binding devices.
- Reconcile current descriptor metadata into existing entries so legacy
  single-device setups gain deterministic MAC routing when account discovery
  provides it.

## 0.7.1 - 2026-08-28

- Correlate command lifecycle events with the originating Home Assistant entity
  and context ID so orchestration consumers can distinguish dispatch from
  device confirmation.
- Preserve correlation metadata from command registration through applied and
  not-confirmed outcomes without coupling consumers to transport internals.

## 0.7.0 - 2026-08-28

- Treat TCL token payload `InternalError` as a transient service failure so a
  temporary server-side fault does not trigger Home Assistant reauthentication.
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
