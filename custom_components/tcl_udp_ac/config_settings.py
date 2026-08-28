"""Config entry settings for the TCL UDP AC integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNT_APP_ID,
    CONF_ACCOUNT_APP_SECRET,
    CONF_ACCOUNT_BASE_URL,
    CONF_ACCOUNT_TENANT_ID,
    CONF_ACTION_JID,
    CONF_ACTION_SOURCE,
    CONF_CLOUD_ACCEPT,
    CONF_CLOUD_ACCEPT_ENCODING,
    CONF_CLOUD_ACCEPT_LANGUAGE,
    CONF_CLOUD_ACCOUNT_ID,
    CONF_CLOUD_APP_BUILD_VERSION,
    CONF_CLOUD_APP_PACKAGE,
    CONF_CLOUD_APP_VERSION,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_BRAND,
    CONF_CLOUD_CHANNEL,
    CONF_CLOUD_CONTROL,
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_FROM,
    CONF_CLOUD_ORIGIN,
    CONF_CLOUD_PLATFORM,
    CONF_CLOUD_PRODUCT_KEY,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_SDK_VERSION,
    CONF_CLOUD_SYSTEM_VERSION,
    CONF_CLOUD_T_APP_VERSION,
    CONF_CLOUD_T_PLATFORM_TYPE,
    CONF_CLOUD_T_STORE_UUID,
    CONF_CLOUD_TID,
    CONF_CLOUD_TO,
    CONF_CLOUD_TOKEN,
    CONF_CLOUD_USER_AGENT,
    CONF_CLOUD_X_REQUESTED_WITH,
    CONF_DEVICE_MAC,
    CONF_ENABLE_AUTO_MODE,
    CONF_ENABLE_FAN_ONLY_MODE,
    DEFAULT_ACCOUNT,
    DEFAULT_ACCOUNT_APP_ID,
    DEFAULT_ACCOUNT_APP_SECRET,
    DEFAULT_ACCOUNT_BASE_URL,
    DEFAULT_ACCOUNT_TENANT_ID,
    DEFAULT_ACTION_JID,
    DEFAULT_ACTION_SOURCE,
    DEFAULT_CLOUD_ACCEPT,
    DEFAULT_CLOUD_ACCEPT_ENCODING,
    DEFAULT_CLOUD_ACCEPT_LANGUAGE,
    DEFAULT_CLOUD_APP_BUILD_VERSION,
    DEFAULT_CLOUD_APP_PACKAGE,
    DEFAULT_CLOUD_APP_VERSION,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_BRAND,
    DEFAULT_CLOUD_CHANNEL,
    DEFAULT_CLOUD_CONTROL,
    DEFAULT_CLOUD_ENABLED,
    DEFAULT_CLOUD_FROM,
    DEFAULT_CLOUD_ORIGIN,
    DEFAULT_CLOUD_PLATFORM,
    DEFAULT_CLOUD_SDK_VERSION,
    DEFAULT_CLOUD_SYSTEM_VERSION,
    DEFAULT_CLOUD_T_APP_VERSION,
    DEFAULT_CLOUD_T_PLATFORM_TYPE,
    DEFAULT_CLOUD_T_STORE_UUID,
    DEFAULT_CLOUD_TID,
    DEFAULT_CLOUD_TO,
    DEFAULT_CLOUD_TOKEN,
    DEFAULT_CLOUD_USER_AGENT,
    DEFAULT_CLOUD_X_REQUESTED_WITH,
    DEFAULT_ENABLE_AUTO_MODE,
    DEFAULT_ENABLE_FAN_ONLY_MODE,
)
from .protocol_driver import ProtocolDriver, resolve_protocol_driver
from .protocol_profiles import (
    DeviceCapabilities,
)

if TYPE_CHECKING:
    from .data import TclUdpConfigEntry


DEFAULT_CONFIG_VALUES: dict[str, Any] = {
    CONF_ACTION_JID: DEFAULT_ACTION_JID,
    CONF_ACTION_SOURCE: DEFAULT_ACTION_SOURCE,
    CONF_ACCOUNT: DEFAULT_ACCOUNT,
    CONF_CLOUD_ENABLED: DEFAULT_CLOUD_ENABLED,
    CONF_CLOUD_TID: DEFAULT_CLOUD_TID,
    CONF_CLOUD_TOKEN: DEFAULT_CLOUD_TOKEN,
    CONF_CLOUD_FROM: DEFAULT_CLOUD_FROM,
    CONF_CLOUD_TO: DEFAULT_CLOUD_TO,
    CONF_CLOUD_BASE_URL: DEFAULT_CLOUD_BASE_URL,
    CONF_CLOUD_CONTROL: DEFAULT_CLOUD_CONTROL,
    CONF_CLOUD_USER_AGENT: DEFAULT_CLOUD_USER_AGENT,
    CONF_CLOUD_PLATFORM: DEFAULT_CLOUD_PLATFORM,
    CONF_CLOUD_APP_PACKAGE: DEFAULT_CLOUD_APP_PACKAGE,
    CONF_CLOUD_SYSTEM_VERSION: DEFAULT_CLOUD_SYSTEM_VERSION,
    CONF_CLOUD_BRAND: DEFAULT_CLOUD_BRAND,
    CONF_CLOUD_APP_VERSION: DEFAULT_CLOUD_APP_VERSION,
    CONF_CLOUD_SDK_VERSION: DEFAULT_CLOUD_SDK_VERSION,
    CONF_CLOUD_CHANNEL: DEFAULT_CLOUD_CHANNEL,
    CONF_CLOUD_APP_BUILD_VERSION: DEFAULT_CLOUD_APP_BUILD_VERSION,
    CONF_CLOUD_T_APP_VERSION: DEFAULT_CLOUD_T_APP_VERSION,
    CONF_CLOUD_T_PLATFORM_TYPE: DEFAULT_CLOUD_T_PLATFORM_TYPE,
    CONF_CLOUD_T_STORE_UUID: DEFAULT_CLOUD_T_STORE_UUID,
    CONF_CLOUD_ORIGIN: DEFAULT_CLOUD_ORIGIN,
    CONF_CLOUD_X_REQUESTED_WITH: DEFAULT_CLOUD_X_REQUESTED_WITH,
    CONF_CLOUD_ACCEPT: DEFAULT_CLOUD_ACCEPT,
    CONF_CLOUD_ACCEPT_ENCODING: DEFAULT_CLOUD_ACCEPT_ENCODING,
    CONF_CLOUD_ACCEPT_LANGUAGE: DEFAULT_CLOUD_ACCEPT_LANGUAGE,
    CONF_ENABLE_FAN_ONLY_MODE: DEFAULT_ENABLE_FAN_ONLY_MODE,
    CONF_ENABLE_AUTO_MODE: DEFAULT_ENABLE_AUTO_MODE,
}

TOKEN_DATA_KEYS = {
    CONF_CLOUD_ACCOUNT_ID,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_TOKEN,
}


@dataclass(frozen=True)
class AuthSettings:
    """Effective TCL account request settings."""

    base_url: str
    app_id: str
    app_secret: str
    tenant_id: str
    cloud_base_url: str

    @classmethod
    def from_entry(cls, entry: TclUdpConfigEntry) -> AuthSettings:
        """Resolve settings using the same data/options precedence as runtime."""
        return cls(
            base_url=entry_value(
                entry, CONF_ACCOUNT_BASE_URL, DEFAULT_ACCOUNT_BASE_URL
            ),
            app_id=entry_value(entry, CONF_ACCOUNT_APP_ID, DEFAULT_ACCOUNT_APP_ID),
            app_secret=entry_value(
                entry, CONF_ACCOUNT_APP_SECRET, DEFAULT_ACCOUNT_APP_SECRET
            ),
            tenant_id=entry_value(
                entry, CONF_ACCOUNT_TENANT_ID, DEFAULT_ACCOUNT_TENANT_ID
            ),
            cloud_base_url=entry_value(
                entry, CONF_CLOUD_BASE_URL, DEFAULT_CLOUD_BASE_URL
            ),
        )

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> AuthSettings:
        """Resolve settings for config flows before a config entry exists."""
        return cls(
            base_url=data.get(CONF_ACCOUNT_BASE_URL, DEFAULT_ACCOUNT_BASE_URL),
            app_id=data.get(CONF_ACCOUNT_APP_ID, DEFAULT_ACCOUNT_APP_ID),
            app_secret=data.get(CONF_ACCOUNT_APP_SECRET, DEFAULT_ACCOUNT_APP_SECRET),
            tenant_id=data.get(CONF_ACCOUNT_TENANT_ID, DEFAULT_ACCOUNT_TENANT_ID),
            cloud_base_url=data.get(CONF_CLOUD_BASE_URL, DEFAULT_CLOUD_BASE_URL),
        )


def entry_value(
    entry: TclUdpConfigEntry,
    key: str,
    default: Any = None,
    *,
    data_first: bool | None = None,
) -> Any:
    """Return a config entry value using the integration's precedence rules."""
    data = getattr(entry, "data", {}) or {}
    options = getattr(entry, "options", {}) or {}
    prefer_data = key in TOKEN_DATA_KEYS if data_first is None else data_first
    if prefer_data:
        return data.get(key, options.get(key, default))
    return options.get(key, data.get(key, default))


