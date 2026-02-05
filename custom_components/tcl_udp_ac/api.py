"""UDP API Client for TCL Air Conditioner."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import (
    DEFAULT_CLOUD_ACCEPT,
    DEFAULT_CLOUD_ACCEPT_ENCODING,
    DEFAULT_CLOUD_ACCEPT_LANGUAGE,
    DEFAULT_CLOUD_APP_BUILD_VERSION,
    DEFAULT_CLOUD_APP_PACKAGE,
    DEFAULT_CLOUD_APP_VERSION,
    DEFAULT_CLOUD_BRAND,
    DEFAULT_CLOUD_CHANNEL,
    DEFAULT_CLOUD_ORIGIN,
    DEFAULT_CLOUD_PLATFORM,
    DEFAULT_CLOUD_SDK_VERSION,
    DEFAULT_CLOUD_SYSTEM_VERSION,
    DEFAULT_CLOUD_T_APP_VERSION,
    DEFAULT_CLOUD_T_PLATFORM_TYPE,
    DEFAULT_CLOUD_T_STORE_UUID,
    DEFAULT_CLOUD_USER_AGENT,
    DEFAULT_CLOUD_X_REQUESTED_WITH,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MIDDLE,
    LOGGER,
    MODE_AUTO,
    MODE_COOL,
    MODE_DEHUMI,
    MODE_FAN,
    MODE_HEAT,
)
from .log_utils import log_debug, log_info, log_warning
from .udp_client import UdpClient

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET


class TclUdpApiClientError(Exception):
    """Exception to indicate a general API error."""


class TclUdpApiClientCommunicationError(TclUdpApiClientError):
    """Exception to indicate a communication error."""


@dataclass(frozen=True)
class CloudHeaderProfile:
    """Cloud header profile to keep request headers consistent."""

    platform: str
    user_agent: str
    app_package: str
    system_version: str
    brand: str
    app_version: str
    sdk_version: str
    channel: str
    app_build_version: str
    t_app_version: str
    t_platform_type: str
    t_store_uuid: str
    origin: str
    x_requested_with: str
    accept: str
    accept_encoding: str
    accept_language: str

    @staticmethod
    def _add_header(headers: dict[str, str], name: str, value: str | None) -> None:
        if value is None:
            return
        value_str = str(value).strip()
        if not value_str:
            return
        headers[name] = value_str

    def build(
        self,
        token: str | None,
        *,
        include_token: bool = True,
        include_content_type: bool = False,
    ) -> dict[str, str]:
        """Build headers for cloud requests."""
        headers: dict[str, str] = {}

        self._add_header(headers, "platform", self.platform)
        self._add_header(headers, "user-agent", self.user_agent)
        self._add_header(headers, "apppackagename", self.app_package)
        self._add_header(headers, "systemversion", self.system_version)
        self._add_header(headers, "brand", self.brand)
        self._add_header(headers, "appversion", self.app_version)
        self._add_header(headers, "sdkversion", self.sdk_version)
        self._add_header(headers, "channel", self.channel)
        self._add_header(headers, "appbuildversion", self.app_build_version)
        self._add_header(headers, "t-app-version", self.t_app_version)
        self._add_header(headers, "t-platform-type", self.t_platform_type)
        self._add_header(headers, "t-store-uuid", self.t_store_uuid)
        self._add_header(headers, "origin", self.origin)
        self._add_header(headers, "x-requested-with", self.x_requested_with)
        self._add_header(headers, "accept", self.accept)
        self._add_header(headers, "accept-encoding", self.accept_encoding)
        self._add_header(headers, "accept-language", self.accept_language)

        if include_content_type:
            headers["content-type"] = "application/json; charset=UTF-8"
        if include_token and token:
            headers["accesstoken"] = token

        return headers


class CloudClient:
    """Cloud API client to isolate HTTP behavior from UDP logic."""

    _HALF_C_IN_F = 0.5 * 9 / 5

    def __init__(  # noqa: PLR0913
        self,
        session: aiohttp.ClientSession | None,
        *,
        enabled: bool,
        tid: str | None,
        token: str | None,
        from_jid: str | None,
        to_jid: str | None,
        base_url: str,
        control_enabled: bool,
        headers: CloudHeaderProfile,
    ) -> None:
        """Initialize the cloud API client."""
        self._session = session
        self._enabled = enabled
        self._tid = tid
        self._token = token
        self._from = from_jid
        self._to = to_jid
        self._base_url = base_url.rstrip("/")
        self._control_enabled = control_enabled
        self._headers = headers

    @property
    def status_enabled(self) -> bool:
        """Return True when status fetch is enabled and configured."""
        return bool(self._enabled and self._tid and self._session)

    @property
    def control_enabled(self) -> bool:
        """Return True when cloud control is enabled and configured."""
        return bool(
            self._enabled
            and self._control_enabled
            and self._tid
            and self._token
            and self._from
            and self._to
            and self._session
        )

    def _control_unavailable_reason(self) -> str:
        if not self._enabled:
            return "cloud disabled"
        if not self._control_enabled:
            return "cloud control disabled"
        missing = []
        if not self._tid:
            missing.append("cloud_tid")
        if not self._token:
            missing.append("cloud_access_token")
        if not self._from:
            missing.append("cloud_from")
        if not self._to:
            missing.append("cloud_to")
        if missing:
            return f"missing config: {', '.join(missing)}"
        if not self._session:
            return "http session not ready"
        return "unknown"

    @staticmethod
    def _cloud_bool(val: str | int | None) -> bool | None:
        if val is None:
            return None
        return str(val).lower() in {"1", "true", "on", "yes"}

    @staticmethod
    def _cloud_int(val: str | float | None) -> int | None:
        if val is None:
            return None
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _cloud_float(val: str | float | None) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _parse_cloud_status(  # noqa: PLR0912, PLR0915
        self, cur_status: dict[str, Any]
    ) -> dict[str, Any]:
        status: dict[str, Any] = {}

        power = self._cloud_bool(cur_status.get("turnOn"))
        if power is not None:
            status["power"] = power

        target_c = self._cloud_float(cur_status.get("celsiusSetTemp"))
        if target_c is not None:
            status["target_temp"] = round(target_c * 9 / 5 + 32, 1)
        else:
            target_temp = self._cloud_int(cur_status.get("setTemp"))
            if target_temp is not None:
                status["target_temp"] = float(target_temp)

            degree_half = self._cloud_bool(cur_status.get("degreeH"))
            if degree_half and "target_temp" in status:
                status["target_temp"] = round(
                    float(status["target_temp"]) + self._HALF_C_IN_F,
                    1,
                )

        current_temp = self._cloud_int(cur_status.get("inTemp"))
        if current_temp is not None:
            status["current_temp"] = current_temp

        outdoor_temp = self._cloud_int(cur_status.get("outTemp"))
        if outdoor_temp is not None:
            status["outdoor_temp"] = outdoor_temp

        wind_map = {
            "0": FAN_AUTO,
            "1": FAN_HIGH,
            "2": FAN_MIDDLE,
            "3": FAN_LOW,
            "4": FAN_HIGH,
            "5": FAN_HIGH,
        }
        wind_spd = cur_status.get("windSpd")
        if wind_spd is not None:
            status["fan_speed"] = wind_map.get(str(wind_spd), FAN_AUTO)

        mode_map = {
            "1": MODE_HEAT,
            "2": MODE_DEHUMI,
            "3": MODE_COOL,
            "4": MODE_HEAT,
            "7": MODE_FAN,
            "8": MODE_AUTO,
        }
        base_mode = cur_status.get("baseMode")
        if base_mode is not None:
            mapped = mode_map.get(str(base_mode))
            if mapped:
                status["mode"] = mapped
            else:
                LOGGER.debug("Unknown cloud baseMode: %s", base_mode)

        swing_h = self._cloud_bool(cur_status.get("directH"))
        if swing_h is not None:
            status["swing_h"] = swing_h

        swing_v = self._cloud_bool(cur_status.get("directV"))
        if swing_v is not None:
            status["swing_v"] = swing_v

        eco = self._cloud_bool(cur_status.get("optECO"))
        if eco is not None:
            status["eco_mode"] = eco

        sleep = cur_status.get("optSleepMd")
        if sleep is not None:
            status["sleep_mode"] = str(sleep) != "0"

        turbo = self._cloud_bool(cur_status.get("optSuper"))
        if turbo is not None:
            status["turbo_mode"] = turbo

        aux_heat = self._cloud_bool(cur_status.get("optHeat"))
        if aux_heat is not None:
            status["aux_heat"] = aux_heat

        healthy = self._cloud_bool(cur_status.get("optHealthy"))
        if healthy is not None:
            status["health_mode"] = healthy

        display = self._cloud_bool(cur_status.get("optDisplay"))
        if display is not None:
            status["display"] = display

        beep = self._cloud_bool(cur_status.get("beepEn"))
        if beep is not None:
            status["beep"] = beep

        return status

    def _build_cloud_message(self, body_xml: str, seq: str) -> str | None:
        if not self._tid or not self._from or not self._to:
            return None

        sendtime = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        msg_id = f"ha_{secrets.randbelow(99000) + 1000}_{int(time.time() * 1000)}"

        return (
            f'<message id="{msg_id}" '
            f'from="{self._from}" '
            f'to="{self._to}" '
            f'type="chat" source="0">'
            f'<x xmlns="tcl:im:attribute">'
            f"<sendtime>{sendtime}</sendtime>"
            f"<apptype>0</apptype><msgtype>1</msgtype>"
            f"</x>"
            f"<body>"
            f'<msg cmd="set" type="control" action="1" seq="{seq}" devid="{self._tid}">'
            f"{body_xml}"
            f"</msg>"
            f"</body>"
            f"</message>"
        )

    async def async_fetch_status(self) -> dict[str, Any] | None:
        """Fetch device status from cloud API when enabled."""
        if not self.status_enabled:
            return None

        url = (
            f"{self._base_url}/device/getdevicestatus"
            f"?tid={self._tid}&category=AC&v={int(time.time() * 1000)}"
        )
        headers = self._headers.build(
            token=self._token, include_token=bool(self._token)
        )

        try:
            async with self._session.get(url, headers=headers, timeout=10) as resp:
                text = await resp.text()
                if resp.status != HTTPStatus.OK:
                    log_warning(
                        LOGGER,
                        "cloud_status_http_error",
                        status=resp.status,
                        tid=self._tid,
                    )
                    return None
        except (TimeoutError, aiohttp.ClientError) as exc:
            log_warning(LOGGER, "cloud_status_request_failed", error=exc)
            return None

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            log_debug(LOGGER, "cloud_status_not_json")
            return None

        cur_status = payload.get("curStatus") or {}
        return self._parse_cloud_status(cur_status)

    async def async_send_command(
        self,
        command: str,
        value: str,
        seq: str,
        degree_half: int | None = None,
    ) -> bool:
        """Send a control command via cloud convertMqtt API."""
        if not self.control_enabled:
            if self._control_enabled:
                log_warning(
                    LOGGER,
                    "cloud_control_unavailable",
                    reason=self._control_unavailable_reason(),
                )
            return False

        tag_map = {
            "TurnOn": "turnOn",
            "SetTemp": "setTemp",
            "WindSpeed": "windSpd",
            "WindDirection_V": "directV",
            "WindDirection_H": "directH",
            "BaseMode": "baseMode",
            "Opt_ECO": "optECO",
            "OptDisplay": "optDisplay",
            "OptHealthy": "optHealthy",
            "Opt_sleepMode": "optSleepMd",
            "Opt_super": "optSuper",
            "OptHeat": "optHeat",
            "BeepEnable": "beepEn",
        }

        tag = tag_map.get(command)
        if not tag:
            return False

        bool_map = {"on": "1", "off": "0", "1": "1", "0": "0"}
        wind_map = {
            "auto": "0",
            "low": "3",
            "middle": "2",
            "high": "1",
        }
        mode_map = {
            MODE_HEAT: "1",
            MODE_DEHUMI: "2",
            MODE_COOL: "3",
            MODE_FAN: "7",
            MODE_AUTO: "8",
        }

        cloud_value = value
        if tag in {
            "turnOn",
            "optECO",
            "optDisplay",
            "optHealthy",
            "optSuper",
            "optHeat",
            "beepEn",
        } or tag in {"directV", "directH"}:
            cloud_value = bool_map.get(value.lower(), value)
        elif tag == "windSpd":
            cloud_value = wind_map.get(value.lower(), value)
        elif tag == "baseMode":
            cloud_value = mode_map.get(value, value)

        body_xml = f'<{tag} value="{cloud_value}"></{tag}>'
        if tag == "setTemp":
            degree_value = "0" if degree_half is None else str(degree_half)
            body_xml += f'<degreeH value="{degree_value}"></degreeH>'

        message = self._build_cloud_message(body_xml, seq)
        if not message:
            return False

        payload = {"source": "APP", "params": message}
        url = f"{self._base_url}/v1/control/convertMqtt/{self._tid}"
        headers = self._headers.build(
            token=self._token,
            include_token=True,
            include_content_type=True,
        )

        try:
            async with self._session.post(
                url, headers=headers, json=payload, timeout=10
            ) as resp:
                if resp.status != HTTPStatus.OK:
                    log_warning(
                        LOGGER,
                        "cloud_control_http_error",
                        status=resp.status,
                        tid=self._tid,
                        command=command,
                    )
                    return False
        except (TimeoutError, aiohttp.ClientError) as exc:
            log_warning(
                LOGGER,
                "cloud_control_request_failed",
                error=exc,
                tid=self._tid,
                command=command,
            )
            return False

        log_info(
            LOGGER,
            "cloud_control_sent",
            tid=self._tid,
            command=command,
            value=value,
            seq=seq,
        )
        return True


class TclUdpApiClient:
    """TCL UDP API Client for local communication."""

    _HALF_C_IN_F = 0.5 * 9 / 5

    def __init__(  # noqa: PLR0913
        self,
        action_jid: str = "homeassistant@tcl.com/ha-plugin",
        action_source: str = "1",
        account: str = "homeassistant",
        session: aiohttp.ClientSession | None = None,
        *,
        cloud_enabled: bool = False,
        cloud_tid: str | None = None,
        cloud_token: str | None = None,
        cloud_from: str | None = None,
        cloud_to: str | None = None,
        cloud_base_url: str = "https://io.zx.tcljd.com",
        cloud_control: bool = False,
        cloud_user_agent: str = DEFAULT_CLOUD_USER_AGENT,
        cloud_platform: str = DEFAULT_CLOUD_PLATFORM,
        cloud_app_package: str = DEFAULT_CLOUD_APP_PACKAGE,
        cloud_system_version: str = DEFAULT_CLOUD_SYSTEM_VERSION,
        cloud_brand: str = DEFAULT_CLOUD_BRAND,
        cloud_app_version: str = DEFAULT_CLOUD_APP_VERSION,
        cloud_sdk_version: str = DEFAULT_CLOUD_SDK_VERSION,
        cloud_channel: str = DEFAULT_CLOUD_CHANNEL,
        cloud_app_build_version: str = DEFAULT_CLOUD_APP_BUILD_VERSION,
        cloud_t_app_version: str = DEFAULT_CLOUD_T_APP_VERSION,
        cloud_t_platform_type: str = DEFAULT_CLOUD_T_PLATFORM_TYPE,
        cloud_t_store_uuid: str = DEFAULT_CLOUD_T_STORE_UUID,
        cloud_origin: str = DEFAULT_CLOUD_ORIGIN,
        cloud_x_requested_with: str = DEFAULT_CLOUD_X_REQUESTED_WITH,
        cloud_accept: str = DEFAULT_CLOUD_ACCEPT,
        cloud_accept_encoding: str = DEFAULT_CLOUD_ACCEPT_ENCODING,
        cloud_accept_language: str = DEFAULT_CLOUD_ACCEPT_LANGUAGE,
    ) -> None:
        """Initialize the API client."""
        self._udp = UdpClient(action_jid, action_source, account)
        self._session = session
        header_profile = CloudHeaderProfile(
            platform=cloud_platform,
            user_agent=cloud_user_agent,
            app_package=cloud_app_package,
            system_version=cloud_system_version,
            brand=cloud_brand,
            app_version=cloud_app_version,
            sdk_version=cloud_sdk_version,
            channel=cloud_channel,
            app_build_version=cloud_app_build_version,
            t_app_version=cloud_t_app_version,
            t_platform_type=cloud_t_platform_type,
            t_store_uuid=cloud_t_store_uuid,
            origin=cloud_origin,
            x_requested_with=cloud_x_requested_with,
            accept=cloud_accept,
            accept_encoding=cloud_accept_encoding,
            accept_language=cloud_accept_language,
        )
        self._cloud = CloudClient(
            session=session,
            enabled=cloud_enabled,
            tid=cloud_tid,
            token=cloud_token,
            from_jid=cloud_from,
            to_jid=cloud_to,
            base_url=cloud_base_url,
            control_enabled=cloud_control,
            headers=header_profile,
        )
        self._cloud_sequence = 0

    async def async_start_listener(self, status_callback: Any) -> None:
        """Start the UDP listener for broadcast messages."""
        try:
            await self._udp.async_start_listener(status_callback)
        except OSError as exception:
            msg = f"Failed to start UDP listener: {exception}"
            raise TclUdpApiClientCommunicationError(msg) from exception

    def _on_socket_readable(self) -> None:
        """Handle socket data readiness."""
        self._udp._on_socket_readable()  # noqa: SLF001

    def _on_send_socket_readable(self) -> None:
        """Handle send socket data readiness (unicast replies)."""
        self._udp._on_send_socket_readable()  # noqa: SLF001

    async def async_stop_listener(self) -> None:
        """Stop the UDP listener."""
        await self._udp.async_stop_listener()

    @property
    def cloud_enabled(self) -> bool:
        """Return True if cloud status fetch is enabled and configured."""
        return self._cloud.status_enabled

    def merge_status(self, status: dict[str, Any]) -> None:
        """Merge status into the last known status."""
        self._udp.merge_status(status)

    async def async_fetch_cloud_status(
        self,
        retries: int = 1,
        retry_delay: float = 1.0,
    ) -> dict[str, Any] | None:
        """Fetch device status from cloud API when enabled (with retry)."""
        attempt = 0
        while True:
            status = await self._cloud.async_fetch_status()
            if status:
                self.merge_status(status)
                return status

            if attempt >= retries:
                if retries:
                    LOGGER.warning(
                        "Cloud status fetch failed after %d attempt(s)",
                        attempt + 1,
                    )
                return None

            attempt += 1
            LOGGER.warning(
                "Cloud status fetch failed, retrying in %.1fs (%d/%d)",
                retry_delay,
                attempt,
                retries,
            )
            await asyncio.sleep(retry_delay)

    async def async_send_cloud_command(self, command: str, value: str) -> bool:
        """Send a control command via cloud convertMqtt API."""
        seq = str(self._cloud_sequence + 1)
        return await self._cloud.async_send_command(command, value, seq)

    def _handle_status_update(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming status update from device."""
        self._udp._handle_status_update(data, addr)  # noqa: SLF001

    def _get_node_value(self, node: ET.Element | None) -> str | None:
        """Extract value from node, handling both <tag value='x'> and <tag>x</tag>."""
        return self._udp._get_node_value(node)  # noqa: SLF001

    def _parse_bool_feature(
        self, status_msg: ET.Element, tag: str, status_key: str, status: dict[str, Any]
    ) -> None:
        """Parse boolean features from both XML formats."""
        self._udp._parse_bool_feature(  # noqa: SLF001
            status_msg, tag, status_key, status
        )

    def _parse_status(self, status_msg: ET.Element) -> dict[str, Any]:
        """Parse status message XML, supporting multiple formats."""
        return self._udp._parse_status(status_msg)  # noqa: SLF001

    async def async_send_command(
        self,
        command: str,
        value: str,
        degree_half: int | None = None,
    ) -> None:
        """
        Send a command using SetMessage XML format (per Java source code).

        Args:
            command: XML tag name (e.g., 'TurnOn', 'SetTemp', 'BaseMode')
            value: Tag value (e.g., 'on', 'off', '78', 'cool')
            degree_half: Optional half-degree flag for cloud/UDP commands.

        """
        try:
            next_seq = str(self._cloud_sequence + 1)
            if self._cloud.control_enabled:
                await self._cloud.async_send_command(
                    command,
                    value,
                    next_seq,
                    degree_half=degree_half,
                )
            self._cloud_sequence += 1
            await self._udp.async_send_command(
                command,
                value,
                degree_half=degree_half,
            )

        except OSError as exception:
            LOGGER.error("Failed to send command: %s", exception)
            raise TclUdpApiClientCommunicationError from exception

    async def async_set_power(self, *, power: bool) -> None:
        """Set power on/off."""
        # Java: <TurnOn>on</TurnOn> or <TurnOn>off</TurnOn>
        await self.async_send_command("TurnOn", "on" if power else "off")

    async def async_set_temperature(self, temperature: float) -> None:
        """Set target temperature."""
        # Java: <SetTemp>78</SetTemp> (Fahrenheit integer)
        temp_value = float(temperature)
        temp_int, degree_half = self._map_set_temp(temp_value)
        await self.async_send_command(
            "SetTemp",
            str(temp_int),
            degree_half=degree_half,
        )

    @staticmethod
    def _fahrenheit_to_celsius(temp_f: float) -> float:
        return (temp_f - 32.0) / 1.8

    @classmethod
    def _map_set_temp(cls, temp_f: float) -> tuple[int, int]:
        """Map Fahrenheit input to setTemp integer + degreeH flag."""
        desired_c = cls._fahrenheit_to_celsius(temp_f)
        desired_c_rounded = round(desired_c * 2) / 2
        base_f = round(temp_f)

        best: tuple[float, float, float, int, int] | None = None
        for f_int in range(base_f - 3, base_f + 4):
            for degree_half in (0, 1):
                c_val = cls._fahrenheit_to_celsius(f_int) + 0.5 * degree_half
                c_rounded = round(c_val * 2) / 2
                diff = abs(c_rounded - desired_c_rounded)
                diff_raw = abs(c_val - desired_c)
                diff_f = abs(f_int - temp_f)
                candidate = (diff, diff_raw, diff_f, f_int, degree_half)
                if best is None or candidate < best:
                    best = candidate

        if best is None:
            return round(temp_f), 0
        return best[3], best[4]

    async def async_set_fan_speed(self, speed_str: str) -> None:
        """Set fan speed (expects 'high', 'middle', 'low', or 'auto')."""
        # Java: <WindSpeed>high</WindSpeed>
        await self.async_send_command("WindSpeed", speed_str)

    async def async_set_swing(self, *, vertical: bool, horizontal: bool) -> None:
        """Set swing mode."""
        # Java: <WindDirection_V>on</WindDirection_V>
        await self.async_send_command("WindDirection_V", "on" if vertical else "off")
        await self.async_send_command("WindDirection_H", "on" if horizontal else "off")

    async def async_set_mode(self, mode_str: str) -> None:
        """Set operation mode (expects 'cool', 'heat', 'fan', 'dehumi', 'selffeel')."""
        # Java: <BaseMode>cool</BaseMode>
        await self.async_send_command("BaseMode", mode_str)

    async def async_set_eco_mode(self, *, enabled: bool) -> None:
        """Set ECO mode."""
        # Java: <Opt_ECO>on</Opt_ECO>
        await self.async_send_command("Opt_ECO", "on" if enabled else "off")

    async def async_set_display(self, *, enabled: bool) -> None:
        """Set display on/off."""
        await self.async_send_command("OptDisplay", "on" if enabled else "off")

    async def async_set_health_mode(self, *, enabled: bool) -> None:
        """Set health mode."""
        await self.async_send_command("OptHealthy", "on" if enabled else "off")

    async def async_set_sleep_mode(self, *, enabled: bool) -> None:
        """Set sleep mode."""
        await self.async_send_command("Opt_sleepMode", "on" if enabled else "off")

    async def async_set_turbo_mode(self, *, enabled: bool) -> None:
        """Set turbo (super) mode."""
        await self.async_send_command("Opt_super", "on" if enabled else "off")

    async def async_set_aux_heat(self, *, enabled: bool) -> None:
        """Set auxiliary (electric) heat on/off."""
        await self.async_send_command("OptHeat", "on" if enabled else "off")

    async def async_set_beep(self, *, enabled: bool) -> None:
        """Set beep on/off."""
        # Java: <BeepEnable>on</BeepEnable>
        await self.async_send_command("BeepEnable", "on" if enabled else "off")

    async def async_send_discovery(self) -> None:
        """Send a discovery packet to find devices."""
        await self._udp.async_send_discovery()

    async def async_request_status(self) -> None:
        """Explicitly request a full status update from the device (SyncStatusReq)."""
        await self._udp.async_request_status()

    def get_last_status(self) -> dict[str, Any]:
        """Get the last received status."""
        return self._udp.get_last_status()

    async def async_close(self) -> None:
        """Close the API client."""
        await self._udp.async_close()


class UDPListenerProtocol(asyncio.DatagramProtocol):
    """UDP listener protocol."""

    def __init__(self, callback: Any) -> None:
        """Initialize the protocol."""
        self._callback = callback

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle received datagram."""
        # CRITICAL DEBUG: Log immediately to confirm this method is actually called
        LOGGER.warning(
            "!!! UDP DATAGRAM RECEIVED from %s, %d bytes !!!", addr, len(data)
        )
        self._callback(data, addr)
