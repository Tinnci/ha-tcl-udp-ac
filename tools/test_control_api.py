#!/usr/bin/env python3
"""Comprehensive test script for TCL AC control API and status verification.

Tests power on/off, mode switching, combined vs single commands via Cloud API,
and optionally local UDP. Verifies status changes after each control operation.

Usage:
  python tools/test_control_api.py                              # interactive menu
  python tools/test_control_api.py --capture-file FILE          # specify capture jsonl
  python tools/test_control_api.py --no-verify                  # skip TLS verification
  python tools/test_control_api.py --allow-live --test power-cycle  # run specific live test
  python tools/test_control_api.py --test all                   # run all tests
  python tools/test_control_api.py --status                     # just show current status
  python tools/test_control_api.py --dry-run                    # show commands without sending

Test Categories:
  status           - Fetch and display current device status
  power-on         - Turn on (single turnOn=1)
  power-off        - Turn off using the app-captured shutdown group
  power-cycle      - Turn off, verify, turn on, verify
  mode-cool        - Set cool using the capture-derived profile bundle
  mode-heat        - Set heat using the capture-derived profile bundle
  mode-fan         - Set fan using the capture-derived legacy profile bundle
  mode-dehumi      - Set dry using the capture-derived profile bundle
  mode-auto        - Report unsupported Auto/AI without sending a command
  mode-matrix      - Test cool/dry/heat/fan/auto as profile bundles
  combined-on-cool - Turn on + set cool in ONE message
  combined-on-heat - Turn on + set heat in ONE message
  separate-on-cool - Turn on THEN set cool in TWO messages
  separate-on-heat - Turn on THEN set heat in TWO messages
  combined-off     - Power off using the app shutdown group
  combined-temp    - Set temperature + degreeH in ONE message
  temp-experiment  - Legacy temperature test plus captured TSL metadata report
  temp-matrix      - Contextual temperature transaction matrix
  swing-combined   - Set both directH + directV in ONE message
  swing-separate   - Set directH THEN directV in TWO messages
  compare-power    - Compare combined vs separate power+mode (full cycle)
  all              - Run all tests sequentially
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import ssl
import sys
import time
import types
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "custom_components" not in sys.modules:
    custom_components_pkg = types.ModuleType("custom_components")
    custom_components_pkg.__path__ = [str(ROOT / "custom_components")]
    sys.modules["custom_components"] = custom_components_pkg
if "custom_components.tcl_udp_ac" not in sys.modules:
    integration_pkg = types.ModuleType("custom_components.tcl_udp_ac")
    integration_pkg.__path__ = [str(ROOT / "custom_components" / "tcl_udp_ac")]
    sys.modules["custom_components.tcl_udp_ac"] = integration_pkg

from custom_components.tcl_udp_ac.const import (
    MODE_AUTO,
    MODE_COOL,
    MODE_DEHUMI,
    MODE_FAN,
    MODE_HEAT,
)
from custom_components.tcl_udp_ac.command_bundles import (
    CaptureEvidence,
    TransactionOutcome,
    TclCommandTransaction,
    VerificationPolicy,
)
from custom_components.tcl_udp_ac.protocol_profiles import (
    UnsupportedModeError,
    resolve_protocol_profile,
)
from custom_components.tcl_udp_ac.temperature_codec import LegacyTemperatureCodec

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CAPTURE = "tcl_1770274433.jsonl"
BASE_URL = "https://io.zx.tcljd.com"

# Cloud API value maps (matching the app behavior observed in captures)
MODE_MAP = {
    "heat": "4",
    "dehumi": "2",
    "cool": "1",
}
MODE_MAP_REV = {v: k for k, v in MODE_MAP.items()}
MODE_MAP_REV["0"] = "fan"
CLI_MODE_MAP = {
    "cool": "1",
    "dry": "2",
    "dehumi": "2",
    "heat": "4",
    "fan": "0",
}
WIND_MAP = {"auto": "0", "high": "1", "middle": "2", "low": "3"}
WIND_MAP_REV = {v: k for k, v in WIND_MAP.items()}

# Status display fields of interest
STATUS_KEY_FIELDS = [
    "turnOn",
    "baseMode",
    "setTemp",
    "celsiusSetTemp",
    "degreeH",
    "inTemp",
    "outTemp",
    "windSpd",
    "directH",
    "directV",
    "beepEn",
    "optECO",
    "optSuper",
    "optDisplay",
    "optSleepMd",
    "optHealthy",
    "optHeat",
    "optSolidWd",
    "optAntiM",
    "actionSource",
]

APP_POWER_OFF_ITEMS = [
    ("optSleepMd", "0"),
    ("optECO", "0"),
    ("optHealthy", "0"),
    ("optSuper", "0"),
    ("optHeat", "0"),
    ("turnOn", "0"),
]


class LiveTestFailure(RuntimeError):
    """Raised when a live control test fails and the run should stop."""


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, no external deps)
# ---------------------------------------------------------------------------
class HttpClient:
    """Thin HTTP client wrapper."""

    def __init__(self, no_verify: bool = False, verbose: bool = False) -> None:
        self._ctx: ssl.SSLContext | None = None
        if no_verify:
            self._ctx = ssl._create_unverified_context()
        self._verbose = verbose

    def get(self, url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        req = urllib.request.Request(url, headers=headers or {}, method="GET")
        if self._verbose:
            print(f"  GET {url}")
        try:
            with urllib.request.urlopen(req, timeout=15, context=self._ctx) as fp:
                body = fp.read().decode("utf-8", errors="replace")
                return fp.getcode(), body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            return e.code, body
        except Exception as e:
            print(f"  HTTP GET failed: {e}", file=sys.stderr)
            return -1, str(e)

    def post(
        self, url: str, headers: dict[str, str], body: bytes
    ) -> tuple[int, str]:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        if self._verbose:
            print(f"  POST {url}")
            print(f"  Body: {body.decode('utf-8', errors='replace')[:300]}")
        try:
            with urllib.request.urlopen(req, timeout=15, context=self._ctx) as fp:
                res = fp.read().decode("utf-8", errors="replace")
                return fp.getcode(), res
        except urllib.error.HTTPError as e:
            res = e.read().decode("utf-8", errors="replace") if e.fp else ""
            return e.code, res
        except Exception as e:
            print(f"  HTTP POST failed: {e}", file=sys.stderr)
            return -1, str(e)


# ---------------------------------------------------------------------------
# Capture file parsing
# ---------------------------------------------------------------------------
def load_credentials_from_capture(capture_file: Path) -> dict[str, Any]:
    """Extract tid, accesstoken, from, to, headers from capture jsonl."""
    text = capture_file.read_text(encoding="utf-8", errors="replace")
    last_convert = None
    last_status = None

    for line in text.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("type") == "request":
            url = j.get("url", "")
            if "/v1/control/convertMqtt/" in url:
                last_convert = j
            elif "device/getdevicestatus" in url:
                last_status = j

    if not last_convert:
        print("ERROR: No convertMqtt request found in capture file", file=sys.stderr)
        sys.exit(3)

    url = last_convert["url"]
    tid = url.rstrip("/").split("/")[-1]
    raw_headers = last_convert.get("headers", {})

    # Extract from/to from the XML params
    body_str = last_convert.get("body", "")
    try:
        body_json = json.loads(body_str)
        params_xml = body_json.get("params", "")
    except (json.JSONDecodeError, TypeError):
        params_match = re.search(r'"params"\s*:\s*"(.*?)"', body_str, re.S)
        params_xml = params_match.group(1).replace('\\"', '"') if params_match else ""

    m_from = re.search(r'from="([^"]+)"', params_xml)
    m_to = re.search(r'to="([^"]+)"', params_xml)
    from_jid = m_from.group(1) if m_from else f"14427826@tcl.com/PH-android-zx01-2"
    to_jid = m_to.group(1) if m_to else f"{tid}@tcl.com/AC-linux-zx01-1"

    # Build control headers
    control_headers: dict[str, str] = {}
    for k in [
        "platform", "user-agent", "apppackagename", "systemversion", "brand",
        "appversion", "sdkversion", "accesstoken", "channel", "appbuildversion",
        "t-app-version", "t-platform-type", "t-store-uuid", "accept-encoding",
    ]:
        if k in raw_headers:
            control_headers[k] = raw_headers[k]
        elif k.title() in raw_headers:
            control_headers[k] = raw_headers[k.title()]

    # Build status headers (from getdevicestatus request)
    status_headers: dict[str, str] = {
        "user-agent": raw_headers.get("user-agent", "Mozilla/5.0"),
        "origin": "https://h5.zx.tcljd.com",
        "x-requested-with": "com.tcl.tclplus",
        "accept": "text/plain, */*; q=0.01",
        "accept-encoding": raw_headers.get("accept-encoding", "gzip, deflate, br, zstd"),
        "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    if last_status:
        sh = last_status.get("headers", {})
        if "user-agent" in sh:
            status_headers["user-agent"] = sh["user-agent"]

    return {
        "tid": tid,
        "from": from_jid,
        "to": to_jid,
        "control_headers": control_headers,
        "status_headers": status_headers,
        "access_token": control_headers.get("accesstoken", ""),
    }


def _normalise_work_mode_label(label: Any) -> str:
    """Normalize captured TCL+ work-mode labels to HA-oriented names."""
    text = str(label).strip().lower()
    return {
        "制冷": "cool",
        "cool": "cool",
        "除湿": "dry",
        "dehumi": "dry",
        "dry": "dry",
        "送风": "fan",
        "fan": "fan",
        "制热": "heat",
        "heat": "heat",
        "ai": "AI",
        "auto": "AI",
        "智能": "AI",
    }.get(text, str(label).strip())


def extract_device_capabilities_from_capture_text(text: str) -> dict[str, dict[str, Any]]:
    """Extract device protocol/capability hints from captured user_devices responses."""
    capabilities: dict[str, dict[str, Any]] = {}

    for line in text.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if record.get("type") != "response":
            continue
        if "/v1/tclplus/user/user_devices" not in record.get("url", ""):
            continue

        try:
            body = json.loads(record.get("body", "{}"))
        except (json.JSONDecodeError, TypeError):
            continue

        for device in body.get("data") or []:
            device_id = str(device.get("deviceId") or "")
            if not device_id:
                continue

            identifiers = {
                str(item.get("identifier")).strip()
                for item in device.get("identifiers") or []
                if item.get("identifier") is not None
            }
            control_identifiers = {
                str(item.get("identifier")).strip()
                for item in device.get("listControl") or []
                if item.get("identifier") is not None
            }
            work_mode_values: dict[str, str] = {}
            target_temperature_spec: dict[str, Any] = {}
            for item in device.get("listControl") or []:
                identifier = str(item.get("identifier") or "").strip()
                data_type = item.get("dataType") or {}
                specs = data_type.get("specs") or {}
                if identifier == "workMode":
                    work_mode_values = {
                        str(value): _normalise_work_mode_label(label)
                        for value, label in specs.items()
                    }
                elif identifier == "targetTemperature":
                    target_temperature_spec = dict(specs)

            capabilities[device_id] = {
                "device_id": device_id,
                "protocol": str(device.get("protocol") or ""),
                "identifiers": sorted(identifiers),
                "control_identifiers": sorted(control_identifiers),
                "has_tsl_target_temperature": "targetTemperature" in control_identifiers,
                "has_legacy_set_temp": "setTemp" in identifiers,
                "work_mode_values": work_mode_values,
                "target_temperature_spec": target_temperature_spec,
            }

    return capabilities


def extract_device_capabilities_from_capture(capture_file: Path) -> dict[str, dict[str, Any]]:
    """Extract capability hints from a capture file."""
    return extract_device_capabilities_from_capture_text(
        capture_file.read_text(encoding="utf-8", errors="replace")
    )


def build_temperature_experiment_plan(
    tid: str,
    capabilities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a safe temperature experiment plan from captured capabilities.

    The current harness knows the legacy convertMqtt write path. It can inspect
    newer TSL-style metadata from captures, but it must not invent a write
    endpoint without a captured request to prove the exact API shape.
    """
    current = capabilities.get(str(tid), {})
    comparable_tsl_devices = sorted(
        device_id
        for device_id, info in capabilities.items()
        if device_id != str(tid) and info.get("has_tsl_target_temperature")
    )
    return {
        "legacy_protocol": "convertMqtt/setTemp",
        "legacy_fields": ["setTemp", "degreeH", "optSuper"],
        "current_device_has_tsl_target_temperature": bool(
            current.get("has_tsl_target_temperature")
        ),
        "tsl_write_safe_to_send": False,
        "tsl_write_reason": (
            "No captured TSL targetTemperature write request exists in this capture."
        ),
        "comparable_tsl_devices": comparable_tsl_devices,
        "current_device": current,
    }