def entry_values(entry: TclUdpConfigEntry) -> dict[str, Any]:
    """Return defaulted config entry values with options overriding data."""
    values = dict(DEFAULT_CONFIG_VALUES)
    data = getattr(entry, "data", {}) or {}
    options = getattr(entry, "options", {}) or {}
    values.update(data)
    values.update(options)
    for key in TOKEN_DATA_KEYS:
        if key in data:
            values[key] = data[key]
    return values


def reload_signature(entry: TclUdpConfigEntry) -> tuple[tuple[str, str], ...]:
    """Return effective non-credential settings that require runtime reload."""
    values = entry_values(entry)
    return tuple(
        sorted(
            (key, repr(value))
            for key, value in values.items()
            if key not in TOKEN_DATA_KEYS
        )
    )


def profile_for_entry(entry: TclUdpConfigEntry) -> ProtocolDriver:
    """Resolve the protocol profile for a config entry."""
    device_id = entry_value(entry, CONF_CLOUD_TID, DEFAULT_CLOUD_TID)
    product_key = entry_value(entry, CONF_CLOUD_PRODUCT_KEY, "")
    return resolve_protocol_driver(device_id, product_key=product_key)


def capabilities_for_entry(entry: TclUdpConfigEntry) -> DeviceCapabilities:
    """Return the protocol capabilities for a config entry."""
    return profile_for_entry(entry).capabilities


