"""UDP API Client for TCL Air Conditioner."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import aiohttp

from .command_bundles import (
    CommandReceipt,
    CommandTransport,
    TransportAttempt,
    TransportDelivery,
)
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
from .credential_manager import CloudAuthRejectedError
from .log_utils import log_debug, log_info, log_warning
from .protocol_driver import ProtocolDriver, resolve_protocol_driver
from .protocol_profiles import UnsupportedModeError
from .temperature_validity import is_valid_outdoor_temperature
from .udp_client import UdpClient

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

    from .command_bundles import TclCommandBundle
    from .udp_hub import UdpHub


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
    # F-series control-panel fault identifiers. TCL reports these as numeric
    # items in ``errorCode``; the panel presents the corresponding short code.
    _TSL_FAULT_CODES = {
        1: "E0",
        2: "EC",
        3: "E3",
        4: "E4",
        5: "E5",
        6: "E7",
        7: "E8",
        8: "E9",
        9: "EF",
        10: "EA",
        11: "EE",
        12: "EP",
        13: "EU",
        14: "EH",
        27: "Ej",
        28: "En",
        29: "Ey",
        30: "F9",
        31: "FA",
        32: "H1",
        33: "H2",
        52: "E1",
        53: "E2",
        54: "E6",
        55: "Eb",
        58: "bf",
        61: "bU",
        62: "bd",
        63: "be",
        64: "b5",
    }

    def __init__(
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
        product_key: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Initialize the cloud API client."""
        self._session = session
        self._enabled = enabled
        self._tid = tid
        self._token = token
        self._from = from_jid
        self._to = to_jid
        self._base_url = base_url.rstrip("/")
        self._product_key = product_key
        self._user_id = user_id
        self._control_enabled = control_enabled
        self._headers = headers
        self._profile: ProtocolDriver = resolve_protocol_driver(
            tid, product_key=product_key
        )

    @property
    def status_enabled(self) -> bool:
        """Return True when status fetch is enabled and configured."""
        return bool(self._enabled and self._tid and self._session)

    @property
    def statistics_enabled(self) -> bool:
        """Return True when cloud statistics can be fetched."""
        return bool(
            self._enabled
            and self._tid
            and self._token
            and self._product_key
            and self._session
        )

    def update_token(self, token: str | None) -> None:
        """Update the access token used for cloud requests."""
        self._token = token

    @staticmethod
    def _raise_for_auth_status(status: int) -> None:
        if status in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            raise CloudAuthRejectedError

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

    @property
    def property_control_enabled(self) -> bool:
        """Return True when TSL property control can be sent."""
        return bool(
            self._enabled
            and self._control_enabled
            and self._tid
            and self._token
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

    def _property_control_unavailable_reason(self) -> str:
        if not self._enabled:
            return "cloud disabled"
        if not self._control_enabled:
            return "cloud control disabled"
        missing = []
        if not self._tid:
            missing.append("cloud_tid")
        if not self._token:
            missing.append("cloud_access_token")
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

    @staticmethod
    def _tsl_mode(val: Any) -> str | None:
        return {
            "1": MODE_COOL,
            "2": MODE_DEHUMI,
            "3": MODE_FAN,
            "4": MODE_HEAT,
            "5": MODE_AUTO,
        }.get(str(val))

    @classmethod
    def _tsl_fan_speed(cls, cur_status: dict[str, Any]) -> str | None:
        auto_switch = cls._cloud_bool(cur_status.get("windSpeedAutoSwitch"))
        gear = cls._cloud_int(cur_status.get("windSpeed7Gear"))
        if auto_switch or gear == 0:
            return FAN_AUTO
        if gear is None:
            return None
        if 1 <= gear <= 7:
            return str(gear)
        return None

    @staticmethod
    def _tsl_direction_is_swing(
        value: Any,
        *,
        swing_values: set[int],
    ) -> bool | None:
        try:
            direction = int(value)
        except (TypeError, ValueError):
            return None
        if direction in swing_values:
            return True
        if direction in {0, 8, 9, 10, 11, 12, 13}:
            return False
        return None

    @staticmethod
    def _fahrenheit_to_celsius(temp_f: float) -> float:
        return (temp_f - 32.0) / 1.8

    @staticmethod
    def _celsius_to_fahrenheit(temp_c: float) -> float:
        return temp_c * 1.8 + 32.0

    def _parse_legacy_cloud_status(self, cur_status: dict[str, Any]) -> dict[str, Any]:
        status: dict[str, Any] = {}

        power = self._cloud_bool(cur_status.get("turnOn"))
        if power is not None:
            status["power"] = power

        target_c = self._cloud_float(cur_status.get("celsiusSetTemp"))
        if target_c is not None:
            status["target_temp"] = round(target_c, 1)
        else:
            target_temp = self._cloud_int(cur_status.get("setTemp"))
            if target_temp is not None:
                status["target_temp"] = round(
                    self._fahrenheit_to_celsius(float(target_temp)),
                    1,
                )

            degree_half = self._cloud_bool(cur_status.get("degreeH"))
            if degree_half and "target_temp" in status:
                status["target_temp"] = round(float(status["target_temp"]) + 0.5, 1)

        current_temp = self._cloud_int(cur_status.get("inTemp"))
        if current_temp is not None:
            status["current_temp"] = round(
                self._fahrenheit_to_celsius(float(current_temp)),
                1,
            )

        outdoor_temp = self._cloud_int(cur_status.get("outTemp"))
        if outdoor_temp is not None:
            # TCL inverter outdoor temp uses Celsius + 150 offset encoding
            outdoor_c = round(float(outdoor_temp) - 150.0, 1)
            if is_valid_outdoor_temperature(outdoor_c):
                status["outdoor_temp"] = outdoor_c

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

        base_mode = cur_status.get("baseMode")
        if base_mode is not None:
            mapped = self._profile.parse_base_mode(base_mode)
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

    def _parse_tsl_core_status(self, cur_status: dict[str, Any]) -> dict[str, Any]:
        status: dict[str, Any] = {}

        power_switch = self._cloud_bool(cur_status.get("powerSwitch"))
        if power_switch is not None:
            status["power"] = power_switch

        target = self._cloud_float(cur_status.get("targetTemperature"))
        if target is not None:
            status["target_temp"] = round(target, 1)

        current = self._cloud_float(cur_status.get("currentTemperature"))
        if current is not None:
            status["current_temp"] = round(current, 1)

        outdoor = self._cloud_float(cur_status.get("externalUnitTemperature"))
        if outdoor is not None and is_valid_outdoor_temperature(outdoor):
            status["outdoor_temp"] = round(outdoor, 1)

        fan_speed = self._tsl_fan_speed(cur_status)
        if fan_speed is not None:
            status["fan_speed"] = fan_speed
        fan_gear = self._cloud_int(cur_status.get("windSpeed7Gear"))
        if fan_gear is not None:
            status["fan_gear"] = fan_gear

        work_mode = cur_status.get("workMode")
        if work_mode is not None:
            mapped = self._tsl_mode(work_mode)
            if mapped:
                status["mode"] = mapped
            else:
                LOGGER.debug("Unknown TSL workMode: %s", work_mode)

        return status

    def _parse_tsl_swing_status(self, cur_status: dict[str, Any]) -> dict[str, Any]:
        status: dict[str, Any] = {}

        swing_h = self._cloud_bool(cur_status.get("horizontalSwitch"))
        if swing_h is None:
            swing_h = self._cloud_bool(cur_status.get("horizontalWind"))
        if swing_h is None and "horizontalDirection" in cur_status:
            swing_h = self._tsl_direction_is_swing(
                cur_status.get("horizontalDirection"),
                swing_values={1, 2, 3, 4},
            )
        if swing_h is not None:
            status["swing_h"] = swing_h

        swing_v = self._cloud_bool(cur_status.get("verticalSwitch"))
        if swing_v is None:
            swing_v = self._cloud_bool(cur_status.get("verticalWind"))
        if swing_v is None and "verticalDirection" in cur_status:
            swing_v = self._tsl_direction_is_swing(
                cur_status.get("verticalDirection"),
                swing_values={1, 2, 3},
            )
        if swing_v is not None:
            status["swing_v"] = swing_v

        return status

    def _parse_tsl_feature_status(self, cur_status: dict[str, Any]) -> dict[str, Any]:
        status: dict[str, Any] = {}

        feature_map = {
            "ECO": "eco_mode",
            "sleep": "sleep_mode",
            "turbo": "turbo_mode",
            "healthy": "health_mode",
            "screen": "display",
            "beepSwitch": "beep",
            "beepTempEn": "beep_temperature",
            "antiMoldew": "anti_mildew",
            "softWind": "soft_wind",
            "selfClean": "self_clean",
            "newWindAutoSwitch": "fresh_air_auto",
        }
        for raw_key, status_key in feature_map.items():
            value = self._cloud_bool(cur_status.get(raw_key))
            if value is not None:
                status[status_key] = value

        aux_heat = self._cloud_bool(
            cur_status.get(
                "PTC",
                cur_status.get("PTCStatus", cur_status.get("eightAddHot")),
            )
        )
        if aux_heat is not None:
            status["aux_heat"] = aux_heat

        return status

    def _parse_tsl_diagnostics(self, cur_status: dict[str, Any]) -> dict[str, Any]:
        """Normalize every observed read-only field from the F-series TSL."""
        status: dict[str, Any] = {}
        numeric_map = {
            "internalUnitCoilTemperature": "internal_coil_temperature",
            "externalUnitCoilTemperature": "external_coil_temperature",
            "externalUnitExhaustTemperature": "external_exhaust_temperature",
            "externalUnitVoltage": "external_voltage",
            "externalUnitElectricCurrent": "external_current",
            "compressorFrequency": "compressor_frequency",
            "internalUnitFanSpeed": "internal_fan_speed",
            "externalUnitFanSpeed": "external_fan_speed",
            "internalUnitFanCurrentGear": "internal_fan_gear",
            "externalUnitFanGear": "external_fan_gear",
            "windSpeedPercentage": "wind_speed_percentage",
            "newWindSetMode": "fresh_air_mode",
            "newWindPercentage": "fresh_air_percentage",
            "sleepTime": "sleep_time",
            "selfCleanStatus": "self_clean_status",
        }
        for raw_key, data_key in numeric_map.items():
            value = self._cloud_float(cur_status.get(raw_key))
            if value is not None:
                status[data_key] = int(value) if value.is_integer() else value

        expansion = self._cloud_float(
            cur_status.get("expansionValve ", cur_status.get("expansionValve"))
        )
        if expansion is not None:
            status["expansion_valve"] = (
                int(expansion) if expansion.is_integer() else expansion
            )

        text_map = {
            "tslLatestVersion": "tsl_version",
            "tslReqVersion": "tsl_request_version",
            "aiSmartControlSource": "ai_control_source",
        }
        for raw_key, data_key in text_map.items():
            value = cur_status.get(raw_key)
            if value is not None:
                status[data_key] = str(value) or "unknown"

        errors = cur_status.get("errorCode")
        if isinstance(errors, list):
            # A healthy live F-series unit returns [48], the JSON byte form of
            # ASCII "0". 48 is not a fault identifier in its control panel.
            if errors == [48]:
                status["error_codes"] = "none"
            else:
                status["error_codes"] = (
                    ", ".join(
                        self._TSL_FAULT_CODES.get(item, str(item))
                        if isinstance(item, int) and not isinstance(item, bool)
                        else str(item)
                        for item in errors
                    )
                    or "none"
                )
        elif errors is not None:
            status["error_codes"] = str(errors)

        query_time = self._cloud_float(cur_status.get("tslQueryTime"))
        if query_time is not None and query_time > 0:
            status["tsl_query_time"] = datetime.fromtimestamp(
                query_time / 1000.0, tz=UTC
            )

        bool_map = {
            "filterBlockStatus": "filter_blocked",
            "fourWayValveStatus": "four_way_valve_active",
            "PTCStatus": "aux_heat_active",
            "selfLearn": "self_learning",
        }
        for raw_key, data_key in bool_map.items():
            value = self._cloud_bool(cur_status.get(raw_key))
            if value is not None:
                status[data_key] = value
        return status

    def _parse_tsl_cloud_status(self, cur_status: dict[str, Any]) -> dict[str, Any]:
        status = self._parse_tsl_core_status(cur_status)
        status.update(self._parse_tsl_swing_status(cur_status))
        status.update(self._parse_tsl_feature_status(cur_status))
        status.update(self._parse_tsl_diagnostics(cur_status))
        return status

    def _parse_cloud_status(self, cur_status: dict[str, Any]) -> dict[str, Any]:
        family = self._profile.cloud_status_family
        if family == "legacy":
            return self._parse_legacy_cloud_status(cur_status)
        if family == "tsl":
            return self._parse_tsl_cloud_status(cur_status)
        status = self._parse_legacy_cloud_status(cur_status)
        status.update(self._parse_tsl_cloud_status(cur_status))
        return status

    def _build_statistics_headers(self) -> dict[str, str]:
        """Build TCL+ headers for AC electricity/runtime statistics."""
        headers = self._headers.build(token=self._token, include_token=True)
        if self._tid:
            headers["deviceid"] = self._tid
        if self._product_key:
            headers["productkey"] = self._product_key
        if self._user_id:
            headers["userid"] = self._user_id
        return headers

    @staticmethod
    def _month_from_row(row: dict[str, Any]) -> str | None:
        data_list = row.get("dataList")
        if not isinstance(data_list, list) or not data_list:
            return None
        for item in data_list:
            if not isinstance(item, dict):
                continue
            time_value = item.get("time")
            if isinstance(time_value, str) and len(time_value) >= 7:
                return time_value[:7]
        return None

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _parse_electricity_summary(
        self, payload: dict[str, Any], *, today: date | None = None
    ) -> dict[str, Any] | None:
        """Parse TCL+ electricity summary into HA-safe report statistics."""
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        rows = data.get("ecoDetails")
        if not isinstance(rows, list):
            return None

        current_month = (today or datetime.now(UTC).date()).strftime("%Y-%m")
        candidates = [row for row in rows if isinstance(row, dict)]
        selected = next(
            (row for row in candidates if self._month_from_row(row) == current_month),
            None,
        )
        if selected is None and candidates:
            selected = candidates[-1]
        if selected is None:
            return None

        period_start = period_end = None
        data_list = selected.get("dataList")
        if isinstance(data_list, list):
            times = [
                item.get("time")
                for item in data_list
                if isinstance(item, dict) and isinstance(item.get("time"), str)
            ]
            if times:
                period_start = times[0]
                period_end = times[-1]

        stats = {
            "period_start": period_start,
            "period_end": period_end,
            "energy_kwh": self._number(selected.get("electricity")),
            "running_hours": self._number(selected.get("runningHours")),
            "eco_hours": self._number(selected.get("ecoHours")),
            "electricity_bill": self._number(selected.get("electricityBill")),
            "carbon_emission": self._number(selected.get("carbonEmission")),
        }
        if stats["energy_kwh"] is None and stats["running_hours"] is None:
            return None
        return stats

    async def async_fetch_energy_statistics(self) -> dict[str, Any] | None:
        """Fetch current-month TCL+ electricity/runtime report statistics."""
        if not self.statistics_enabled:
            return None

        url = f"{self._base_url}/v1/ac/statistics/electricity/summary?timeType=2"
        try:
            async with self._session.get(
                url, headers=self._build_statistics_headers(), timeout=10
            ) as resp:
                text = await resp.text()
                self._raise_for_auth_status(resp.status)
                if resp.status != HTTPStatus.OK:
                    log_warning(
                        LOGGER,
                        "cloud_statistics_http_error",
                        status=resp.status,
                        tid=self._tid,
                    )
                    return None
        except (TimeoutError, aiohttp.ClientError) as exc:
            log_warning(LOGGER, "cloud_statistics_request_failed", error=exc)
            return None

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            log_debug(LOGGER, "cloud_statistics_not_json")
            return None

        stats = self._parse_electricity_summary(payload)
        if stats is None:
            log_debug(LOGGER, "cloud_statistics_empty", tid=self._tid)
        return stats

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

    @staticmethod
    def _build_property_msg_id() -> str:
        return f"ha_{secrets.randbelow(99000) + 1000}_{int(time.time() * 1000)}"

    def _build_tsl_property_payload(self, bundle: TclCommandBundle) -> dict[str, Any]:
        """Build the TCL+ property-control JSON body for a TSL bundle."""
        payload: dict[str, Any] = {
            "msgId": self._build_property_msg_id(),
            "version": "1.0",
            "params": [dict(bundle.payload)],
            "source": "APP",
        }
        if bundle.module_id:
            payload["moduleId"] = bundle.module_id
        return payload

    def _tsl_property_url(self, bundle: TclCommandBundle) -> str | None:
        if not self._tid:
            return None
        path = "/v1/control/property" if bundle.source_type else "/v1/tclplus/property"
        return f"{self._base_url}{path}/{self._tid}"

    def _build_tsl_property_headers(self, bundle: TclCommandBundle) -> dict[str, str]:
        """Build TCL+ headers for TSL property-control writes."""
        headers = self._headers.build(
            token=self._token,
            include_token=True,
            include_content_type=True,
        )
        if bundle.source_type:
            headers["sourceType"] = str(bundle.source_type)
        return headers

    @staticmethod
    def _tsl_property_response_ok(text: str) -> bool:
        if not text:
            return True
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return True
        code = payload.get("code")
        return code in {None, "", 0, "0", 200, "200"} or payload.get("success") is True

    async def async_send_tsl_property_bundle(self, bundle: TclCommandBundle) -> bool:
        """Send a protocol 1 TSL property-control bundle."""
        if not self.property_control_enabled:
            if self._control_enabled:
                log_warning(
                    LOGGER,
                    "tsl_property_control_unavailable",
                    reason=self._property_control_unavailable_reason(),
                )
            return False

        url = self._tsl_property_url(bundle)
        if not url:
            return False

        payload = self._build_tsl_property_payload(bundle)
        desc = ", ".join(f"{key}={value}" for key, value in bundle.payload.items())
        try:
            async with self._session.post(
                url,
                headers=self._build_tsl_property_headers(bundle),
                json=payload,
                timeout=10,
            ) as resp:
                text = await resp.text()
                self._raise_for_auth_status(resp.status)
                if resp.status != HTTPStatus.OK:
                    log_warning(
                        LOGGER,
                        "tsl_property_control_http_error",
                        status=resp.status,
                        tid=self._tid,
                        command=desc,
                    )
                    return False
        except (TimeoutError, aiohttp.ClientError) as exc:
            log_warning(
                LOGGER,
                "tsl_property_control_request_failed",
                error=exc,
                tid=self._tid,
                command=desc,
            )
            return False

        if not self._tsl_property_response_ok(text):
            log_warning(
                LOGGER,
                "tsl_property_control_rejected",
                tid=self._tid,
                command=desc,
            )
            return False

        log_info(
            LOGGER,
            "tsl_property_control_sent",
            tid=self._tid,
            command=desc,
        )
        return True

    async def async_fetch_status(self) -> dict[str, Any] | None:
        """Fetch device status from cloud API when enabled."""
        if not self.status_enabled:
            return None

        is_tsl = self._profile.cloud_status_family == "tsl"
        if is_tsl:
            url = f"{self._base_url}/v1/thing/status"
        else:
            url = (
                f"{self._base_url}/device/getdevicestatus"
                f"?tid={self._tid}&category=AC&v={int(time.time() * 1000)}"
            )
        headers = self._headers.build(
            token=self._token, include_token=bool(self._token)
        )

        try:
            request = (
                self._session.post(
                    url, headers=headers, json={"deviceId": self._tid}, timeout=10
                )
                if is_tsl
                else self._session.get(url, headers=headers, timeout=10)
            )
            async with request as resp:
                text = await resp.text()
                self._raise_for_auth_status(resp.status)
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

        cur_status = (
            ((payload.get("data") or {}).get("status") or {})
            if is_tsl
            else (payload.get("curStatus") or {})
        )
        return self._parse_cloud_status(cur_status)

    async def async_send_command(
        self,
        command: str,
        value: str,
        seq: str,
        degree_half: int | None = None,
    ) -> bool:
        """Send a single control command via cloud convertMqtt API."""
        items = [(command, value)]
        if command == "SetTemp" and degree_half is not None:
            items.append(("DegreeH", str(degree_half)))
        return await self.async_send_commands(items, seq)

    def _map_cloud_item(self, command: str, value: str) -> tuple[str, str] | None:
        """Map a HA-style command/value to cloud tag/value."""
        tag_map = {
            "TurnOn": "turnOn",
            "SetTemp": "setTemp",
            "DegreeH": "degreeH",
            "WindSpeed": "windSpd",
            "WindDirection_V": "directV",
            "WindDirection_H": "directH",
            "BaseMode": "baseMode",
            "Opt_ECO": "optECO",
            "OptDisplay": "optDisplay",
            "OptHealthy": "optHealthy",
            "Opt_sleepMode": "optSleepMd",
            "Opt_super": "optSuper",
            "OptSolidWd": "optSolidWd",
            "OptHeat": "optHeat",
            "BeepEnable": "beepEn",
        }

        tag = tag_map.get(command)
        if not tag:
            return None

        bool_map = {"on": "1", "off": "0", "1": "1", "0": "0"}
        wind_map = {
            "auto": "0",
            "low": "3",
            "middle": "2",
            "high": "1",
        }
        mode_map = {
            MODE_HEAT: "4",
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
            "optSleepMd",
            "optSuper",
            "optSolidWd",
            "optHeat",
            "beepEn",
            "directV",
            "directH",
        }:
            cloud_value = bool_map.get(value.lower(), value)
        elif tag == "windSpd":
            cloud_value = wind_map.get(value.lower(), value)
        elif tag == "baseMode":
            cloud_value = mode_map.get(value, value)

        return tag, cloud_value

    async def async_send_commands(
        self,
        items: list[tuple[str, str]],
        seq: str,
    ) -> bool:
        """
        Send multiple control tags in ONE cloud convertMqtt message.

        items: list of (HA_command, HA_value) pairs.
        """
        if not self.control_enabled:
            if self._control_enabled:
                log_warning(
                    LOGGER,
                    "cloud_control_unavailable",
                    reason=self._control_unavailable_reason(),
                )
            return False

        body_parts: list[str] = []
        for command, value in items:
            mapped = self._map_cloud_item(command, value)
            if mapped is None:
                LOGGER.warning("Unknown cloud command: %s", command)
                continue
            tag, cloud_value = mapped
            body_parts.append(f'<{tag} value="{cloud_value}"></{tag}>')

        if not body_parts:
            return False

        body_xml = "".join(body_parts)
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

        desc = ", ".join(f"{c}={v}" for c, v in items)
        try:
            async with self._session.post(
                url, headers=headers, json=payload, timeout=10
            ) as resp:
                if resp.status != HTTPStatus.OK:
                    self._raise_for_auth_status(resp.status)
                    log_warning(
                        LOGGER,
                        "cloud_control_http_error",
                        status=resp.status,
                        tid=self._tid,
                        command=desc,
                    )
                    return False
        except (TimeoutError, aiohttp.ClientError) as exc:
            log_warning(
                LOGGER,
                "cloud_control_request_failed",
                error=exc,
                tid=self._tid,
                command=desc,
            )
            return False

        log_info(
            LOGGER,
            "cloud_control_sent",
            tid=self._tid,
            command=desc,
            value="batch",
            seq=seq,
        )
        return True


class TclUdpApiClient:
    """TCL UDP API Client for local communication."""

    _HALF_C_IN_F = 0.5 * 9 / 5

    def __init__(
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
        cloud_product_key: str | None = None,
        cloud_user_id: str | None = None,
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
        device_mac: str | None = None,
        udp_hub: UdpHub | None = None,
    ) -> None:
        """Initialize the API client."""
        self._protocol_profile = resolve_protocol_driver(
            cloud_tid,
            product_key=cloud_product_key,
        )
        self._udp = UdpClient(
            action_jid,
            action_source,
            account,
            protocol_profile=self._protocol_profile,
            device_mac=device_mac,
            device_id=cloud_tid,
            udp_hub=udp_hub,
        )
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
            product_key=cloud_product_key,
            user_id=cloud_user_id,
            control_enabled=cloud_control,
            headers=header_profile,
        )
        self._cloud_sequence = 0
        self._token_manager: Any = None

    def set_token_manager(self, token_manager: Any) -> None:
        """Attach the credential facade after runtime construction."""
        self._token_manager = token_manager

    async def _async_cloud_request(self, operation: Any) -> Any:
        """Run one authorized cloud request through credential maintenance."""
        token_manager = getattr(self, "_token_manager", None)
        if token_manager is None:
            return await operation()
        return await token_manager.async_authenticated_request(operation)

    async def async_start_listener(self, status_callback: Any) -> None:
        """Start the UDP listener for broadcast messages."""
        if not self._protocol_profile.local_transport_enabled:
            return
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
        if not self._protocol_profile.local_transport_enabled:
            return
        await self._udp.async_stop_listener()

    @property
    def cloud_enabled(self) -> bool:
        """Return True if cloud status fetch is enabled and configured."""
        return self._cloud.status_enabled

    @property
    def cloud_statistics_enabled(self) -> bool:
        """Return True if cloud statistics fetch is enabled and configured."""
        return self._cloud.statistics_enabled

    def update_cloud_token(self, token: str | None) -> None:
        """Update the cloud access token on the live client (after refresh)."""
        self._cloud.update_token(token)

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
            status = await self._async_cloud_request(self._cloud.async_fetch_status)
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

    async def async_fetch_cloud_energy_statistics(self) -> dict[str, Any] | None:
        """Fetch TCL+ electricity/runtime statistics."""
        return await self._async_cloud_request(
            self._cloud.async_fetch_energy_statistics
        )

    async def async_send_cloud_command(self, command: str, value: str) -> bool:
        """Send a control command via cloud convertMqtt API."""
        seq = str(self._cloud_sequence + 1)
        return await self._async_cloud_request(
            lambda: self._cloud.async_send_command(command, value, seq)
        )

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
    ) -> TransportDelivery:
        """
        Send a single command via both cloud and UDP.

        Args:
            command: XML tag name (e.g., 'TurnOn', 'SetTemp', 'BaseMode')
            value: Tag value (e.g., 'on', 'off', '78', 'cool')
            degree_half: Optional half-degree flag for SetTemp commands.

        """
        items: list[tuple[str, str]] = [(command, value)]
        if command == "SetTemp" and degree_half is not None:
            items.append(("DegreeH", str(degree_half)))
            # The real TCL app always disables Super/Turbo mode when
            # setting temperature, otherwise the device ignores setTemp.
            items.append(("Opt_super", "off"))
        return await self.async_send_commands(items)

    async def async_send_commands(
        self,
        items: list[tuple[str, str]],
    ) -> TransportDelivery:
        """
        Send multiple tags in ONE message via both cloud and UDP.

        items: list of (tag, value) pairs, e.g. [("TurnOn", "on"), ("BaseMode", "cool")]
        """
        try:
            profile = getattr(
                self,
                "_protocol_profile",
                resolve_protocol_driver(None),
            )
            if not getattr(profile, "legacy_transport_enabled", True):
                log_warning(
                    LOGGER,
                    "legacy_command_unsupported_for_profile",
                    profile=getattr(profile, "name", "unknown"),
                    command=", ".join(f"{key}={value}" for key, value in items),
                )
                return TransportDelivery()
            self._cloud_sequence += 1
            next_seq = str(self._cloud_sequence)
            cloud_attempt = TransportAttempt.SKIPPED
            if self._cloud.control_enabled:
                cloud_accepted = await self._async_cloud_request(
                    lambda: self._cloud.async_send_commands(items, next_seq)
                )
                cloud_attempt = (
                    TransportAttempt.ACCEPTED
                    if cloud_accepted
                    else TransportAttempt.REJECTED
                )
            udp_accepted = await self._udp.async_send_commands(items)
            udp_attempt = (
                TransportAttempt.ACCEPTED if udp_accepted else TransportAttempt.SKIPPED
            )
            return TransportDelivery(cloud=cloud_attempt, udp=udp_attempt)
        except OSError as exception:
            LOGGER.error("Failed to send command: %s", exception)
            if (
                "cloud_attempt" in locals()
                and cloud_attempt == TransportAttempt.ACCEPTED
            ):
                return TransportDelivery(
                    cloud=cloud_attempt,
                    udp=TransportAttempt.FAILED,
                )
            raise TclUdpApiClientCommunicationError from exception

    async def async_send_command_bundle(
        self, bundle: TclCommandBundle
    ) -> CommandReceipt:
        """Send a profile-built grouped command bundle."""
        if bundle.transport == CommandTransport.TSL_PROPERTY:
            sent = await self._async_cloud_request(
                lambda: self._cloud.async_send_tsl_property_bundle(bundle)
            )
            delivery = TransportDelivery(
                cloud=(TransportAttempt.ACCEPTED if sent else TransportAttempt.REJECTED)
            )
        else:
            delivery = await self.async_send_commands(bundle.to_command_items())

        return CommandReceipt(
            intent=bundle.intent,
            expected_status=dict(bundle.expected_status),
            delivery=delivery,
        )

    async def async_set_power(self, *, power: bool) -> CommandReceipt:
        """Set power on/off."""
        profile = getattr(self, "_protocol_profile", resolve_protocol_driver(None))
        bundle = (
            profile.build_power_on_command()
            if power
            else profile.build_power_off_command()
        )
        return await self.async_send_command_bundle(bundle)

    async def async_set_power_mode(
        self, *, power: bool, mode_str: str | None = None
    ) -> CommandReceipt:
        """
        Set power and mode in a single combined message.

        When turning on, always include mode to avoid the device using
        a stale mode from a previous session.
        """
        items: list[tuple[str, str]] = [
            ("TurnOn", "on" if power else "off"),
        ]
        if power and mode_str:
            items.append(("BaseMode", mode_str))
        delivery = await self.async_send_commands(items)
        expected_status: dict[str, Any] = {"power": power}
        if power and mode_str:
            expected_status["mode"] = mode_str
        return CommandReceipt("power_mode:set", expected_status, delivery)

    async def async_set_mode_profile(
        self,
        mode_str: str,
        *,
        target_temperature: float | None = None,
    ) -> CommandReceipt:
        """Set HVAC mode through the configured protocol profile."""
        bundle = self._protocol_profile.build_mode_command(
            mode_str,
            target_temperature=target_temperature,
        )
        return await self.async_send_command_bundle(bundle)

    async def async_set_temperature(self, temperature: float) -> CommandReceipt:
        """Set target temperature."""
        profile = getattr(self, "_protocol_profile", None)
        if profile is not None:
            current_mode = self.get_last_status().get("mode")
            try:
                bundle = profile.build_temperature_command(
                    float(temperature),
                    current_mode=current_mode,
                )
            except UnsupportedModeError:
                log_warning(
                    LOGGER,
                    "temperature_unsupported_for_profile_context",
                    profile=getattr(profile, "name", "unknown"),
                    current_mode=current_mode,
                    temperature=temperature,
                )
                raise
            return await self.async_send_command_bundle(bundle)

        # Test/fallback path for object instances that were constructed before
        # protocol profiles existed.
        temp_value = float(temperature)
        temp_int, degree_half = self._map_set_temp(temp_value)
        delivery = await self.async_send_command(
            "SetTemp",
            str(temp_int),
            degree_half=degree_half,
        )
        return CommandReceipt(
            "temperature:set", {"target_temp": float(temperature)}, delivery
        )

    @staticmethod
    def _fahrenheit_to_celsius(temp_f: float) -> float:
        return (temp_f - 32.0) / 1.8

    @staticmethod
    def _celsius_to_fahrenheit(temp_c: float) -> float:
        return temp_c * 1.8 + 32.0

    @classmethod
    def _map_set_temp(cls, temp_c: float) -> tuple[int, int]:
        """Map Celsius input to protocol setTemp integer + degreeH flag."""
        desired_c_rounded = round(temp_c * 2) / 2
        base_f = round(cls._celsius_to_fahrenheit(temp_c))

        best: tuple[float, float, float, int, int] | None = None
        for f_int in range(base_f - 3, base_f + 4):
            for degree_half in (0, 1):
                c_val = cls._fahrenheit_to_celsius(f_int) + 0.5 * degree_half
                c_rounded = round(c_val * 2) / 2
                diff = abs(c_rounded - desired_c_rounded)
                diff_raw = abs(c_val - temp_c)
                diff_f = abs(f_int - cls._celsius_to_fahrenheit(temp_c))
                candidate = (diff, diff_raw, diff_f, f_int, degree_half)
                if best is None or candidate < best:
                    best = candidate

        if best is None:
            return round(cls._celsius_to_fahrenheit(temp_c)), 0
        return best[3], best[4]

    async def async_set_fan_speed(self, speed_str: str) -> CommandReceipt | None:
        """Set fan speed (expects 'high', 'middle', 'low', or 'auto')."""
        profile = getattr(self, "_protocol_profile", resolve_protocol_driver(None))
        if not profile.capabilities.supports_fan_speed:
            log_warning(
                LOGGER,
                "fan_speed_unsupported_for_profile",
                profile=getattr(profile, "name", "unknown"),
                fan_speed=speed_str,
            )
            return None
        return await self.async_send_command_bundle(
            profile.build_fan_command(speed_str)
        )

    async def async_set_swing(
        self, *, vertical: bool, horizontal: bool
    ) -> CommandReceipt | None:
        """Set swing mode (both directions in one message)."""
        profile = getattr(self, "_protocol_profile", resolve_protocol_driver(None))
        if not profile.capabilities.supports_swing:
            log_warning(
                LOGGER,
                "swing_unsupported_for_profile",
                profile=getattr(profile, "name", "unknown"),
                vertical=vertical,
                horizontal=horizontal,
            )
            return None
        return await self.async_send_command_bundle(
            profile.build_swing_command(vertical=vertical, horizontal=horizontal)
        )

    async def async_set_mode(self, mode_str: str) -> CommandReceipt:
        """Set operation mode (expects 'cool', 'heat', 'fan', 'dehumi', 'selffeel')."""
        # Java: <BaseMode>cool</BaseMode>
        delivery = await self.async_send_command("BaseMode", mode_str)
        return CommandReceipt("mode:set", {"mode": mode_str}, delivery)

    async def async_set_eco_mode(self, *, enabled: bool) -> CommandReceipt:
        """Set ECO mode."""
        return await self.async_set_feature("eco_mode", enabled=enabled)

    async def async_set_display(self, *, enabled: bool) -> CommandReceipt:
        """Set display on/off."""
        return await self.async_set_feature("display", enabled=enabled)

    async def async_set_health_mode(self, *, enabled: bool) -> CommandReceipt:
        """Set health mode."""
        return await self.async_set_feature("health_mode", enabled=enabled)

    async def async_set_sleep_mode(self, *, enabled: bool) -> CommandReceipt:
        """Set sleep mode."""
        return await self.async_set_feature("sleep_mode", enabled=enabled)

    async def async_set_turbo_mode(self, *, enabled: bool) -> CommandReceipt:
        """Set turbo (super) mode."""
        return await self.async_set_feature("turbo_mode", enabled=enabled)

    async def async_set_aux_heat(self, *, enabled: bool) -> CommandReceipt:
        """Set auxiliary (electric) heat on/off."""
        return await self.async_set_feature("aux_heat", enabled=enabled)

    async def async_set_beep(self, *, enabled: bool) -> CommandReceipt:
        """Set beep on/off."""
        return await self.async_set_feature("beep", enabled=enabled)

    async def async_set_feature(
        self, data_key: str, *, enabled: bool
    ) -> CommandReceipt:
        """Set a profile-described feature without leaking protocol details."""
        profile = getattr(self, "_protocol_profile", resolve_protocol_driver(None))
        bundle = profile.build_feature_command(data_key, enabled=enabled)
        return await self.async_send_command_bundle(bundle)

    async def async_set_number(self, data_key: str, value: float) -> CommandReceipt:
        """Set a profile-described numeric property."""
        bundle = self._protocol_profile.build_number_command(data_key, value)
        return await self.async_send_command_bundle(bundle)

    async def async_send_discovery(self) -> None:
        """Send a discovery packet to find devices."""
        if not self._protocol_profile.local_transport_enabled:
            return
        await self._udp.async_send_discovery()

    async def async_request_status(self) -> None:
        """Explicitly request a full status update from the device (SyncStatusReq)."""
        if not self._protocol_profile.local_transport_enabled:
            return
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
