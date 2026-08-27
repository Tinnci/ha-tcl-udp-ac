# Runtime Architecture

This integration uses a modular, in-repository runtime. Home Assistant remains
the lifecycle owner, while device state, command confirmation, protocol
selection, and UDP socket ownership live behind explicit seams.

## Compatibility invariants

Architecture changes must preserve these user-facing contracts:

- existing config-entry keys remain readable;
- existing device and entity unique IDs do not change;
- `tcl_udp_ac_command_result` remains the command result event;
- the existing Repairs translation and issue behavior remain available;
- local UDP remains the primary state/control path;
- cloud status and control remain optional fallbacks;
- unsupported TSL writes remain disabled rather than guessed.

The stored `device_mac` key is additive and internal. TCL+ device discovery
persists it when available so the shared UDP hub can route packets without
guessing. Existing single-device entries without a MAC continue to bind the
first unambiguous local device. Multiple unknown entries deliberately reject an
ambiguous packet instead of allowing state from one AC to appear on another.

## Runtime modules and seams

```text
Home Assistant entities
        |
        v
DeviceSession (one per config entry/device)
        |-- StateReducer / DeviceState
        |-- CommandTracker
        |-- ProtocolDriver
        |-- TclUdpApiClient compatibility transport facade
                 |-- CloudClient
                 `-- UdpClient channel
                           |
                           v
                  UdpHub (one per HA instance)
```

### DeviceSession

`DeviceSession` is the Home Assistant-facing device module. Its interface keeps
state reconciliation, command registration, and confirmation identity local to
one config entry. Transport adapters return an immutable `CommandReceipt`
directly; the session records it only when at least one transport accepted the
command. There is no shared pending slot between concurrent commands.

Cloud and UDP delivery are not presented as an atomic operation. A receipt
records each attempt as accepted, rejected, skipped, or failed. For example, a
cloud-accepted command remains eligible for status confirmation if its UDP
attempt subsequently fails.

### StateReducer

State is reconciled per field rather than with an unqualified `dict.update()`.
Each observation records its source and monotonic receipt time. Newer values
replace older values, UDP wins equal-time ties, and a cloud fallback cannot
replace a UDP field received in the preceding 90 seconds. Partial updates do
not clear fields they omit.

UDP callbacks contain only fields parsed from the current packet. This prevents
previous cloud values held in the compatibility client's cache from being
misclassified as fresh local observations.

Integration-derived observations are accepted only for `energy_statistics`.
They cannot overwrite device control fields such as power, mode, or target
temperature.

### CommandTracker

Every accepted session command receives a stable per-session `command_id`.
`CommandTracker` stores the receipt and its transport outcome with the expected
status. The coordinator confirms and clears that exact command, so concurrent
requests do not overwrite each other. Status matching establishes the observed
final state, not causality, because the device protocols do not return a command
transaction identifier. Repairs issue identifiers include the config-entry ID,
so one device cannot clear another device's warning.

### ProtocolDriver

The ordered driver registry resolves devices from `deviceId` and `productKey`.
A driver defines capabilities, command compilation, transport family, status
family, and device-specific mode normalization. Existing protocol profile
classes satisfy this interface; `resolve_protocol_profile()` remains as a
compatibility alias.

### UdpHub

One domain-wide `UdpHub` owns the listener and send sockets. Device channels
subscribe with an expected MAC when TCL+ discovery provides it. Routing uses:

1. packet identity/MAC when present;
2. a previously bound source IP for identity-free replies;
3. first-device binding only when exactly one subscription is unknown.

Packet identity always wins over a stale IP binding. If more than one unknown
subscription could receive a packet, the hub logs and drops it rather than
mixing device state.

## Extension path

Adding a confirmed device family should require:

1. a driver implementation or profile satisfying `ProtocolDriver`;
2. a registry rule using stable device/product metadata;
3. capture-backed command and parser tests;
4. explicit capabilities that hide unconfirmed writes;
5. replay tests proving status normalization and command expectations.

An external protocol package is intentionally deferred until another consumer
needs it. The current boundaries allow that extraction later without imposing
cross-repository release management now.
