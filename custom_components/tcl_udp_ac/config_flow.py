"""Adds config flow for TCL UDP AC."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .account_client import (
    AccountClient,
    TclAccountAuthError,
    TclAccountError,
    TclCloudDevice,
    TclTokens,
)
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

# Device fields collected after a successful login (tokens are auto-filled).
DEVICE_CONFIG_KEYS = (
    CONF_CLOUD_TID,
    CONF_CLOUD_FROM,
    CONF_CLOUD_TO,
    CONF_CLOUD_CONTROL,
    CONF_ENABLE_FAN_ONLY_MODE,
    CONF_ENABLE_AUTO_MODE,
)


def _schema_for_keys(
    keys: tuple[str, ...],
    values: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build a Home Assistant form schema for selected config keys."""
    source = values or DEFAULT_CONFIG_VALUES
    return vol.Schema(
        {
            vol.Optional(
                key, default=source.get(key, DEFAULT_CONFIG_VALUES[key])
            ): type(DEFAULT_CONFIG_VALUES[key])
            for key in keys
        }
    )


def _entry_values(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Return config entry values with options overriding initial data."""
    values = dict(DEFAULT_CONFIG_VALUES)
    values.update(getattr(entry, "data", {}))
    values.update(getattr(entry, "options", {}))
    return values


def _account_client(hass: Any, data: dict[str, Any]) -> AccountClient:
    """Build an AccountClient from config values (or defaults)."""
    session = async_get_clientsession(hass)
    return AccountClient(
        session,
        base_url=data.get(CONF_ACCOUNT_BASE_URL, DEFAULT_ACCOUNT_BASE_URL),
        app_id=data.get(CONF_ACCOUNT_APP_ID, DEFAULT_ACCOUNT_APP_ID),
        app_secret=data.get(CONF_ACCOUNT_APP_SECRET, DEFAULT_ACCOUNT_APP_SECRET),
        tenant_id=data.get(CONF_ACCOUNT_TENANT_ID, DEFAULT_ACCOUNT_TENANT_ID),
        cloud_base_url=data.get(CONF_CLOUD_BASE_URL, DEFAULT_CLOUD_BASE_URL),
    )


def _data_with_tokens(base: dict[str, Any], tokens: TclTokens) -> dict[str, Any]:
    """Merge login tokens into a config data dict."""
    data = dict(base)
    data[CONF_CLOUD_ENABLED] = True
    data[CONF_CLOUD_TOKEN] = tokens.access_token
    data[CONF_CLOUD_REFRESH_TOKEN] = tokens.refresh_token
    if tokens.account_id:
        data[CONF_CLOUD_ACCOUNT_ID] = tokens.account_id
    return data


def _device_label(device: TclCloudDevice) -> str:
    """Return the label shown in the discovered-device selector."""
    label = device.title
    details = []
    if device.device_id:
        details.append(device.device_id)
    if device.product_key:
        details.append(device.product_key)
    if device.protocol is not None:
        details.append(f"protocol {device.protocol}")
    if details:
        return f"{label} ({', '.join(details)})"
    return label


def _default_device_cloud_control(devices: list[TclCloudDevice]) -> bool:
    """Return a cautious cloud-control default for discovered devices."""
    if not devices:
        return DEFAULT_CLOUD_CONTROL
    return devices[0].supports_legacy_cloud_control


def _device_select_schema(devices: list[TclCloudDevice]) -> vol.Schema:
    """Build the post-login device selection schema."""
    choices = {device.device_id: _device_label(device) for device in devices}
    default_device = devices[0].device_id if devices else None
    return vol.Schema(
        {
            vol.Required(CONF_CLOUD_TID, default=default_device): vol.In(choices),
            vol.Optional(
                CONF_CLOUD_CONTROL, default=_default_device_cloud_control(devices)
            ): type(DEFAULT_CLOUD_CONTROL),
            vol.Optional(
                CONF_ENABLE_FAN_ONLY_MODE, default=DEFAULT_ENABLE_FAN_ONLY_MODE
            ): type(DEFAULT_ENABLE_FAN_ONLY_MODE),
            vol.Optional(
                CONF_ENABLE_AUTO_MODE, default=DEFAULT_ENABLE_AUTO_MODE
            ): type(DEFAULT_ENABLE_AUTO_MODE),
        }
    )


def _data_with_device(
    base: dict[str, Any],
    device: TclCloudDevice,
    user_input: dict[str, Any],
) -> dict[str, Any]:
    """Merge discovered device metadata into config data."""
    data = dict(base)
    data.update(user_input)
    data[CONF_CLOUD_TID] = device.device_id
    data[CONF_CLOUD_FROM] = device.cloud_from_jid or DEFAULT_CLOUD_FROM
    data[CONF_CLOUD_TO] = device.cloud_to_jid
    if device.master_id:
        data[CONF_ACCOUNT] = device.master_id
    return data


class TclUdpFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TCL UDP AC."""

    VERSION = 1
    _basic_user_input: dict[str, Any]
    _login_devices: list[TclCloudDevice]
    _login_tokens: TclTokens
    _sms_mobile: str

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return TclUdpOptionsFlowHandler()

    async def async_step_user(
        self,
        user_input: dict | None = None,  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:
        """Present a menu of login methods."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["login_password", "login_sms", "manual"],
        )

    async def async_step_login_password(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Log in with account and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            account = _account_client(self.hass, {})
            try:
                self._login_tokens = await account.async_login_password(
                    user_input["username"], user_input["password"]
                )
            except TclAccountAuthError:
                errors["base"] = "invalid_auth"
            except TclAccountError:
                errors["base"] = "cannot_connect"
            else:
                await self._async_load_login_devices(account)
                return await self.async_step_device()

        schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
            }
        )
        return self.async_show_form(
            step_id="login_password", data_schema=schema, errors=errors
        )

    async def async_step_login_sms(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Request an SMS code for the given mobile number."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._sms_mobile = user_input["mobile"]
            account = _account_client(self.hass, {})
            try:
                await account.async_request_sms_code(self._sms_mobile)
            except TclAccountError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_sms_code()

        schema = vol.Schema({vol.Required("mobile"): str})
        return self.async_show_form(
            step_id="login_sms", data_schema=schema, errors=errors
        )

    async def async_step_sms_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Submit the SMS code to complete login."""
        errors: dict[str, str] = {}
        if user_input is not None:
            account = _account_client(self.hass, {})
            try:
                self._login_tokens = await account.async_login_sms(
                    self._sms_mobile, user_input["code"]
                )
            except TclAccountAuthError:
                errors["base"] = "invalid_auth"
            except TclAccountError:
                errors["base"] = "cannot_connect"
            else:
                await self._async_load_login_devices(account)
                return await self.async_step_device()

        schema = vol.Schema({vol.Required("code"): str})
        return self.async_show_form(
            step_id="sms_code", data_schema=schema, errors=errors
        )

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect device fields after login; tokens are already obtained."""
        if user_input is not None:
            data = dict(DEFAULT_CONFIG_VALUES)
            devices = getattr(self, "_login_devices", [])
            selected_device = next(
                (
                    device
                    for device in devices
                    if device.device_id == user_input.get(CONF_CLOUD_TID)
                ),
                None,
            )
            if selected_device is not None:
                data = _data_with_device(data, selected_device, user_input)
            else:
                data.update(user_input)
            data = _data_with_tokens(data, self._login_tokens)
            unique_id = data.get(CONF_CLOUD_TID) or "tcl_udp_ac"
            await self.async_set_unique_id(str(unique_id))
            self._abort_if_unique_id_configured()
            title = (
                selected_device.title
                if selected_device is not None
                else "TCL UDP Air Conditioner"
            )
            return self.async_create_entry(title=title, data=data)

        devices = getattr(self, "_login_devices", [])
        if devices:
            return self.async_show_form(
                step_id="device",
                data_schema=_device_select_schema(devices),
                errors={},
            )

        return self.async_show_form(
            step_id="device",
            data_schema=_schema_for_keys(DEVICE_CONFIG_KEYS),
            errors={},
        )

    async def _async_load_login_devices(self, account: AccountClient) -> None:
        """Load account AC devices after a successful TCL+ login."""
        try:
            self._login_devices = await account.async_list_devices(
                self._login_tokens.access_token
            )
        except TclAccountError:
            # Device discovery is a convenience layer. Keep the login flow usable
            # by falling back to the manual TID/JID form.
            self._login_devices = []

    async def async_step_manual(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle manual token entry (original flow)."""
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
            step_id="manual",
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

    async def async_step_reauth(
        self,
        _entry_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication when the cloud token can no longer refresh."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Re-login with password and update the existing entry's tokens."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            account = _account_client(self.hass, dict(entry.data))
            try:
                tokens = await account.async_login_password(
                    user_input["username"], user_input["password"]
                )
            except TclAccountAuthError:
                errors["base"] = "invalid_auth"
            except TclAccountError:
                errors["base"] = "cannot_connect"
            else:
                new_data = _data_with_tokens(dict(entry.data), tokens)
                return self.async_update_reload_and_abort(entry, data=new_data)

        schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
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
