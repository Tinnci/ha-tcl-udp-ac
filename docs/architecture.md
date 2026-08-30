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
- local UDP remains the primary state/control path for legacy devices;
- cloud status and control remain optional fallbacks;
- protocol 1 devices explicitly use cloud-only TSL status and property control.

The stored descriptor fields (`device_mac`, `device_name`, `device_room`,
`device_model`, and `device_protocol`) are additive. Existing identifiers do not
change: the cloud TID remains the config-entry unique ID and the prefix of every
entity unique ID. Presentation metadata supplies suggested names, models, and
areas; it does not overwrite names customized in Home Assistant.

## Runtime modules and seams

```text
TCL+ account API ---> AccountDeviceInventory ---> DeviceDescriptor
                                                     |
                                                     v
Home Assistant entities ---> DeviceSession (one per config entry/device)
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

### DeviceDescriptor and AccountDeviceInventory

`DeviceDescriptor` is the semantic Module for one discovered AC. Its Interface
separates stable identity (TID, MAC, product/protocol metadata) from suggested
presentation (name, room, model) and derives the device-scoped config patch.
It does not contain credentials or Home Assistant lifecycle behavior.

`AccountDeviceInventory` is an account snapshot, not another config-entry
type. Its `available_devices` Interface subtracts the stable TIDs already
configured for that account. `AccountDeviceCatalog` is the Adapter to the TCL+
API and always calls through the loaded source entry's `TokenManager` Seam, so
inventory discovery follows the same proactive refresh and single auth-retry
rules as every other authorized cloud request.

Choosing “add from existing account” creates another ordinary per-device entry.
Account credentials and effective request settings are copied, device-scoped
fields are replaced from the selected descriptor, and `CredentialManager`
continues to synchronize future rotations across entries sharing the account
ID. This gives the account inventory Leverage without weakening per-device
state and command Locality.

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

The protocol 1 driver is a deep Module: entities submit mode, fan, swing,
feature, or numeric intents without knowing TSL identifiers or endpoints. The
driver compiles those intents into property bundles with an expected state
projection. The same capability description creates product-specific switches,
numbers, and diagnostics, keeping product knowledge local to one Interface.

Protocol 1 sets `local_transport_enabled=False`. The compatibility transport
facade makes listener startup, discovery, and local status requests no-ops for
that profile, while the coordinator continues to use the same Interface and
polls `POST /v1/thing/status`. Legacy drivers continue using the shared UDP
hub and optional cloud fallback.

### UdpHub

One domain-wide `UdpHub` owns the listener and send sockets. Device channels
subscribe with both their cloud TID and MAC when available. Routing uses:

1. packet identity matched against the descriptor's TID/MAC identity set;
2. a previously bound source IP for identity-free replies;
3. first-device binding only when the hub has exactly one subscription and it
   has no known identity.

Packet identity always wins over a stale IP binding. If an identity matches
multiple subscriptions, or an unknown subscription coexists with any other
device, the hub logs and drops the unmatched packet rather than mixing device
state. This Depth keeps ambiguity handling inside the transport Module rather
than leaking it into entities or coordinators.

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