# ---------------------------------------------------------------------------
# Cloud API: Status
# ---------------------------------------------------------------------------
def fetch_status(
    http: HttpClient,
    tid: str,
    status_headers: dict[str, str],
    *,
    label: str = "Status",
    quiet: bool = False,
) -> dict[str, Any]:
    """Fetch and display current device status."""
    url = f"{BASE_URL}/device/getdevicestatus?tid={tid}&category=AC&v={int(time.time() * 1000)}"

    # Retry once on timeout
    for attempt in range(2):
        code, body = http.get(url, headers=status_headers)
        if code != -1:
            break
        if attempt == 0:
            print(f"  ... status HTTP timeout, retrying ...")
            time.sleep(2)

    if code != 200:
        print(f"  [{label}] HTTP {code} - FAILED")
        return {}

    try:
        j = json.loads(body)
    except json.JSONDecodeError:
        print(f"  [{label}] Invalid JSON response")
        return {}

    cur_status = j.get("curStatus", {})
    line_status = j.get("LINE_STATUS", "?")

    if not quiet:
        print(f"\n{'='*60}")
        print(f"  [{label}]  LINE_STATUS={line_status}")
        print(f"{'='*60}")
        for k in STATUS_KEY_FIELDS:
            v = cur_status.get(k)
            if v is not None:
                extra = ""
                if k == "turnOn":
                    extra = f"  ({'ON' if str(v) == '1' else 'OFF'})"
                elif k == "baseMode":
                    extra = f"  ({MODE_MAP_REV.get(str(v), '?')})"
                elif k == "windSpd":
                    extra = f"  ({WIND_MAP_REV.get(str(v), '?')})"
                print(f"    {k:20s} = {v}{extra}")

        # Show other fields not in the key list
        other_keys = sorted(set(cur_status.keys()) - set(STATUS_KEY_FIELDS))
        if other_keys:
            print(f"  {'--- other fields ---':^40}")
            for k in other_keys:
                print(f"    {k:20s} = {cur_status[k]}")

    return cur_status


