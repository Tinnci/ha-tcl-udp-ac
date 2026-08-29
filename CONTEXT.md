# Domain Language

## Device Descriptor

A `DeviceDescriptor` is the current TCL+ description of exactly one physical
AC. The cloud TID is its stable integration identity. MAC and product/protocol
metadata refine routing and protocol selection. Name, room, and model are
presentation suggestions and never replace Home Assistant's stable entity IDs.

## Account Device Inventory

An `AccountDeviceInventory` is a current account snapshot of device
descriptors plus the set of TIDs already represented by config entries. It is
not a runtime owner and is not persisted as a separate account config entry.
Its purpose is to discover devices that can be enrolled.

## Device Enrollment

Enrollment turns one available descriptor into one ordinary device config
entry. It reuses the selected account's credential lifecycle and request
settings, replaces device-specific fields, and preserves the invariant that
state, commands, entities, and reloads are local to one device entry.

## Local Device Identity

UDP packets may identify the same AC by cloud TID or MAC. A device subscription
therefore owns a normalized identity set. Source IP is only a learned route for
identity-free replies; it cannot override an explicit packet identity.