@dataclass(frozen=True)
class ConfigEntrySettings:
    """Effective config entry settings used to build the runtime client."""

    action_jid: str
    action_source: str
    account: str
    cloud_enabled: bool
    cloud_tid: str
    cloud_token: str
    cloud_from: str
    cloud_to: str
    cloud_base_url: str
    cloud_product_key: str
    cloud_control: bool
    cloud_user_agent: str
    cloud_platform: str
    cloud_app_package: str
    cloud_system_version: str
    cloud_brand: str
    cloud_app_version: str
    cloud_sdk_version: str
    cloud_channel: str
    cloud_app_build_version: str
    cloud_t_app_version: str
    cloud_t_platform_type: str
    cloud_t_store_uuid: str
    cloud_origin: str
    cloud_x_requested_with: str
    cloud_accept: str
    cloud_accept_encoding: str
    cloud_accept_language: str
    device_mac: str

    @classmethod
    def from_entry(cls, entry: TclUdpConfigEntry) -> ConfigEntrySettings:
        """Build effective settings from a config entry."""
        return cls(
            action_jid=entry_value(entry, CONF_ACTION_JID, DEFAULT_ACTION_JID),
            action_source=entry_value(entry, CONF_ACTION_SOURCE, DEFAULT_ACTION_SOURCE),
            account=entry_value(entry, CONF_ACCOUNT, DEFAULT_ACCOUNT),
            cloud_enabled=entry_value(entry, CONF_CLOUD_ENABLED, DEFAULT_CLOUD_ENABLED),
            cloud_tid=entry_value(entry, CONF_CLOUD_TID, DEFAULT_CLOUD_TID),
            cloud_token=entry_value(entry, CONF_CLOUD_TOKEN, DEFAULT_CLOUD_TOKEN),
            cloud_from=entry_value(entry, CONF_CLOUD_FROM, DEFAULT_CLOUD_FROM),
            cloud_to=entry_value(entry, CONF_CLOUD_TO, DEFAULT_CLOUD_TO),
            cloud_base_url=entry_value(
                entry, CONF_CLOUD_BASE_URL, DEFAULT_CLOUD_BASE_URL
            ),
            cloud_product_key=entry_value(entry, CONF_CLOUD_PRODUCT_KEY, ""),
            cloud_control=entry_value(entry, CONF_CLOUD_CONTROL, DEFAULT_CLOUD_CONTROL),
            cloud_user_agent=entry_value(
                entry, CONF_CLOUD_USER_AGENT, DEFAULT_CLOUD_USER_AGENT
            ),
            cloud_platform=entry_value(
                entry, CONF_CLOUD_PLATFORM, DEFAULT_CLOUD_PLATFORM
            ),
            cloud_app_package=entry_value(
                entry, CONF_CLOUD_APP_PACKAGE, DEFAULT_CLOUD_APP_PACKAGE
            ),
            cloud_system_version=entry_value(
                entry, CONF_CLOUD_SYSTEM_VERSION, DEFAULT_CLOUD_SYSTEM_VERSION
            ),
            cloud_brand=entry_value(entry, CONF_CLOUD_BRAND, DEFAULT_CLOUD_BRAND),
            cloud_app_version=entry_value(
                entry, CONF_CLOUD_APP_VERSION, DEFAULT_CLOUD_APP_VERSION
            ),
            cloud_sdk_version=entry_value(
                entry, CONF_CLOUD_SDK_VERSION, DEFAULT_CLOUD_SDK_VERSION
            ),
            cloud_channel=entry_value(entry, CONF_CLOUD_CHANNEL, DEFAULT_CLOUD_CHANNEL),
            cloud_app_build_version=entry_value(
                entry, CONF_CLOUD_APP_BUILD_VERSION, DEFAULT_CLOUD_APP_BUILD_VERSION
            ),
            cloud_t_app_version=entry_value(
                entry, CONF_CLOUD_T_APP_VERSION, DEFAULT_CLOUD_T_APP_VERSION
            ),
            cloud_t_platform_type=entry_value(
                entry, CONF_CLOUD_T_PLATFORM_TYPE, DEFAULT_CLOUD_T_PLATFORM_TYPE
            ),
            cloud_t_store_uuid=entry_value(
                entry, CONF_CLOUD_T_STORE_UUID, DEFAULT_CLOUD_T_STORE_UUID
            ),
            cloud_origin=entry_value(entry, CONF_CLOUD_ORIGIN, DEFAULT_CLOUD_ORIGIN),
            cloud_x_requested_with=entry_value(
                entry, CONF_CLOUD_X_REQUESTED_WITH, DEFAULT_CLOUD_X_REQUESTED_WITH
            ),
            cloud_accept=entry_value(entry, CONF_CLOUD_ACCEPT, DEFAULT_CLOUD_ACCEPT),
            cloud_accept_encoding=entry_value(
                entry, CONF_CLOUD_ACCEPT_ENCODING, DEFAULT_CLOUD_ACCEPT_ENCODING
            ),
            cloud_accept_language=entry_value(
                entry, CONF_CLOUD_ACCEPT_LANGUAGE, DEFAULT_CLOUD_ACCEPT_LANGUAGE
            ),
            device_mac=entry_value(entry, CONF_DEVICE_MAC, ""),
        )

    @property
    def profile(self) -> ProtocolDriver:
        """Return the protocol profile for these settings."""
        return resolve_protocol_driver(
            self.cloud_tid,
            product_key=self.cloud_product_key,
        )

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return protocol capabilities for these settings."""
        return self.profile.capabilities

    def api_client_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments for TclUdpApiClient."""
        return {
            "action_jid": self.action_jid,
            "action_source": self.action_source,
            "account": self.account,
            "cloud_enabled": self.cloud_enabled,
            "cloud_tid": self.cloud_tid,
            "cloud_token": self.cloud_token,
            "cloud_from": self.cloud_from,
            "cloud_to": self.cloud_to,
            "cloud_base_url": self.cloud_base_url,
            "cloud_product_key": self.cloud_product_key,
            "cloud_user_id": self.account,
            "cloud_control": self.cloud_control,
            "cloud_user_agent": self.cloud_user_agent,
            "cloud_platform": self.cloud_platform,
            "cloud_app_package": self.cloud_app_package,
            "cloud_system_version": self.cloud_system_version,
            "cloud_brand": self.cloud_brand,
            "cloud_app_version": self.cloud_app_version,
            "cloud_sdk_version": self.cloud_sdk_version,
            "cloud_channel": self.cloud_channel,
            "cloud_app_build_version": self.cloud_app_build_version,
            "cloud_t_app_version": self.cloud_t_app_version,
            "cloud_t_platform_type": self.cloud_t_platform_type,
            "cloud_t_store_uuid": self.cloud_t_store_uuid,
            "cloud_origin": self.cloud_origin,
            "cloud_x_requested_with": self.cloud_x_requested_with,
            "cloud_accept": self.cloud_accept,
            "cloud_accept_encoding": self.cloud_accept_encoding,
            "cloud_accept_language": self.cloud_accept_language,
            "device_mac": self.device_mac,
        }
