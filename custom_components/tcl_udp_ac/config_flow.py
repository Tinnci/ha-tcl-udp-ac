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
    DEFAULT_ACCOUNT,
    DEFAULT_ACTION_JID,
    DEFAULT_ACTION_SOURCE,
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
                }
            ),
        )
