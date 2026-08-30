"""Stable identity and presentation metadata for one TCL device."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_ACCOUNT,
    CONF_CLOUD_FROM,
    CONF_CLOUD_PRODUCT_KEY,
    CONF_CLOUD_TID,
    CONF_CLOUD_TO,
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PROTOCOL,
    CONF_DEVICE_ROOM,
)
from .protocol_driver import resolve_protocol_driver


@dataclass(frozen=True)
class DeviceDescriptor:
    """Describe one account device without coupling it to a config entry."""

    device_id: str
    category: str
    product_key: str | None = None
    master_id: str | None = None
    name: str | None = None
    room: str | None = None
    mac: str | None = None
    model: str | None = None
    protocol: str | None = None
    is_online: bool | None = None
    energy: bool = False

    @property
    def supports_legacy_cloud_control(self) -> bool:
        """Return whether this device uses the legacy XMPP cloud path."""
        return self.protocol in {None, "", "0"}

    @property
    def supports_cloud_control(self) -> bool:
        """Return whether the integration has a mapped cloud-control path."""
        if self.supports_legacy_cloud_control:
            return True
        profile = resolve_protocol_driver(self.device_id, product_key=self.product_key)
        return not profile.legacy_transport_enabled

    @property
    def cloud_from_jid(self) -> str | None:
        """Return the account sender JID for legacy cloud control."""
        if not self.master_id:
            return None
        return f"{self.master_id}@tcl.com/PH-android-zx01-2"

    @property
    def cloud_to_jid(self) -> str:
        """Return the device JID for legacy cloud control."""
        return f"{self.device_id}@tcl.com/AC-linux-zx01-1"

    @property
    def title(self) -> str:
        """Return a suggested config-entry title, not a registry rename."""
        parts = [self.name or self.model or self.device_id]
        if self.room:
            parts.append(self.room)
        return " - ".join(parts)

    @property
    def routing_identities(self) -> tuple[str, ...]:
        """Return all cloud-known identities usable by deterministic UDP routing."""
        return tuple(value for value in (self.device_id, self.mac) if value)

    def config_patch(self) -> dict[str, Any]:
        """Return device-scoped config data while preserving stable identifiers."""
        patch: dict[str, Any] = {
            CONF_CLOUD_TID: self.device_id,
            CONF_CLOUD_TO: self.cloud_to_jid,
        }
        optional = {
            CONF_CLOUD_FROM: self.cloud_from_jid,
            CONF_CLOUD_PRODUCT_KEY: self.product_key,
            CONF_ACCOUNT: self.master_id,
            CONF_DEVICE_MAC: self.mac,
            CONF_DEVICE_NAME: self.name,
            CONF_DEVICE_ROOM: self.room,
            CONF_DEVICE_MODEL: self.model,
            CONF_DEVICE_PROTOCOL: self.protocol,
        }
        patch.update(
            {key: value for key, value in optional.items() if value not in (None, "")}
        )
        return patch


# Compatibility name for callers that imported the account-client DTO directly.
TclCloudDevice = DeviceDescriptor
