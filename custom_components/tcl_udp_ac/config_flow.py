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
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_CONTROL,
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_ACCEPT,
    CONF_CLOUD_ACCEPT_ENCODING,
    CONF_CLOUD_ACCEPT_LANGUAGE,
    CONF_CLOUD_APP_BUILD_VERSION,
    CONF_CLOUD_APP_PACKAGE,
    CONF_CLOUD_APP_VERSION,
    CONF_CLOUD_BRAND,
    CONF_CLOUD_CHANNEL,
    CONF_CLOUD_FROM,
    CONF_CLOUD_ORIGIN,
    CONF_CLOUD_PLATFORM,
    CONF_CLOUD_SDK_VERSION,
    CONF_CLOUD_SYSTEM_VERSION,
    CONF_CLOUD_T_APP_VERSION,
    CONF_CLOUD_T_PLATFORM_TYPE,
    CONF_CLOUD_T_STORE_UUID,
    CONF_CLOUD_TID,
    CONF_CLOUD_TOKEN,
    CONF_CLOUD_TO,
    CONF_CLOUD_USER_AGENT,
    CONF_CLOUD_X_REQUESTED_WITH,
    DEFAULT_ACCOUNT,
    DEFAULT_ACTION_JID,
    DEFAULT_ACTION_SOURCE,
    DEFAULT_CLOUD_ACCEPT,
    DEFAULT_CLOUD_ACCEPT_ENCODING,
    DEFAULT_CLOUD_ACCEPT_LANGUAGE,
    DEFAULT_CLOUD_APP_BUILD_VERSION,
    DEFAULT_CLOUD_APP_PACKAGE,
    DEFAULT_CLOUD_APP_VERSION,
    DEFAULT_CLOUD_BRAND,
    DEFAULT_CLOUD_CHANNEL,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_CONTROL,
    DEFAULT_CLOUD_ENABLED,
    DEFAULT_CLOUD_ORIGIN,
    DEFAULT_CLOUD_PLATFORM,
    DEFAULT_CLOUD_SDK_VERSION,
    DEFAULT_CLOUD_SYSTEM_VERSION,
    DEFAULT_CLOUD_T_APP_VERSION,
    DEFAULT_CLOUD_T_PLATFORM_TYPE,
    DEFAULT_CLOUD_TID,
    DEFAULT_CLOUD_TOKEN,
    DEFAULT_CLOUD_FROM,
    DEFAULT_CLOUD_TO,
    DEFAULT_CLOUD_T_STORE_UUID,
    DEFAULT_CLOUD_USER_AGENT,
    DEFAULT_CLOUD_X_REQUESTED_WITH,
    DOMAIN,
)


class TclUdpFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TCL UDP AC."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
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
            await self.async_set_unique_id("tcl_udp_ac")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="TCL UDP Air Conditioner",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ACTION_JID, default=DEFAULT_ACTION_JID): str,
                    vol.Optional(
                        CONF_ACTION_SOURCE, default=DEFAULT_ACTION_SOURCE
                    ): str,
                    vol.Optional(CONF_ACCOUNT, default=DEFAULT_ACCOUNT): str,
                    vol.Optional(
                        CONF_CLOUD_ENABLED, default=DEFAULT_CLOUD_ENABLED
                    ): bool,
                    vol.Optional(CONF_CLOUD_TID, default=DEFAULT_CLOUD_TID): str,
                    vol.Optional(
                        CONF_CLOUD_TOKEN, default=DEFAULT_CLOUD_TOKEN
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_FROM, default=DEFAULT_CLOUD_FROM
                    ): str,
                    vol.Optional(CONF_CLOUD_TO, default=DEFAULT_CLOUD_TO): str,
                    vol.Optional(
                        CONF_CLOUD_BASE_URL, default=DEFAULT_CLOUD_BASE_URL
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_CONTROL, default=DEFAULT_CLOUD_CONTROL
                    ): bool,
                    vol.Optional(
                        CONF_CLOUD_USER_AGENT, default=DEFAULT_CLOUD_USER_AGENT
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_PLATFORM, default=DEFAULT_CLOUD_PLATFORM
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_APP_PACKAGE, default=DEFAULT_CLOUD_APP_PACKAGE
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_SYSTEM_VERSION,
                        default=DEFAULT_CLOUD_SYSTEM_VERSION,
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_BRAND, default=DEFAULT_CLOUD_BRAND
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_APP_VERSION, default=DEFAULT_CLOUD_APP_VERSION
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_SDK_VERSION, default=DEFAULT_CLOUD_SDK_VERSION
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_CHANNEL, default=DEFAULT_CLOUD_CHANNEL
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_APP_BUILD_VERSION,
                        default=DEFAULT_CLOUD_APP_BUILD_VERSION,
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_T_APP_VERSION, default=DEFAULT_CLOUD_T_APP_VERSION
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_T_PLATFORM_TYPE,
                        default=DEFAULT_CLOUD_T_PLATFORM_TYPE,
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_T_STORE_UUID, default=DEFAULT_CLOUD_T_STORE_UUID
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ORIGIN, default=DEFAULT_CLOUD_ORIGIN
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_X_REQUESTED_WITH,
                        default=DEFAULT_CLOUD_X_REQUESTED_WITH,
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ACCEPT, default=DEFAULT_CLOUD_ACCEPT
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ACCEPT_ENCODING,
                        default=DEFAULT_CLOUD_ACCEPT_ENCODING,
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ACCEPT_LANGUAGE,
                        default=DEFAULT_CLOUD_ACCEPT_LANGUAGE,
                    ): str,
                }
            ),
            errors=errors,
        )


