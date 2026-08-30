# Repository guidance

## Tooling and scope

- Use `uv` for Python environments and test commands. Do not introduce Node.js tooling for integration work.
- Preserve unrelated user changes. Keep authentication, transport, protocol-profile, and entity concerns in their existing modules instead of growing a new catch-all abstraction.
- Do not commit credentials, access tokens, refresh tokens, Home Assistant secrets, host passwords, packet captures containing secrets, or sanitized values that can be reversed.
- This repository belongs to the GitHub account `Tinnci`. Before committing or pushing, make sure `gh` is using `Tinnci` and the repository-local `hooks.expectedGhAccount` remains `Tinnci`. Restore the user's previous active account after pushing when appropriate.

## Authentication architecture

- `AccountClient` owns TCL account HTTP behavior and response classification. Keep these failure classes distinct:
  - HTTP 401/403 or an explicit credential rejection is an authentication failure.
  - HTTP 429 is rate limiting.
  - A successful response without the required token fields is a protocol failure.
  - Timeouts, DNS failures, connection failures, and 5xx responses are transient service failures.
- Never convert transient or rate-limit failures into Home Assistant reauthentication. They must preserve the existing session and allow the normal UDP/cloud fallback behavior.
- TCL has returned HTTP 200 token payloads containing `InternalError` during temporary service failures. Classify that payload as transient, not as credential rejection; add a regression test before expanding payload-based authentication classifications.
- Every authorized cloud status, statistics, and control request must pass through `TokenManager.async_authenticated_request`. Do not add coordinator-only refresh calls or bypass this seam for a new endpoint.
- A cloud request may be retried once only after an explicit 401/403-style `CloudAuthRejectedError`. Refresh with the rejected token as the compare value so concurrent callers can observe and reuse a token already rotated by another caller. A second rejection becomes `ConfigEntryAuthFailed`.
- If that forced refresh encounters a transient, rate-limit, or server failure, preserve and propagate that failure. Do not retry the already-rejected access token and do not convert the failure to `ConfigEntryAuthFailed`. Proactive refresh may still retain a not-yet-rejected access token after a transient refresh failure.
- Manual-token entries have no refresh path. If their token is explicitly rejected, raise a clear `ConfigEntryAuthFailed` diagnostic instead of silently retrying or treating it as a network failure.

## Credential persistence and config entries

- `CredentialManager` is shared through `IntegrationRuntime`. Refresh locks are scoped by TCL account ID, not config-entry ID, so devices on the same account use a single-flight refresh.
- Re-read access token, refresh token, and account ID inside the account lock. This is required for the double-check that prevents rotating-refresh-token races.
- Persist rotated credentials to every config entry with the same previous account ID. Preserve a previous refresh token when TCL omits a replacement, accept a canonical account ID returned by TCL, and hot-update loaded device sessions.
- Token fields are authoritative in `entry.data`; stale token values in `entry.options` must not override them. Other effective settings continue to use options-over-data precedence.
- Use `AuthSettings` for login, refresh, and reauthentication clients. Password and SMS reauthentication must use effective entry settings and synchronize credentials through `CredentialManager`.
- Credential-only entry updates must not reload the integration. `reload_signature` excludes token fields; changes to runtime-affecting noncredential settings must still reload normally.
- Keep account-client instances cached per `AuthSettings` so the TCL public key cache survives repeated refreshes.

## Multi-device inventory and routing

- Keep one config entry per physical AC. The cloud TID remains the config-entry unique ID, device-registry identifier, and entity unique-ID prefix.
- `DeviceDescriptor` owns device identity and suggested presentation metadata; it must not own credentials, HTTP behavior, coordinator state, or entity lifecycle.
- `AccountDeviceInventory` is a discovery snapshot, not an account config entry. Adding from an existing account must create another ordinary per-device entry.
- Authorized inventory requests must pass through the source entry's `TokenManager.async_authenticated_request`; explicit token rejection gets the same single refresh/retry policy as other cloud requests.
- UDP subscriptions use every known stable identity (currently TID and MAC). Never fan out an explicitly identified packet; conflicting or ambiguous routes must be dropped.
- Inventory reconciliation may refresh descriptor metadata but must not change existing config-entry unique IDs, entity unique IDs, config-entry titles, or user-customized registry names.

