"""Privacy-safe diagnostics for TCL UDP AC config entries."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .config_settings import ConfigEntrySettings, entry_value
from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNT_APP_ID,
    CONF_ACCOUNT_APP_SECRET,
    CONF_ACCOUNT_TENANT_ID,
    CONF_ACTION_JID,
    CONF_CLOUD_ACCOUNT_ID,
    CONF_CLOUD_FROM,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_T_STORE_UUID,
    CONF_CLOUD_TID,
    CONF_CLOUD_TO,
    CONF_CLOUD_TOKEN,
    CONF_DEVICE_MAC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PROTOCOL,
    CONF_DEVICE_ROOM,
    CONF_ENABLE_AUTO_MODE,
    CONF_ENABLE_FAN_ONLY_MODE,
    DEFAULT_ENABLE_AUTO_MODE,
    DEFAULT_ENABLE_FAN_ONLY_MODE,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TclUdpConfigEntry

TO_REDACT = {
    CONF_ACCOUNT,
    CONF_ACCOUNT_APP_ID,
    CONF_ACCOUNT_APP_SECRET,
    CONF_ACCOUNT_TENANT_ID,
    CONF_ACTION_JID,
    CONF_CLOUD_ACCOUNT_ID,
    CONF_CLOUD_FROM,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_TID,
    CONF_CLOUD_TO,
    CONF_CLOUD_TOKEN,
    CONF_CLOUD_T_STORE_UUID,
    CONF_DEVICE_MAC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ROOM,
    "account_id",
    "access_token",
    "refresh_token",
    "device_id",
    "entry_id",
    "entity_id",
    "context_id",
    "jid",
    "mac",
    "name",
    "room",
    "tid",
    "token",
}


def _serializable(value: Any) -> Any:
    """Convert runtime values to Home Assistant diagnostics-safe primitives."""
    if isinstance(value, dict):
        return {str(key): _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serializable(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return type(value).__name__


def _call_reporter(owner: Any, method_name: str) -> Any:
    """Read an optional synchronous diagnostics snapshot method."""
    method = getattr(owner, method_name, None)
    return method() if method is not None else None


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: TclUdpConfigEntry,
) -> dict[str, Any]:
    """Return a redacted diagnostics snapshot for one physical AC."""
    runtime = entry.runtime_data
    settings = ConfigEntrySettings.from_entry(entry)
    profile = settings.profile
    capabilities = profile.capabilities
    coordinator = runtime.coordinator
    session = runtime.session

    last_exception = getattr(coordinator, "last_exception", None)
    refresh_token = entry_value(entry, CONF_CLOUD_REFRESH_TOKEN)
    report = {
        "integration": {
            "version": getattr(runtime.integration, "version", None),
            "coordinator_last_update_success": getattr(
                coordinator, "last_update_success", None
            ),
            "coordinator_last_exception_type": (
                type(last_exception).__name__ if last_exception is not None else None
            ),
        },
        "configuration": {
            "cloud_enabled": bool(settings.cloud_enabled),
            "cloud_control_enabled": bool(settings.cloud_control),
            "access_token_configured": bool(settings.cloud_token),
            "refresh_token_configured": bool(refresh_token),
            "manual_token_mode": bool(settings.cloud_token and not refresh_token),
            "device_protocol": entry_value(entry, CONF_DEVICE_PROTOCOL),
            "product_key": settings.cloud_product_key or None,
            "fan_only_mode_enabled": bool(
                entry_value(
                    entry,
                    CONF_ENABLE_FAN_ONLY_MODE,
                    DEFAULT_ENABLE_FAN_ONLY_MODE,
                )
            ),
            "auto_mode_enabled": bool(
                entry_value(
                    entry,
                    CONF_ENABLE_AUTO_MODE,
                    DEFAULT_ENABLE_AUTO_MODE,
                )
            ),
        },
        "protocol_profile": {
            "profile": profile.name,
            "local_transport_enabled": bool(
                getattr(profile, "local_transport_enabled", True)
            ),
            "legacy_transport_enabled": bool(profile.legacy_transport_enabled),
            "cloud_status_family": profile.cloud_status_family,
            "verified_hvac_modes": capabilities.verified_hvac_modes,
            "experimental_hvac_modes": capabilities.experimental_hvac_modes,
            "fan_modes": capabilities.fan_modes,
            "supports_fan_speed": capabilities.supports_fan_speed,
            "supports_swing": capabilities.supports_swing,
            "switches": tuple(capabilities.switches),
            "diagnostic_sensors": tuple(
                capability.data_key for capability in capabilities.diagnostic_sensors
            ),
            "binary_diagnostics": tuple(
                capability.data_key for capability in capabilities.binary_diagnostics
            ),
            "numbers": tuple(
                capability.data_key for capability in capabilities.numbers
            ),
        },
        "state": session.get_last_status(),
        "commands": {
            "pending": session.pending_command_confirmation(),
            "last_attempt": _call_reporter(session, "last_command_attempt"),
            "last_result": coordinator.last_command_result,
        },
    }
    return async_redact_data(_serializable(report), TO_REDACT)