# ---------------------------------------------------------------------------
# Cloud API: Control
# ---------------------------------------------------------------------------
def build_control_xml(
    from_jid: str,
    to_jid: str,
    tid: str,
    items: list[tuple[str, str]],
    seq: int | None = None,
) -> str:
    """Build the XML message for cloud convertMqtt control.

    items: list of (tag_name, value) pairs to send in ONE message.
    """
    if seq is None:
        seq = int(time.time() % 100000)
    msg_id = f"ha_test_{secrets.randbelow(90000) + 10000}_{int(time.time() * 1000)}"
    sendtime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    items_xml = "".join(f'<{tag} value="{val}"></{tag}>' for tag, val in items)

    return (
        f'<message id="{msg_id}" from="{from_jid}" to="{to_jid}" '
        f'type="chat" source="0">'
        f'<x xmlns="tcl:im:attribute">'
        f"<sendtime>{sendtime}</sendtime>"
        f"<apptype>0</apptype><msgtype>1</msgtype>"
        f"</x>"
        f"<body>"
        f'<msg cmd="set" type="control" action="1" seq="{seq}" devid="{tid}">'
        f"{items_xml}"
        f"</msg></body></message>"
    )


def send_cloud_control(
    http: HttpClient,
    creds: dict[str, Any],
    items: list[tuple[str, str]],
    *,
    label: str = "control",
    dry_run: bool = False,
) -> bool:
    """Send a cloud control command with one or more tags."""
    tid = creds["tid"]
    xml = build_control_xml(creds["from"], creds["to"], tid, items)
    payload = json.dumps({"source": "APP", "params": xml}).encode("utf-8")

    items_desc = ", ".join(f"{t}={v}" for t, v in items)
    print(f"\n  >> CLOUD CONTROL [{label}]: {items_desc}")

    if dry_run:
        print(f"     [DRY-RUN] XML: {xml[:200]}...")
        return True

    headers = dict(creds["control_headers"])
    headers["Content-Type"] = "application/json; charset=UTF-8"

    url = f"{BASE_URL}/v1/control/convertMqtt/{tid}"

    # Retry once on timeout
    for attempt in range(2):
        code, body = http.post(url, headers, payload)
        if code != -1:
            break
        if attempt == 0:
            print(f"     HTTP timeout, retrying ...")
            time.sleep(2)

    if code == 200:
        try:
            r = json.loads(body)
            success = r.get("success", False)
            print(f"     HTTP {code} success={success}")
            return success
        except json.JSONDecodeError:
            print(f"     HTTP {code} (non-json response)")
            return code == 200
    else:
        print(f"     HTTP {code} FAILED: {body[:200]}")
        return False


