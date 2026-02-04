"""Adds config flow for TCL UDP AC."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class TclUdpFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TCL UDP AC."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            # For UDP-based integration, we don't need credentials
            # Just create the entry
            await self.async_set_unique_id("tcl_udp_ac")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="TCL UDP Air Conditioner",
                data={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=_errors,
            description_placeholders={
                "description": (
                    "This integration will discover TCL AC units on your "
                    "network via UDP broadcast."
                ),
            },
        )