class TclUdpOptionsFlowHandler(config_entries.OptionsFlow):
    """Tcl UDP Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ACTION_JID,
                        default=self.config_entry.options.get(
                            CONF_ACTION_JID,
                            self.config_entry.data.get(
                                CONF_ACTION_JID, DEFAULT_ACTION_JID
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_ACTION_SOURCE,
                        default=self.config_entry.options.get(
                            CONF_ACTION_SOURCE,
                            self.config_entry.data.get(
                                CONF_ACTION_SOURCE, DEFAULT_ACTION_SOURCE
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_ACCOUNT,
                        default=self.config_entry.options.get(
                            CONF_ACCOUNT,
                            self.config_entry.data.get(CONF_ACCOUNT, DEFAULT_ACCOUNT),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ENABLED,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_ENABLED,
                            self.config_entry.data.get(
                                CONF_CLOUD_ENABLED, DEFAULT_CLOUD_ENABLED
                            ),
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_CLOUD_TID,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_TID,
                            self.config_entry.data.get(
                                CONF_CLOUD_TID, DEFAULT_CLOUD_TID
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_TOKEN,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_TOKEN,
                            self.config_entry.data.get(
                                CONF_CLOUD_TOKEN, DEFAULT_CLOUD_TOKEN
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_FROM,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_FROM,
                            self.config_entry.data.get(
                                CONF_CLOUD_FROM, DEFAULT_CLOUD_FROM
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_TO,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_TO,
                            self.config_entry.data.get(
                                CONF_CLOUD_TO, DEFAULT_CLOUD_TO
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_BASE_URL,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_BASE_URL,
                            self.config_entry.data.get(
                                CONF_CLOUD_BASE_URL, DEFAULT_CLOUD_BASE_URL
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_CONTROL,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_CONTROL,
                            self.config_entry.data.get(
                                CONF_CLOUD_CONTROL, DEFAULT_CLOUD_CONTROL
                            ),
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_CLOUD_USER_AGENT,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_USER_AGENT,
                            self.config_entry.data.get(
                                CONF_CLOUD_USER_AGENT, DEFAULT_CLOUD_USER_AGENT
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_PLATFORM,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_PLATFORM,
                            self.config_entry.data.get(
                                CONF_CLOUD_PLATFORM, DEFAULT_CLOUD_PLATFORM
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_APP_PACKAGE,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_APP_PACKAGE,
                            self.config_entry.data.get(
                                CONF_CLOUD_APP_PACKAGE, DEFAULT_CLOUD_APP_PACKAGE
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_SYSTEM_VERSION,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_SYSTEM_VERSION,
                            self.config_entry.data.get(
                                CONF_CLOUD_SYSTEM_VERSION,
                                DEFAULT_CLOUD_SYSTEM_VERSION,
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_BRAND,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_BRAND,
                            self.config_entry.data.get(
                                CONF_CLOUD_BRAND, DEFAULT_CLOUD_BRAND
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_APP_VERSION,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_APP_VERSION,
                            self.config_entry.data.get(
                                CONF_CLOUD_APP_VERSION, DEFAULT_CLOUD_APP_VERSION
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_SDK_VERSION,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_SDK_VERSION,
                            self.config_entry.data.get(
                                CONF_CLOUD_SDK_VERSION, DEFAULT_CLOUD_SDK_VERSION
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_CHANNEL,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_CHANNEL,
                            self.config_entry.data.get(
                                CONF_CLOUD_CHANNEL, DEFAULT_CLOUD_CHANNEL
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_APP_BUILD_VERSION,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_APP_BUILD_VERSION,
                            self.config_entry.data.get(
                                CONF_CLOUD_APP_BUILD_VERSION,
                                DEFAULT_CLOUD_APP_BUILD_VERSION,
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_T_APP_VERSION,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_T_APP_VERSION,
                            self.config_entry.data.get(
                                CONF_CLOUD_T_APP_VERSION, DEFAULT_CLOUD_T_APP_VERSION
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_T_PLATFORM_TYPE,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_T_PLATFORM_TYPE,
                            self.config_entry.data.get(
                                CONF_CLOUD_T_PLATFORM_TYPE,
                                DEFAULT_CLOUD_T_PLATFORM_TYPE,
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_T_STORE_UUID,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_T_STORE_UUID,
                            self.config_entry.data.get(
                                CONF_CLOUD_T_STORE_UUID, DEFAULT_CLOUD_T_STORE_UUID
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ORIGIN,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_ORIGIN,
                            self.config_entry.data.get(
                                CONF_CLOUD_ORIGIN, DEFAULT_CLOUD_ORIGIN
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_X_REQUESTED_WITH,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_X_REQUESTED_WITH,
                            self.config_entry.data.get(
                                CONF_CLOUD_X_REQUESTED_WITH,
                                DEFAULT_CLOUD_X_REQUESTED_WITH,
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ACCEPT,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_ACCEPT,
                            self.config_entry.data.get(
                                CONF_CLOUD_ACCEPT, DEFAULT_CLOUD_ACCEPT
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ACCEPT_ENCODING,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_ACCEPT_ENCODING,
                            self.config_entry.data.get(
                                CONF_CLOUD_ACCEPT_ENCODING,
                                DEFAULT_CLOUD_ACCEPT_ENCODING,
                            ),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_ACCEPT_LANGUAGE,
                        default=self.config_entry.options.get(
                            CONF_CLOUD_ACCEPT_LANGUAGE,
                            self.config_entry.data.get(
                                CONF_CLOUD_ACCEPT_LANGUAGE,
                                DEFAULT_CLOUD_ACCEPT_LANGUAGE,
                            ),
                        ),
                    ): str,
                }
            ),
        )