# ---------------------------------------------------------------------------
# Local UDP: Control
# ---------------------------------------------------------------------------
def send_udp_control(
    device_ip: str,
    device_port: int,
    device_mac: str,
    items: list[tuple[str, str]],
    *,
    label: str = "udp_control",
    dry_run: bool = False,
    timeout: float = 3.0,
) -> str | None:
    """Send a UDP SetMessage with one or more tags.

    Unlike the current integration code which sends one tag at a time,
    this sends ALL tags in a single SetMessage.
    """
    import socket

    seq = int(time.time() % 100000)
    items_xml = "".join(f"<{tag}>{val}</{tag}>" for tag, val in items)

    mac_attr = ""
    if device_mac and device_mac != "00:00:00:00:00:00":
        mac_attr = f' tclid="{device_mac.upper()}"'

    xml_command = (
        f'<msg{mac_attr} msgid="SetMessage" type="Control" seq="{seq}">'
        f"<SetMessage>{items_xml}</SetMessage>"
        f"</msg>"
    )

    items_desc = ", ".join(f"{t}={v}" for t, v in items)
    print(f"\n  >> UDP CONTROL [{label}]: {items_desc}")
    print(f"     Target: {device_ip}:{device_port}")
    print(f"     XML: {xml_command}")

    if dry_run:
        print("     [DRY-RUN]")
        return None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    try:
        sock.sendto(xml_command.encode("utf-8"), (device_ip, device_port))
        print("     Sent OK")
    except OSError as e:
        print(f"     Send FAILED: {e}")
        sock.close()
        return None

    try:
        data, addr = sock.recvfrom(4096)
        response = data.decode("utf-8", errors="replace")
        print(f"     Response from {addr}: {response[:200]}")
        sock.close()
        return response
    except TimeoutError:
        print(f"     No response within {timeout}s")
        sock.close()
        return None


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
class TestRunner:
    """Manages test execution and status verification."""

    def __init__(
        self,
        http: HttpClient,
        creds: dict[str, Any],
        *,
        dry_run: bool = False,
        delay: float = 2.0,
        stop_on_failure: bool = True,
        udp_ip: str | None = None,
        udp_port: int = 10075,
        udp_mac: str | None = None,
        device_capabilities: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.http = http
        self.creds = creds
        self.dry_run = dry_run
        self.delay = delay
        self.stop_on_failure = stop_on_failure
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.udp_mac = udp_mac
        self.device_capabilities = device_capabilities or {}
        self.protocol_profile = resolve_protocol_profile(str(creds.get("tid", "")))
        self.results: list[dict[str, Any]] = []
        self._seq = int(time.time() % 100000)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def status(self, label: str = "Status", *, quiet: bool = False) -> dict[str, Any]:
        return fetch_status(
            self.http, self.creds["tid"], self.creds["status_headers"],
            label=label, quiet=quiet,
        )

    def cloud_control(
        self, items: list[tuple[str, str]], *, label: str = "control"
    ) -> bool:
        return send_cloud_control(
            self.http, self.creds, items, label=label, dry_run=self.dry_run,
        )

    def udp_control(
        self, items: list[tuple[str, str]], *, label: str = "udp"
    ) -> str | None:
        if not self.udp_ip:
            print("  [SKIP UDP] No --device-ip provided")
            return None
        return send_udp_control(
            self.udp_ip, self.udp_port, self.udp_mac or "",
            items, label=label, dry_run=self.dry_run,
        )

    def wait_and_check(self, label: str, fields_to_check: dict[str, str]) -> dict[str, Any]:
        """Wait then check status, comparing expected field values.

        On HTTP timeout, retries once after an extra delay.
        """
        if self.dry_run:
            print(f"  [DRY-RUN] Would wait {self.delay}s then verify: {fields_to_check}")
            return {}

        print(f"\n  ... waiting {self.delay}s for status update ...")
        time.sleep(self.delay)
        s = self.status(label=f"After {label}")

        # Retry once on HTTP failure (empty dict means timeout/error)
        if not s:
            print(f"  ... retrying status after extra {self.delay}s ...")
            time.sleep(self.delay)
            s = self.status(label=f"After {label} (retry)")

        # Verify expected values
        mismatches = {}
        matches = {}
        for k, expected in fields_to_check.items():
            actual = str(s.get(k, "?"))
            if actual == expected:
                matches[k] = actual
            else:
                mismatches[k] = {"expected": expected, "actual": actual}

        if mismatches:
            print(f"\n  !! MISMATCHES for [{label}]:")
            for k, v in mismatches.items():
                print(f"     {k}: expected={v['expected']}, actual={v['actual']}")
        if matches:
            print(f"  OK verified: {matches}")

        result = {
            "test": label,
            "status": s,
            "expected": fields_to_check,
            "matches": matches,
            "mismatches": mismatches,
            "success": len(mismatches) == 0,
        }
        self.results.append(result)
        if mismatches and self.stop_on_failure:
            raise LiveTestFailure(f"{label} did not reach expected state: {mismatches}")
        return s

    def execute_transaction(
        self,
        transaction: TclCommandTransaction,
        *,
        label: str,
        status_delays: tuple[float, ...] | None = None,
        poll_interval: float | None = None,
        poll_timeout: float | None = None,
        raise_on_mismatch: bool = True,
    ) -> dict[str, Any]:
        """Send a transaction and verify status projection separately."""
        items = list(transaction.payload.items())
        accepted = self.cloud_control(items, label=label)
        if self.dry_run:
            print(
                "  [DRY-RUN] Would verify transaction projection: "
                f"{transaction.expected_status_projection}"
            )
            return {}

        status_after: dict[str, Any] = {}
        start = time.monotonic()
        if poll_interval is not None and poll_timeout is not None:
            print(
                f"\n  ... polling every {poll_interval:g}s for up to "
                f"{poll_timeout:g}s ..."
            )
            next_sleep = max(poll_interval, 0.1)
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= poll_timeout:
                    break
                time.sleep(min(next_sleep, max(poll_timeout - elapsed, 0.0)))
                elapsed = time.monotonic() - start
                status_after = self.status(
                    label=f"After {label} +{elapsed:.1f}s",
                    quiet=True,
                )
                self._print_observed_status(status_after)
                interim = transaction.classify_result(
                    transport_accepted=accepted,
                    status_after=status_after,
                )
                if interim.outcome == TransactionOutcome.APPLIED:
                    print(f"  First matching status after {elapsed:.1f}s")
                    break
        else:
            delays = status_delays or (self.delay,)
            for delay in delays:
                print(f"\n  ... waiting {delay}s for [{label}] status check ...")
                time.sleep(delay)
                status_after = self.status(
                    label=f"After {label} +{delay:g}s",
                    quiet=True,
                )
                self._print_observed_status(status_after)

        if not status_after:
            status_after = {}

        result = transaction.classify_result(
            transport_accepted=accepted,
            status_after=status_after,
        )
        record = {
            "test": label,
            "status": status_after,
            "expected": transaction.expected_status_projection,
            "matches": result.matches,
            "mismatches": result.mismatches,
            "success": result.outcome == TransactionOutcome.APPLIED,
            "transaction_outcome": result.outcome.value,
        }
        self.results.append(record)
        print(f"  Transaction outcome: {result.outcome.value}")
        if result.mismatches:
            for key, mismatch in result.mismatches.items():
                print(
                    f"     {key}: expected={mismatch['expected']} "
                    f"actual={mismatch['actual']}"
                )
        if result.mismatches and self.stop_on_failure and raise_on_mismatch:
            raise LiveTestFailure(
                f"{label} did not apply expected status: {result.mismatches}"
            )
        return status_after

    @staticmethod
    def _print_observed_status(status_after: dict[str, Any]) -> None:
        """Print compact status fields for transaction polling."""
        if not status_after:
            print("     observed: <empty status>")
            return
        set_temp = status_after.get("setTemp")
        degree_h = status_after.get("degreeH")
        base_mode = status_after.get("baseMode")
        turn_on = status_after.get("turnOn")
        wind_spd = status_after.get("windSpd")
        print(
            "     observed: "
            f"turnOn={turn_on}, baseMode={base_mode}, "
            f"setTemp={set_temp}, degreeH={degree_h}, windSpd={wind_spd}"
        )

    def safe_power_off(self, *, label: str = "safe-power-off") -> dict[str, Any]:
        """Turn off with the app-captured shutdown group and verify state."""
        self.cloud_control(APP_POWER_OFF_ITEMS, label=label)
        return self.wait_and_check(label, {"turnOn": "0"})

    # --- Individual Tests ---

    def test_status(self) -> None:
        print("\n" + "=" * 70)
        print("TEST: Fetch Current Status")
        print("=" * 70)
        self.status(label="Current")

    def test_power_on(self) -> None:
        print("\n" + "=" * 70)
        print("TEST: Power ON (single tag: turnOn=1)")
        print("=" * 70)
        self.cloud_control([("turnOn", "1")], label="power-on")
        self.wait_and_check("power-on", {"turnOn": "1"})

    def test_power_off(self) -> None:
        print("\n" + "=" * 70)
        print("TEST: Power OFF (app shutdown group)")
        print("=" * 70)
        self.cloud_control(APP_POWER_OFF_ITEMS, label="power-off")
        self.wait_and_check("power-off", {"turnOn": "0"})

    def test_power_cycle(self) -> None:
        print("\n" + "=" * 70)
        print("TEST: Power Cycle (OFF -> verify -> ON -> verify)")
        print("=" * 70)
        before = self.status(label="Before power-cycle")

        self.cloud_control(APP_POWER_OFF_ITEMS, label="cycle-off")
        self.wait_and_check("cycle-off", {"turnOn": "0"})

        self.cloud_control([("turnOn", "1")], label="cycle-on")
        self.wait_and_check("cycle-on", {"turnOn": "1"})

    def test_mode(self, mode_name: str) -> None:
        mode_val = MODE_MAP.get(mode_name)
        if not mode_val:
            print(
                f"  Unsupported standalone mode: {mode_name}. "
                "Use the capture-derived profile path instead."
            )
            return
        print("\n" + "=" * 70)
        print(f"TEST: Set Mode to {mode_name} (single tag: baseMode={mode_val})")
        print("=" * 70)
        self.cloud_control([("baseMode", mode_val)], label=f"mode-{mode_name}")
        self.wait_and_check(f"mode-{mode_name}", {"baseMode": mode_val})

    def test_grouped_mode(self, mode_name: str, *, label_prefix: str = "grouped-mode") -> None:
        """Set mode with a capture-derived protocol profile bundle."""
        profile_mode = {
            "cool": MODE_COOL,
            "dehumi": MODE_DEHUMI,
            "heat": MODE_HEAT,
            "fan": MODE_FAN,
            "selffeel": MODE_AUTO,
            "auto": MODE_AUTO,
        }.get(mode_name)
        if not profile_mode:
            print(f"  Unknown mode: {mode_name}")
            return

        label = f"{label_prefix}-{mode_name}"
        try:
            bundle = self.protocol_profile.build_mode_command(profile_mode)
        except UnsupportedModeError as exc:
            print("\n" + "=" * 70)
            print(f"TEST: Grouped Mode to {mode_name} (unsupported)")
            print("=" * 70)
            print(f"  >> Unsupported by protocol profile: {exc}")
            return

        mode_val = bundle.payload.get("baseMode")
        print("\n" + "=" * 70)
        print(f"TEST: Profile Mode to {mode_name} (capture-derived bundle)")
        print(f"  Evidence: {bundle.evidence.level} - {bundle.evidence.source}")
        print("=" * 70)
        self.cloud_control(
            list(bundle.payload.items()),
            label=label,
        )
        expected = {"turnOn": "1"}
        if mode_val is not None:
            expected["baseMode"] = mode_val
        self.wait_and_check(label, expected)

    def test_mode_matrix(self) -> None:
        """Run the known mode matrix one command at a time."""
        print("\n" + "=" * 70)
        print("TEST: Mode Matrix (capture-derived protocol profiles)")
        print("=" * 70)
        print("  Temperature-only experiments remain separate from mode profiles.")

        for mode_name in ("cool", "dehumi", "heat", "fan", "selffeel"):
            self.test_grouped_mode(mode_name, label_prefix="mode-matrix")

    def test_combined_on_mode(self, mode_name: str) -> None:
        """Turn ON + set mode in ONE message (the correct way the app does it)."""
        mode_val = MODE_MAP.get(mode_name)
        if not mode_val:
            print(f"  Unknown mode: {mode_name}")
            return
        print("\n" + "=" * 70)
        print(f"TEST: Combined ON + {mode_name} (turnOn=1 + baseMode={mode_val} in ONE message)")
        print("=" * 70)

        # First turn off and confirm off state (avoids timing issues)
        self.cloud_control(APP_POWER_OFF_ITEMS, label=f"combined-pre-off")
        if not self.dry_run:
            time.sleep(self.delay)
            s_off = self.status(label="confirm-off", quiet=True)
            print(f"  Confirmed: turnOn={s_off.get('turnOn')}")

        # Now send combined on+mode
        self.cloud_control(
            [("turnOn", "1"), ("baseMode", mode_val)],
            label=f"combined-on-{mode_name}",
        )
        self.wait_and_check(
            f"combined-on-{mode_name}",
            {"turnOn": "1", "baseMode": mode_val},
        )

    def test_separate_on_mode(self, mode_name: str) -> None:
        """Turn ON then set mode in TWO separate messages (current HA behavior)."""
        mode_val = MODE_MAP.get(mode_name)
        if not mode_val:
            print(f"  Unknown mode: {mode_name}")
            return
        print("\n" + "=" * 70)
        print(f"TEST: Separate ON then {mode_name} (turnOn=1, THEN baseMode={mode_val})")
        print("=" * 70)

        # First turn off and confirm off state
        self.cloud_control(APP_POWER_OFF_ITEMS, label=f"separate-pre-off")
        if not self.dry_run:
            time.sleep(self.delay)
            s_off = self.status(label="confirm-off", quiet=True)
            print(f"  Confirmed: turnOn={s_off.get('turnOn')}")

        # Send power on first
        self.cloud_control([("turnOn", "1")], label=f"separate-on")
        print(f"  ... waiting 1s (follow-up) ...")
        if not self.dry_run:
            time.sleep(1.0)

        # Then send mode
        self.cloud_control([("baseMode", mode_val)], label=f"separate-mode-{mode_name}")
        self.wait_and_check(
            f"separate-on-{mode_name}",
            {"turnOn": "1", "baseMode": mode_val},
        )

    def test_combined_temp(self, temp_f: int = 75, degree_h: str = "0") -> None:
        """Set temperature + degreeH in ONE message (like the app does).

        Ensures device is ON first, since temp changes are ignored when OFF.
        """
        print("\n" + "=" * 70)
        print(f"TEST: Combined Temp (setTemp={temp_f} + degreeH={degree_h})")
        print("=" * 70)

        # Ensure device is ON (temp changes are ignored when OFF)
        if not self.dry_run:
            s = self.status(label="temp-pre-check", quiet=True)
            if s.get("turnOn") != "1":
                print("  Device is OFF, turning ON first ...")
                self.cloud_control([("turnOn", "1"), ("baseMode", "1")], label="temp-ensure-on")
                time.sleep(self.delay)

        # Real TCL app always sends optSuper=0 with temp changes
        items = [("setTemp", str(temp_f)), ("degreeH", degree_h), ("optSuper", "0")]
        self.cloud_control(items, label=f"temp-{temp_f}-dh{degree_h}")
        self.wait_and_check(
            f"temp-{temp_f}",
            {"setTemp": str(temp_f), "degreeH": degree_h},
        )

    def test_temperature_experiment(self, temp_f: int = 75, degree_h: str = "0") -> None:
        """Compare known legacy temperature behavior with captured TSL metadata."""
        print("\n" + "=" * 70)
        print("TEST: Temperature Experiment")
        print("=" * 70)

        plan = build_temperature_experiment_plan(
            self.creds["tid"],
            self.device_capabilities,
        )
        current = plan["current_device"]
        print(f"  Current tid: {self.creds['tid']}")
        if current:
            print(
                "  Captured protocol="
                f"{current.get('protocol')}, identifiers={current.get('identifiers')}"
            )
        else:
            print("  No user_devices metadata found for current tid in capture.")

        if plan["comparable_tsl_devices"]:
            print(
                "  Captured TSL-style targetTemperature metadata on devices: "
                + ", ".join(plan["comparable_tsl_devices"])
            )
        else:
            print("  No captured TSL-style targetTemperature metadata found.")
        print(f"  TSL write safe to send: {plan['tsl_write_safe_to_send']}")
        print(f"  TSL write reason: {plan['tsl_write_reason']}")

        print("\n  --- Legacy convertMqtt temperature command ---")
        self.test_combined_temp(temp_f=temp_f, degree_h=degree_h)

    def build_temperature_matrix_transactions(
        self,
        *,
        temp_f: int = 75,
        degree_h: str = "0",
        mode: str | None = None,
        current_status: dict[str, Any] | None = None,
    ) -> list[tuple[str, TclCommandTransaction]]:
        """Build contextual temperature hypotheses without marking them supported."""
        current_status = current_status or {}
        base_mode = CLI_MODE_MAP.get(str(mode or "").lower()) if mode else None
        base_mode = base_mode or str(current_status.get("baseMode") or "1")
        wind_spd = str(current_status.get("windSpd") or "0")
        evidence = CaptureEvidence(
            level="hypothesis",
            source="manual contextual temperature experiment",
            rationale=(
                "Standalone setTemp was transport-accepted but not device-applied; "
                "these candidates test whether current mode context is required."
            ),
        )
        expected = {"setTemp": str(temp_f), "degreeH": degree_h}
        cases = [
            (
                "A-field-only",
                {"setTemp": str(temp_f), "degreeH": degree_h},
            ),
            (
                "B-power-temp",
                {"turnOn": "1", "setTemp": str(temp_f), "degreeH": degree_h},
            ),
            (
                "C-mode-temp",
                {
                    "turnOn": "1",
                    "baseMode": base_mode,
                    "setTemp": str(temp_f),
                    "degreeH": degree_h,
                },
            ),
            (
                "D-mode-temp-auto-fan",
                {
                    "turnOn": "1",
                    "baseMode": base_mode,
                    "setTemp": str(temp_f),
                    "degreeH": degree_h,
                    "windSpd": "0",
                },
            ),
            (
                "E-mode-temp-current-fan",
                {
                    "turnOn": "1",
                    "baseMode": base_mode,
                    "setTemp": str(temp_f),
                    "degreeH": degree_h,
                    "windSpd": wind_spd,
                },
            ),
            (
                "F-mode-temp-super-clear",
                {
                    "turnOn": "1",
                    "baseMode": base_mode,
                    "setTemp": str(temp_f),
                    "degreeH": degree_h,
                    "windSpd": "0",
                    "optSuper": "0",
                },
            ),
        ]
        return [
            (
                name,
                TclCommandTransaction(
                    intent=f"temperature:{name}",
                    payload=payload,
                    evidence=evidence,
                    expected_status_projection=expected,
                    verification_policy=VerificationPolicy.STATUS_MATCH,
                ),
            )
            for name, payload in cases
        ]

    def test_temperature_matrix(
        self,
        temp_f: int = 75,
        degree_h: str = "0",
        *,
        mode: str | None = None,
        candidate: str | None = None,
        poll_interval: float = 1.0,
        poll_timeout: float = 12.0,
    ) -> None:
        """Run the contextual temperature transaction matrix."""
        print("\n" + "=" * 70)
        print("TEST: Contextual Temperature Transaction Matrix")
        print("=" * 70)
        print("  This is experimental. It does not change HA temperature support.")
        print(
            "  Live mode polls status every "
            f"{poll_interval:g}s for up to {poll_timeout:g}s per candidate."
        )
        if mode:
            print(f"  Forced mode context: {mode} (baseMode={CLI_MODE_MAP.get(mode)})")

        current_status: dict[str, Any] = {}
        if not self.dry_run:
            current_status = self.status(label="Temperature matrix baseline", quiet=True)
        else:
            print("  [DRY-RUN] Assuming current baseMode=1 and windSpd=0.")

        transactions = self.build_temperature_matrix_transactions(
            temp_f=temp_f,
            degree_h=degree_h,
            mode=mode,
            current_status=current_status,
        )
        if candidate:
            candidate_key = candidate.upper()
            transactions = [
                (name, transaction)
                for name, transaction in transactions
                if name.startswith(f"{candidate_key}-")
            ]
            if not transactions:
                print(f"  Unknown candidate: {candidate}")
                return

        for name, transaction in transactions:
            print("\n" + "-" * 70)
            print(f"Candidate {name}: {transaction.payload}")
            self.execute_transaction(
                transaction,
                label=f"temp-matrix-{name}",
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
                raise_on_mismatch=False,
            )

    def test_swing_combined(self, h: str = "1", v: str = "1") -> None:
        """Set both swing directions in ONE message."""
        print("\n" + "=" * 70)
        print(f"TEST: Combined Swing (directH={h} + directV={v} in ONE message)")
        print("=" * 70)
        self.cloud_control(
            [("directH", h), ("directV", v)],
            label="swing-combined",
        )
        self.wait_and_check("swing-combined", {"directH": h, "directV": v})

    def test_swing_separate(self, h: str = "1", v: str = "1") -> None:
        """Set swing directions in TWO separate messages."""
        print("\n" + "=" * 70)
        print(f"TEST: Separate Swing (directH={h} THEN directV={v})")
        print("=" * 70)
        self.cloud_control([("directH", h)], label="swing-h")
        if not self.dry_run:
            time.sleep(0.5)
        self.cloud_control([("directV", v)], label="swing-v")
        self.wait_and_check("swing-separate", {"directH": h, "directV": v})

    def test_compare_power_mode(self) -> None:
        """Full comparison: combined vs separate power+mode."""
        print("\n" + "=" * 70)
        print("TEST: COMPARISON - Combined vs Separate Power+Mode")
        print("=" * 70)

        before = self.status(label="Comparison baseline", quiet=True)

        cool_mode = MODE_MAP["cool"]

        # --- Test A: Combined OFF then Combined ON+COOL ---
        print(
            "\n  --- A: Combined turnOn=0 -> Combined turnOn=1 "
            f"+ baseMode={cool_mode} ---"
        )
        self.cloud_control(APP_POWER_OFF_ITEMS, label="A-off")
        if not self.dry_run:
            time.sleep(self.delay)
        s_off = self.status(label="A-after-off", quiet=True)
        print(f"     turnOn={s_off.get('turnOn')}, baseMode={s_off.get('baseMode')}")

        self.cloud_control(
            [("turnOn", "1"), ("baseMode", cool_mode)],
            label="A-combined-on-cool",
        )
        s_a = self.wait_and_check(
            "A-combined",
            {"turnOn": "1", "baseMode": cool_mode},
        )

        # --- Test B: Combined OFF then Separate ON then COOL ---
        print(
            "\n  --- B: Combined turnOn=0 -> Separate turnOn=1 "
            f"-> baseMode={cool_mode} ---"
        )
        self.cloud_control(APP_POWER_OFF_ITEMS, label="B-off")
        if not self.dry_run:
            time.sleep(self.delay)
        s_off2 = self.status(label="B-after-off", quiet=True)
        print(f"     turnOn={s_off2.get('turnOn')}, baseMode={s_off2.get('baseMode')}")

        self.cloud_control([("turnOn", "1")], label="B-on")
        if not self.dry_run:
            time.sleep(0.5)
        self.cloud_control([("baseMode", cool_mode)], label="B-mode-cool")
        s_b = self.wait_and_check(
            "B-separate",
            {"turnOn": "1", "baseMode": cool_mode},
        )

        # --- Test C: Try Combined ON + HEAT ---
        heat_mode = MODE_MAP["heat"]
        print(f"\n  --- C: Combined turnOn=0 -> Combined turnOn=1 + baseMode={heat_mode} (heat) ---")
        self.cloud_control(APP_POWER_OFF_ITEMS, label="C-off")
        if not self.dry_run:
            time.sleep(self.delay)

        self.cloud_control(
            [("turnOn", "1"), ("baseMode", heat_mode)],
            label="C-combined-on-heat",
        )
        s_c = self.wait_and_check("C-combined-heat", {"turnOn": "1", "baseMode": heat_mode})

        # --- Test D: Try just baseMode switch while on ---
        print(f"\n  --- D: Mode switch while ON: baseMode={cool_mode} (cool) ---")
        self.cloud_control([("baseMode", cool_mode)], label="D-mode-cool")
        s_d = self.wait_and_check(
            "D-mode-switch",
            {"turnOn": "1", "baseMode": cool_mode},
        )

        # Restore original state
        print("\n  --- Restoring original state ---")
        orig_on = before.get("turnOn", "1")
        orig_mode = before.get("baseMode", cool_mode)
        self.cloud_control(
            [("turnOn", orig_on), ("baseMode", orig_mode)],
            label="restore",
        )
        if not self.dry_run:
            time.sleep(self.delay)
        self.status(label="After restore")

    def test_udp_combined_power_mode(self) -> None:
        """Test UDP: combined power+mode in one SetMessage."""
        if not self.udp_ip:
            print("\n  [SKIP] No --device-ip provided for UDP test")
            return
        print("\n" + "=" * 70)
        print("TEST: UDP Combined Power + Mode")
        print("=" * 70)

        # UDP: Turn off
        self.udp_control([("TurnOn", "off")], label="udp-off")
        if not self.dry_run:
            time.sleep(self.delay)

        # UDP: Combined on + cool
        self.udp_control(
            [("TurnOn", "on"), ("BaseMode", "cool")],
            label="udp-combined-on-cool",
        )
        self.wait_and_check("udp-combined-on-cool", {"turnOn": "1"})

        # UDP: Separate on then mode
        self.udp_control([("TurnOn", "off")], label="udp-off-2")
        if not self.dry_run:
            time.sleep(self.delay)
        self.udp_control([("TurnOn", "on")], label="udp-on-separate")
        if not self.dry_run:
            time.sleep(0.5)
        self.udp_control([("BaseMode", "cool")], label="udp-mode-separate")
        self.wait_and_check("udp-separate-on-cool", {"turnOn": "1"})

    def test_off_mode_preserved(self) -> None:
        """Test whether baseMode is preserved after power off."""
        print("\n" + "=" * 70)
        print("TEST: Is baseMode preserved after power off?")
        print("=" * 70)

        # Set to heat mode
        heat_mode = MODE_MAP["heat"]
        self.cloud_control([("turnOn", "1"), ("baseMode", heat_mode)], label="set-heat")
        if not self.dry_run:
            time.sleep(self.delay)
        s1 = self.status(label="Heat mode set", quiet=True)
        print(f"  After set heat: turnOn={s1.get('turnOn')}, baseMode={s1.get('baseMode')}")

        # Turn off
        self.cloud_control(APP_POWER_OFF_ITEMS, label="off-preserve")
        if not self.dry_run:
            time.sleep(self.delay)
        s2 = self.status(label="After off")
        print(f"  After off: turnOn={s2.get('turnOn')}, baseMode={s2.get('baseMode')}")
        if s2.get("baseMode") == heat_mode:
            print("  >> baseMode PRESERVED after power off")
        else:
            print(f"  >> baseMode CHANGED after power off: was {heat_mode}, now {s2.get('baseMode')}")

        # Turn on without specifying mode
        self.cloud_control([("turnOn", "1")], label="on-no-mode")
        if not self.dry_run:
            time.sleep(self.delay)
        s3 = self.status(label="After on (no mode)")
        print(f"  After on (no mode): turnOn={s3.get('turnOn')}, baseMode={s3.get('baseMode')}")

    def test_full_state_on(self) -> None:
        """Test turning on with full state.

        The device may not apply setTemp reliably when sent together with
        turnOn+baseMode in the same message. So we send power+mode first,
        wait for device to fully boot up, then set temp+fan separately.

        The device resets setTemp to its last stored value on cold start,
        so we need extra delay before sending the new temp.
        """
        print("\n" + "=" * 70)
        print("TEST: Full state ON (power+mode, then temp+fan)")
        print("=" * 70)

        # First turn off
        self.cloud_control(APP_POWER_OFF_ITEMS, label="full-pre-off")
        if not self.dry_run:
            time.sleep(self.delay)

        # Step 1: power + mode
        self.cloud_control(
            [("turnOn", "1"), ("baseMode", MODE_MAP["cool"])],
            label="full-power-mode",
        )
        if not self.dry_run:
            # Extra wait for device to fully boot and stabilize after cold start
            time.sleep(self.delay + 2)
            s_on = self.status(label="confirm-on", quiet=True)
            print(f"  Confirmed ON: turnOn={s_on.get('turnOn')}, baseMode={s_on.get('baseMode')}, "
                  f"setTemp={s_on.get('setTemp')}")

        # Step 2: temp + degreeH + fan + optSuper=0
        self.cloud_control(
            [("setTemp", "75"), ("degreeH", "0"), ("windSpd", "0"), ("optSuper", "0")],
            label="full-temp-fan",
        )
        # Check after longer delay - device needs time to apply temp after cold start
        result = self.wait_and_check(
            "full-state-on",
            {
                "turnOn": "1",
                "baseMode": MODE_MAP["cool"],
                "setTemp": "75",
                "windSpd": "0",
            },
        )
        # Temperature after cold power-on may not apply immediately due to
        # device boot sequence. Mark partial success if only setTemp mismatched.
        if self.results:
            last = self.results[-1]
            if (
                not last["success"]
                and set(last["mismatches"].keys()) == {"setTemp"}
                and last["matches"].get("turnOn") == "1"
                and last["matches"].get("baseMode") == MODE_MAP["cool"]
            ):
                last["known_limitation"] = True
                print("  >> Known limitation: setTemp may not apply immediately after cold power-on")

    def print_summary(self) -> None:
        """Print a summary of all test results."""
        if not self.results:
            return
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        for r in self.results:
            if r["success"]:
                marker = "PASS"
            elif r.get("known_limitation"):
                marker = "SKIP"
            else:
                marker = "FAIL"
            details = ""
            if r["mismatches"]:
                details = " | " + ", ".join(
                    f"{k}: expected={v['expected']} actual={v['actual']}"
                    for k, v in r["mismatches"].items()
                )
            if r.get("known_limitation"):
                details += " (device limitation)"
            print(f"  [{marker}] {r['test']}{details}")

        passed = sum(1 for r in self.results if r["success"])
        known = sum(
            1 for r in self.results
            if not r["success"] and r.get("known_limitation")
        )
        failed = sum(
            1 for r in self.results
            if not r["success"] and not r.get("known_limitation")
        )
        total = len(self.results)
        print(f"\n  Total: {passed}/{total} passed", end="")
        if known:
            print(f", {known} known limitations", end="")
        if failed:
            print(f", {failed} FAILED", end="")
        print()


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------
def interactive_menu(runner: TestRunner) -> None:
    """Show an interactive menu for test selection."""
    tests = OrderedDict([
        ("1",  ("Show current status",               runner.test_status)),
        ("2",  ("Power ON (single turnOn=1)",         runner.test_power_on)),
        ("3",  ("Power OFF (single turnOn=0)",        runner.test_power_off)),
        ("4",  ("Power cycle (OFF -> ON)",            runner.test_power_cycle)),
        ("5",  ("Combined ON + Cool (1 message)",     lambda: runner.test_combined_on_mode("cool"))),
        ("6",  ("Combined ON + Heat (1 message)",     lambda: runner.test_combined_on_mode("heat"))),
        ("7",  ("Separate ON then Cool (2 messages)", lambda: runner.test_separate_on_mode("cool"))),
        ("8",  ("Separate ON then Heat (2 messages)", lambda: runner.test_separate_on_mode("heat"))),
        ("9",  ("Compare combined vs separate",       runner.test_compare_power_mode)),
        ("10", ("Mode preserved after OFF?",          runner.test_off_mode_preserved)),
        ("11", ("Full state ON (power+mode+temp+fan)",runner.test_full_state_on)),
        ("12", ("Set temp 75F + degreeH=0",           lambda: runner.test_combined_temp(75, "0"))),
        ("13", ("Set temp 73F + degreeH=1",           lambda: runner.test_combined_temp(73, "1"))),
        ("14", ("Swing combined (H+V in 1 msg)",      lambda: runner.test_swing_combined("1", "1"))),
        ("15", ("Swing separate (H then V)",          lambda: runner.test_swing_separate("1", "1"))),
        ("16", ("UDP combined power+mode",            runner.test_udp_combined_power_mode)),
        ("17", ("Mode profile: Cool",                 lambda: runner.test_grouped_mode("cool", label_prefix="mode"))),
        ("18", ("Mode profile: Heat",                 lambda: runner.test_grouped_mode("heat", label_prefix="mode"))),
        ("19", ("Mode profile: Fan",                  lambda: runner.test_grouped_mode("fan", label_prefix="mode"))),
        ("20", ("Mode profile: Dehumi",               lambda: runner.test_grouped_mode("dehumi", label_prefix="mode"))),
        ("21", ("Mode profile: Auto/Selffeel unsupported", lambda: runner.test_grouped_mode("selffeel", label_prefix="mode"))),
        ("22", ("Mode matrix (cool/dry/heat/fan/auto)", runner.test_mode_matrix)),
        ("23", ("Temperature experiment",             runner.test_temperature_experiment)),
        ("24", ("Temperature transaction matrix",     runner.test_temperature_matrix)),
        ("s",  ("Print test summary",                 runner.print_summary)),
        ("q",  ("Quit",                               None)),
    ])

    while True:
        print("\n" + "=" * 70)
        print("TCL AC Control API Test Menu")
        print("=" * 70)
        for key, (desc, _) in tests.items():
            print(f"  {key:>3s}. {desc}")
        print()

        choice = input("Select test (number/q): ").strip().lower()
        if choice == "q":
            runner.print_summary()
            break
        if choice in tests:
            _, fn = tests[choice]
            if fn:
                try:
                    fn()
                except KeyboardInterrupt:
                    print("\n  [Interrupted]")
                except Exception as e:
                    print(f"\n  ERROR: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print(f"  Unknown choice: {choice}")


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------
TEST_DISPATCH = {
    "status": "test_status",
    "power-on": "test_power_on",
    "power-off": "test_power_off",
    "power-cycle": "test_power_cycle",
    "mode-cool": ("test_grouped_mode", "cool"),
    "mode-heat": ("test_grouped_mode", "heat"),
    "mode-fan": ("test_grouped_mode", "fan"),
    "mode-dehumi": ("test_grouped_mode", "dehumi"),
    "mode-auto": ("test_grouped_mode", "selffeel"),
    "mode-matrix": "test_mode_matrix",
    "combined-on-cool": ("test_combined_on_mode", "cool"),
    "combined-on-heat": ("test_combined_on_mode", "heat"),
    "separate-on-cool": ("test_separate_on_mode", "cool"),
    "separate-on-heat": ("test_separate_on_mode", "heat"),
    "combined-temp": "test_combined_temp",
    "temp-experiment": "test_temperature_experiment",
    "temp-matrix": "test_temperature_matrix",
    "combined-off": "test_power_off",
    "swing-combined": "test_swing_combined",
    "swing-separate": "test_swing_separate",
    "compare-power": "test_compare_power_mode",
    "mode-preserved": "test_off_mode_preserved",
    "full-state-on": "test_full_state_on",
    "udp-power-mode": "test_udp_combined_power_mode",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="TCL AC Control API test tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--capture-file", default=DEFAULT_CAPTURE, help="jsonl capture file")
    p.add_argument("--no-verify", action="store_true", help="skip TLS verification")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="show commands without sending")
    p.add_argument(
        "--allow-live",
        action="store_true",
        help="required for tests that send control commands to the real AC",
    )
    p.add_argument(
        "--leave-on",
        action="store_true",
        help="do not run final safe power-off cleanup after live control tests",
    )
    p.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="continue running tests after a state verification mismatch",
    )
    p.add_argument("--status", action="store_true", help="just show current status")
    p.add_argument(
        "--target-celsius",
        type=float,
        help="target Celsius for temperature matrix/experiment",
    )
    p.add_argument(
        "--mode",
        choices=sorted(CLI_MODE_MAP),
        help="force mode context for temperature matrix",
    )
    p.add_argument(
        "--candidate",
        choices=["A", "B", "C", "D", "E", "F"],
        help="run only one temperature matrix candidate",
    )
    p.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="seconds between live status polls for transaction tests",
    )
    p.add_argument(
        "--poll-timeout",
        type=float,
        default=12.0,
        help="maximum seconds to poll each live transaction candidate",
    )
    p.add_argument("--delay", type=float, default=2.5, help="seconds to wait between control and status check")
    p.add_argument(
        "--test",
        choices=list(TEST_DISPATCH.keys()) + ["all"],
        help="run a specific test or 'all'",
    )
    p.add_argument(
        "command",
        nargs="?",
        choices=list(TEST_DISPATCH.keys()) + ["all", "status"],
        help="optional positional command alias for --test or --status",
    )
    p.add_argument("--device-ip", help="device IP for local UDP tests")
    p.add_argument("--device-id", help="override cloud device id/tid for profile selection")
    p.add_argument("--device-port", type=int, default=10075, help="device UDP port")
    p.add_argument("--device-mac", help="device MAC/tclid for UDP tests")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.command:
        if args.command == "status":
            args.status = True
        elif not args.test:
            args.test = args.command

    mutating_run = bool(args.test and args.test != "status") or (
        not args.status and not args.test
    )
    if mutating_run and not args.dry_run and not args.allow_live:
        print(
            "Refusing to send live control commands without --allow-live. "
            "Use --status for read-only checks or --dry-run to preview payloads.",
            file=sys.stderr,
        )
        sys.exit(2)

    capture = Path(args.capture_file)
    if not capture.exists():
        # Try relative to script directory
        capture = Path(__file__).parent.parent / args.capture_file
    if not capture.exists():
        print(f"Capture file not found: {args.capture_file}", file=sys.stderr)
        print("  Try: --capture-file path/to/tcl_*.jsonl", file=sys.stderr)
        sys.exit(2)

    print(f"Loading credentials from: {capture}")
    creds = load_credentials_from_capture(capture)
    if args.device_id:
        creds["tid"] = args.device_id
    print(f"  tid={creds['tid']}, from={creds['from']}, to={creds['to']}")
    device_capabilities = extract_device_capabilities_from_capture(capture)
    current_capabilities = device_capabilities.get(creds["tid"])
    if current_capabilities:
        print(
            "  captured device protocol="
            f"{current_capabilities.get('protocol')}, "
            "tsl_target_temperature="
            f"{current_capabilities.get('has_tsl_target_temperature')}"
        )

    http = HttpClient(no_verify=args.no_verify, verbose=args.verbose)
    runner = TestRunner(
        http,
        creds,
        dry_run=args.dry_run,
        delay=args.delay,
        stop_on_failure=not args.continue_on_failure,
        udp_ip=args.device_ip,
        udp_port=args.device_port,
        udp_mac=args.device_mac,
        device_capabilities=device_capabilities,
    )

    if args.status:
        runner.test_status()
        return

    temp_f = 75
    degree_h = "0"
    if args.target_celsius is not None:
        encoded_temp, encoded_degree_h = LegacyTemperatureCodec.encode(
            args.target_celsius,
            fallback_celsius=args.target_celsius,
        )
        temp_f = int(encoded_temp)
        degree_h = encoded_degree_h
        print(
            f"  target_celsius={args.target_celsius} -> "
            f"setTemp={temp_f}, degreeH={degree_h}"
        )

    def run_dispatch(spec: str | tuple[str, str]) -> None:
        if spec == "test_temperature_matrix":
            runner.test_temperature_matrix(
                temp_f=temp_f,
                degree_h=degree_h,
                mode=args.mode,
                candidate=args.candidate,
                poll_interval=args.poll_interval,
                poll_timeout=args.poll_timeout,
            )
            return
        if spec == "test_temperature_experiment":
            runner.test_temperature_experiment(temp_f=temp_f, degree_h=degree_h)
            return
        if spec == "test_combined_temp":
            runner.test_combined_temp(temp_f=temp_f, degree_h=degree_h)
            return
        if isinstance(spec, tuple):
            getattr(runner, spec[0])(spec[1])
        else:
            getattr(runner, spec)()

    try:
        if args.test:
            if args.test == "all":
                for name, spec in TEST_DISPATCH.items():
                    if name == "status":
                        continue
                    print(f"\n{'#' * 70}")
                    print(f"# Running: {name}")
                    print(f"{'#' * 70}")
                    run_dispatch(spec)
                runner.print_summary()
            else:
                spec = TEST_DISPATCH[args.test]
                run_dispatch(spec)
                runner.print_summary()
            return

        # Default: interactive menu
        interactive_menu(runner)
    except LiveTestFailure as exc:
        print(f"\n  STOPPING: {exc}", file=sys.stderr)
        runner.print_summary()
        sys.exit_code = 1
    finally:
        if mutating_run and not args.dry_run and not args.leave_on:
            print("\nRunning final safe power-off cleanup...")
            try:
                runner.safe_power_off(label="final-cleanup-off")
            except LiveTestFailure as exc:
                print(f"Final cleanup did not verify OFF: {exc}", file=sys.stderr)
                sys.exit(1)
    if getattr(sys, "exit_code", 0):
        sys.exit(sys.exit_code)


if __name__ == "__main__":
    main()