## Protocol 1 TSL devices

- Product `1112013595N` / protocol 1 is cloud-only. Its `ProtocolDriver` must keep local listener, discovery, status request, and legacy XML control disabled; do not emit periodic UDP discovery for it.
- Fetch its authoritative status with `POST /v1/thing/status` and body `{"deviceId": tid}`. Normalize `data.status`; do not route protocol 1 through the legacy `curStatus` response shape.
- Power, mode, target temperature, seven-gear/automatic fan, swing, profile-described feature switches, and numeric controls compile to TSL property bundles. Keep product identifiers and expected-state projections inside the protocol profile rather than adding protocol conditionals to entities or the coordinator.
- Preserve all observed F-series diagnostics through profile-described HA entities. Do not invent physical units for fan-speed or valve fields. For `errorCode`, normalize the observed healthy byte marker `[48]` (ASCII `"0"`) to `none`, map defined numeric fault identifiers to the product-panel short codes, and preserve unknown identifiers verbatim. Accept both `expansionValve` and the observed `expansionValve ` key.
- Every TSL status and property request still passes through `TokenManager.async_authenticated_request`, and HTTP acceptance is not device confirmation; retain the normal command status-match loop.

## Tests and translations

- Run the complete suite after authentication, persistence, lifecycle, config-flow, or cloud-request changes:

  ```sh
  uv run --with aiohttp --with 'cryptography==46.0.5' --with voluptuous --with yarl python -m unittest discover -s tests
  ```

- Also run:

  ```sh
  uv run python -m compileall -q custom_components/tcl_udp_ac tests
  uv run --with ruff ruff check --select F,I,N custom_components/tcl_udp_ac tests
  git diff --check
  ```

- Authentication tests must cover ordinary refresh, expired refresh tokens, transient failures, explicit rejection with one retry, concurrent same-account refresh, cross-entry synchronization, hot updates, and credential-only no-reload behavior.
- All primary translation JSON files must have the same leaf-key shape as `translations/en.json`. When adding or renaming a config-flow step, update every primary language and keep `tests/test_config_metadata.py` passing.
- Keep `strings.json` equal to the canonical English translation source. For child entities with `has_entity_name`, set `translation_key` but do not assign `_attr_name = None`: Home Assistant 2026.6 treats the mere presence of `_attr_name` as authoritative and otherwise suppresses the translated semantic suffix.

## Home Assistant deployment checks

- Treat deployment, restart, and publication as explicit boundaries: run local tests first, then back up the installed integration, deploy, compile inside the HA container, restart, and inspect logs from the new start.
- Never place backup directories inside `config/custom_components`. Home Assistant may discover names such as `tcl_udp_ac.backup-*` as Python modules and fail to import the integration. Store recoverable backups under `config/backups` or outside the HA config tree.
- Deploy only `custom_components/tcl_udp_ac`; exclude `__pycache__` and `.pyc` files.
- After restart, verify all five platforms (`binary_sensor`, `climate`, `number`, `switch`, and `sensor`) load and observe at least one completed coordinator refresh. Search specifically for `tcl_udp_ac`, authentication errors, `ERROR`, and tracebacks.
- Do not force a real token refresh merely to test deployment when the current token is healthy. Verify the fresh-token path in the live instance and cover refresh/rejection/concurrency branches with deterministic tests.
- A transient DNS or TCL cloud outage in logs is not evidence that reauthentication is required. Correlate the HTTP status and subsequent recovery before changing authentication behavior.
