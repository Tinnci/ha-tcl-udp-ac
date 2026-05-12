"""Adds config flow for TCL UDP AC."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ACCOUNT,
    CONF_ACTION_JID,
    CONF_ACTION_SOURCE,
    CONF_CLOUD_ACCEPT,
    CONF_CLOUD_ACCEPT_ENCODING,
    CONF_CLOUD_ACCEPT_LANGUAGE,
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
    CONF_ENABLE_AUTO_MODE,
    CONF_ENABLE_FAN_ONLY_MODE,
    DEFAULT_ACCOUNT,
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
    DOMAIN,
)

DEFAULT_CONFIG_VALUES = {
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

BASIC_CONFIG_KEYS = (
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_TID,
    CONF_CLOUD_TOKEN,
    CONF_CLOUD_CONTROL,
    CONF_ENABLE_FAN_ONLY_MODE,
    CONF_ENABLE_AUTO_MODE,
)
ADVANCED_CONFIG_KEYS = tuple(
    key for key in DEFAULT_CONFIG_VALUES if key not in BASIC_CONFIG_KEYS
)


def _schema_for_keys(
    keys: tuple[str, ...],
    values: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build a Home Assistant form schema for selected config keys."""
    source = values or DEFAULT_CONFIG_VALUES
    return vol.Schema(
        {
            vol.Optional(key, default=source.get(key, DEFAULT_CONFIG_VALUES[key])): type(
                DEFAULT_CONFIG_VALUES[key]
            )
            for key in keys
        }
    )


def _entry_values(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Return config entry values with options overriding initial data."""
    values = dict(DEFAULT_CONFIG_VALUES)
    values.update(getattr(entry, "data", {}))
    values.update(getattr(entry, "options", {}))
    return values


class TclUdpFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TCL UDP AC."""

    VERSION = 1
    _basic_user_input: dict[str, Any]

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return TclUdpOptionsFlowHandler()

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._basic_user_input = dict(user_input)
            if getattr(self, "show_advanced_options", False):
                return await self.async_step_advanced()

            data = dict(DEFAULT_CONFIG_VALUES)
            data.update(user_input)
            unique_id = data.get(CONF_CLOUD_TID) or "tcl_udp_ac"
            await self.async_set_unique_id(str(unique_id))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="TCL UDP Air Conditioner",
                data=data,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema_for_keys(BASIC_CONFIG_KEYS),
            errors=errors,
        )

    async def async_step_advanced(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle advanced setup fields for captured app/cloud headers."""
        if user_input is not None:
            data = dict(DEFAULT_CONFIG_VALUES)
            data.update(getattr(self, "_basic_user_input", {}))
            data.update(user_input)
            unique_id = data.get(CONF_CLOUD_TID) or "tcl_udp_ac"
            await self.async_set_unique_id(str(unique_id))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="TCL UDP Air Conditioner",
                data=data,
            )

        return self.async_show_form(
            step_id="advanced",
            data_schema=_schema_for_keys(ADVANCED_CONFIG_KEYS),
            errors={},
        )


class TclUdpOptionsFlowHandler(config_entries.OptionsFlow):
    """Tcl UDP Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        values = _entry_values(self.config_entry)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema_for_keys(tuple(DEFAULT_CONFIG_VALUES), values),
        )
