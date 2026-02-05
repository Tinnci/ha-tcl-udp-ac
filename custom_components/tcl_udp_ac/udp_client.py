"""UDP client for TCL Air Conditioner."""

from __future__ import annotations

import asyncio
import json
import secrets
import socket
import time
import xml.etree.ElementTree as ET
from typing import Any

from .const import (
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
    UDP_BROADCAST_PORT,
    UDP_COMMAND_PORT,
)
from .log_utils import log_info, log_warning

SYNC_THROTTLE_SECONDS = 2.0


class UdpClient:
    """UDP client to isolate local device communication."""

    _HALF_C_IN_F = 0.5 * 9 / 5

    def __init__(
        self,
        action_jid: str,
        action_source: str,
        account: str,
    ) -> None:
        """Initialize UDP client with protocol metadata."""
        self._listener_sock: socket.socket | None = None
        self._send_sock: socket.socket | None = None
        self._listener_transport: asyncio.DatagramTransport | None = None
        self._status_callback: Any = None
        self._last_status: dict[str, Any] = {}
        self._tasks: set[asyncio.Task] = set()
        self._sequence = 0
        self._last_received_seq: str | None = None
        self._device_mac = "00:00:00:00:00:00"
        self._device_ip: str | None = None
        self._device_port: int = UDP_COMMAND_PORT

        self._action_jid = action_jid
        self._action_source = action_source
        self._account = account

    async def async_start_listener(self, status_callback: Any) -> None:
        """Start the UDP listener for broadcast messages."""
        self._status_callback = status_callback
        loop = asyncio.get_running_loop()

        # Create raw socket manually - more reliable than create_datagram_endpoint
        self._listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._listener_sock.setblocking(False)  # noqa: FBT003
        self._listener_sock.bind(("0.0.0.0", UDP_BROADCAST_PORT))  # noqa: S104

        LOGGER.info(
            "UDP socket created: bound to %s", self._listener_sock.getsockname()
        )

        loop.add_reader(self._listener_sock.fileno(), self._on_socket_readable)

        self._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._send_sock.setblocking(False)  # noqa: FBT003
        loop.add_reader(self._send_sock.fileno(), self._on_send_socket_readable)

        self._listener_transport = None

        LOGGER.info(
            "UDP listener started on port %s (using raw socket)", UDP_BROADCAST_PORT
        )

    def _on_socket_readable(self) -> None:
        """Handle readable listener socket."""
        if not self._listener_sock:
            return
        try:
            data, addr = self._listener_sock.recvfrom(4096)
            LOGGER.debug("UDP recv: %d bytes from %s:%d", len(data), addr[0], addr[1])
            self._handle_status_update(data, addr)
        except BlockingIOError:
            pass
        except OSError as exc:  # pragma: no cover - unexpected socket errors
            LOGGER.error("Error reading from socket: %s", exc)

    def _on_send_socket_readable(self) -> None:
        """Handle readable send socket (unicast replies)."""
        if not self._send_sock:
            return
        try:
            data, addr = self._send_sock.recvfrom(4096)
            LOGGER.debug(
                "UDP send socket recv: %d bytes from %s:%d",
                len(data),
                addr[0],
                addr[1],
            )
            self._handle_status_update(data, addr)
        except BlockingIOError:
            pass
        except OSError as exc:  # pragma: no cover - unexpected socket errors
            LOGGER.error("Error reading from send socket: %s", exc)

    async def async_stop_listener(self) -> None:
        """Stop the UDP listener."""
        if self._send_sock:
            loop = asyncio.get_running_loop()
            loop.remove_reader(self._send_sock.fileno())
            self._send_sock.close()
            self._send_sock = None
        if self._listener_sock:
            loop = asyncio.get_running_loop()
            loop.remove_reader(self._listener_sock.fileno())
            self._listener_sock.close()
            self._listener_sock = None
            LOGGER.info("UDP listener stopped")

    def merge_status(self, status: dict[str, Any]) -> None:
        """Merge status into the last known status."""
        self._last_status.update(status)

    def get_last_status(self) -> dict[str, Any]:
        """Get the last received status."""
        return self._last_status

    def _handle_status_update(self, data: bytes, addr: tuple[str, int]) -> None:  # noqa: PLR0912, PLR0915
        """Handle incoming status update from device."""
        try:
            message = data.decode("utf-8")
            sender_ip, sender_port = addr

            if self._device_ip != sender_ip:
                LOGGER.info(
                    "Device IP discovered/changed: %s -> %s", self._device_ip, sender_ip
                )
                self._device_ip = sender_ip
                task = asyncio.create_task(self.async_request_status())
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            if sender_port and sender_port != self._device_port:
                LOGGER.info(
                    "Device port updated from traffic: %d -> %d",
                    self._device_port,
                    sender_port,
                )
                self._device_port = sender_port

            root = ET.fromstring(message)  # noqa: S314
            root_tag = root.tag
            LOGGER.debug("Processing XML root tag: %s", root_tag)

            if root_tag == "deviceInfo":
                LOGGER.info("Received deviceInfo (Discovery response)")
                dev_ip = root.findtext("DevIP") or root.findtext("devIP")
                dev_mac = (
                    root.findtext("DevMAC")
                    or root.findtext("devMac")
                    or root.findtext("devMAC")
                )

                if dev_ip and self._device_ip != dev_ip:
                    LOGGER.info(
                        "Device IP discovered via deviceInfo: %s -> %s",
                        self._device_ip,
                        dev_ip,
                    )
                    self._device_ip = dev_ip

                if dev_mac and self._device_mac != dev_mac:
                    LOGGER.info("Device MAC discovered via deviceInfo: %s", dev_mac)
                    self._device_mac = dev_mac

                dev_port_str = root.findtext("DevPort") or root.findtext("devPort")
                if dev_port_str:
                    try:
                        dev_port = int(dev_port_str)
                        if self._device_port != dev_port:
                            LOGGER.info(
                                "Device port discovered via deviceInfo: %d", dev_port
                            )
                            self._device_port = dev_port
                    except ValueError:
                        pass
                return

            dev_id = root.get("tclid") or root.get("devid")
            if dev_id and dev_id != self._device_mac:
                LOGGER.info("Device MAC discovered via header: %s", dev_id)
                self._device_mac = dev_id
                task = asyncio.create_task(self.async_request_status())
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            msg_type = (root.get("type") or "").lower()
            msg_cmd = (root.get("cmd") or "").lower()
            if msg_cmd == "status" or msg_type == "notify":
                current_seq = root.get("seq")
                if current_seq is not None and current_seq == self._last_received_seq:
                    LOGGER.debug("Ignoring duplicate seq: %s", current_seq)
                    return
                self._last_received_seq = current_seq
                LOGGER.debug("UDP Raw Payload from %s: %s", addr[0], message)

                status_msg = root.find("statusUpdateMsg") or root.find(
                    "StatusUpdateMsg"
                )
                if status_msg is not None:
                    status = self._parse_status(status_msg)
                    self.merge_status(status)
                    LOGGER.debug("Applied state updates: %s", status)
                    LOGGER.debug("Full Current Status: %s", self._last_status)

                    if self._status_callback:
                        task = asyncio.create_task(
                            self._status_callback(self._last_status)
                        )
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)
                else:
                    LOGGER.warning(
                        "Received status message but no statusUpdateMsg found in XML"
                    )
            else:
                LOGGER.debug("UDP Raw Payload from %s: %s", addr[0], message)
                LOGGER.debug(
                    "Ignored XML msg (not status/notify): cmd=%s, type=%s",
                    msg_cmd,
                    msg_type,
                )

        except ET.ParseError as exception:
            LOGGER.error("Error parsing XML status message: %s", exception)
        except UnicodeDecodeError as exception:
            LOGGER.error("Error decoding status message: %s", exception)
        except (KeyError, AttributeError) as exception:
            LOGGER.error("Error processing status message: %s", exception)

    def _get_node_value(self, node: ET.Element | None) -> str | None:
        """Extract value from node, handling both <tag value='x'> and <tag>x</tag>."""
        if node is None:
            return None
        val = node.get("value")
        if val is None:
            val = node.text
        return val

    def _parse_bool_feature(
        self, status_msg: ET.Element, tag: str, status_key: str, status: dict[str, Any]
    ) -> None:
        """Parse boolean features from both XML formats."""
        node = status_msg.find(tag) or status_msg.find(tag[0].lower() + tag[1:])
        val = self._get_node_value(node)
        if val is not None:
            status[status_key] = val.lower() == "on" or val == "1"

    def _parse_status(self, status_msg: ET.Element) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915
        """Parse status message XML, supporting multiple formats."""
        status: dict[str, Any] = {}
        parsed_tags = set()

        def get_and_record(tag_names: list[str]) -> ET.Element | None:
            for name in tag_names:
                node = status_msg.find(name)
                if node is not None:
                    parsed_tags.add(node.tag)
                    return node
            return None

        node = get_and_record(["TurnOn", "turnOn", "Power", "power"])
        val = self._get_node_value(node)
        if val:
            status["power"] = val.lower() == "on" or val == "1"

        node = get_and_record(["SetTemp", "setTemp"])
        val = self._get_node_value(node)
        if val:
            try:
                status["target_temp"] = int(val)
            except ValueError:
                LOGGER.warning("Invalid SetTemp value: %s", val)

        degree_half = None
        node = get_and_record(["DegreeH", "degreeH", "degreeh"])
        val = self._get_node_value(node)
        if val is not None:
            degree_half = val.lower() == "on" or val == "1"
        if degree_half and "target_temp" in status:
            status["target_temp"] = round(
                float(status["target_temp"]) + self._HALF_C_IN_F,
                1,
            )

        node = get_and_record(["InTemp", "inTemp", "IndoorTemp", "indoorTemp"])
        val = self._get_node_value(node)
        if val:
            try:
                status["current_temp"] = int(val)
            except ValueError:
                LOGGER.warning("Invalid InTemp value: %s", val)

        node = get_and_record(["OutTemp", "outTemp", "OutdoorTemp", "outdoorTemp"])
        val = self._get_node_value(node)
        if val:
            try:
                status["outdoor_temp"] = int(val)
            except ValueError:
                LOGGER.warning("Invalid OutTemp value: %s", val)

        def parse_bool(tags: list[str], key: str) -> None:
            node = get_and_record(tags)
            val = self._get_node_value(node)
            if val is not None:
                status[key] = val.lower() == "on" or val == "1"

        parse_bool(["OptECO", "optECO", "Opt_ECO"], "eco_mode")
        parse_bool(["OptDisplay", "optDisplay", "Opt_display"], "display")
        parse_bool(["OptHealthy", "optHealthy", "Opt_healthy"], "health_mode")
        parse_bool(["Opt_sleepMode", "sleepMode", "SleepMode"], "sleep_mode")
        parse_bool(["Opt_super", "superMode", "SuperMode", "OptSuper"], "turbo_mode")
        parse_bool(["OptHeat", "optHeat", "Opt_heat"], "aux_heat")
        parse_bool(["BeepEnable", "beepEn", "BeepEn"], "beep")

        node = get_and_record(["WindSpeed", "windSpd", "WindSpd"])
        val = self._get_node_value(node)
        if val:
            v = val.lower()
            if v in {"0", "1", "2", "3"}:
                wind_map = {
                    "0": FAN_AUTO,
                    "1": FAN_HIGH,
                    "2": FAN_MIDDLE,
                    "3": FAN_LOW,
                }
                status["fan_speed"] = wind_map.get(v, FAN_AUTO)
            elif v == "high":
                status["fan_speed"] = FAN_HIGH
            elif v == "middle":
                status["fan_speed"] = FAN_MIDDLE
            elif v == "low":
                status["fan_speed"] = FAN_LOW
            elif v == "auto":
                status["fan_speed"] = FAN_AUTO
            else:
                status["fan_speed"] = v

        parse_bool(["WindDirection_H", "directH", "directh"], "swing_h")
        parse_bool(["WindDirection_V", "directV", "directv"], "swing_v")

        node = get_and_record(["BaseMode", "baseMode", "Mode", "mode"])
        val = self._get_node_value(node)
        if val:
            v = val.lower()
            if v == "cool":
                status["mode"] = MODE_COOL
            elif v == "heat":
                status["mode"] = MODE_HEAT
            elif v == "fan":
                status["mode"] = MODE_FAN
            elif v == "dehumi":
                status["mode"] = MODE_DEHUMI
            elif v == "selffeel":
                status["mode"] = MODE_AUTO
            else:
                status["mode"] = v

        for child in status_msg:
            if child.tag not in parsed_tags and child.tag not in [
                "actionSource",
                "action_source",
            ]:
                LOGGER.debug(
                    "Unknown tag in statusUpdateMsg: %s = %s",
                    child.tag,
                    self._get_node_value(child),
                )

        return status

    async def async_send_command(
        self,
        command: str,
        value: str,
        degree_half: int | None = None,
    ) -> None:
        """Send a command using SetMessage XML format (UDP only)."""
        self._sequence += 1
        seq = str(self._sequence)

        extra_xml = ""
        if command == "SetTemp" and degree_half is not None:
            extra_xml = f"<DegreeH>{degree_half}</DegreeH>"

        xml_command = (
            f'<msg tclid="{self._device_mac}" msgid="SetMessage" '
            f'type="Control" seq="{seq}">'
            f"<SetMessage>"
            f"<{command}>{value}</{command}>"
            f"{extra_xml}"
            f"</SetMessage>"
            f"</msg>"
        )

        LOGGER.debug("Sending SetMessage: %s", xml_command)

        if self._device_ip and self._device_port and self._send_sock:
            target_addr = (self._device_ip, self._device_port)
            log_info(
                LOGGER,
                "udp_control_sent",
                command=command,
                value=value,
                seq=seq,
                ip=target_addr[0],
                port=target_addr[1],
            )
            self._send_sock.sendto(xml_command.encode("utf-8"), target_addr)
        else:
            log_warning(
                LOGGER,
                "udp_control_skipped",
                command=command,
                value=value,
                reason="device_not_discovered",
            )

    async def async_send_discovery(self) -> None:
        """Send a discovery packet to find devices."""
        if not self._send_sock:
            return
        try:
            self._sequence += 1
            xml_command = '<message msgid="SearchDevice"></message>'

            LOGGER.debug("Sending Discovery: %s", xml_command)

            self._send_sock.sendto(
                xml_command.encode("utf-8"),
                ("<broadcast>", UDP_COMMAND_PORT),
            )

            if self._device_ip:
                tcl_id_attr = ""
                if self._device_mac and self._device_mac != "00:00:00:00:00:00":
                    tcl_id_attr = f' tclid="{self._device_mac}"'

                sync_xml = (
                    f'<msg{tcl_id_attr} msgid="SyncStatusReq" '
                    f'type="Notify" seq="{self._sequence}">'
                    f"<SyncStatusReq></SyncStatusReq></msg>"
                )
                self._send_sock.sendto(
                    sync_xml.encode("utf-8"),
                    (self._device_ip, self._device_port),
                )

            json_search = json.dumps(
                {
                    "msgId": str(secrets.randbelow(9000) + 1000),
                    "version": "123",
                    "method": "searchReq",
                }
            )
            self._send_sock.sendto(
                json_search.encode("utf-8"),
                ("<broadcast>", UDP_COMMAND_PORT),
            )
            LOGGER.debug("Sent discovery (XML and JSON)")

        except OSError as exception:
            LOGGER.warning("Failed to send discovery packet: %s", exception)

    async def async_request_status(self) -> None:
        """Explicitly request a full status update from the device (SyncStatusReq)."""
        if not self._send_sock:
            return
        if not self._device_ip:
            await self.async_send_discovery()
            return

        now = time.time()
        if (
            hasattr(self, "_last_sync_time")
            and now - self._last_sync_time < SYNC_THROTTLE_SECONDS
        ):
            return
        self._last_sync_time = now

        try:
            self._sequence += 1
            tcl_id_attr = ""
            if self._device_mac and self._device_mac != "00:00:00:00:00:00":
                tcl_id_attr = f' tclid="{self._device_mac}"'

            for msg_type in ["Control", "Notify"]:
                xml = (
                    f'<msg{tcl_id_attr} msgid="SyncStatusReq" '
                    f'type="{msg_type}" seq="{self._sequence}">'
                    f"<SyncStatusReq></SyncStatusReq></msg>"
                )
                LOGGER.debug(
                    "Sending SyncStatusReq (%s) to %s (MAC: %s)",
                    msg_type,
                    self._device_ip,
                    self._device_mac,
                )
                self._send_sock.sendto(
                    xml.encode("utf-8"),
                    (self._device_ip, self._device_port),
                )
        except OSError as exception:
            LOGGER.error("Failed to send SyncStatusReq: %s", exception)

    async def async_close(self) -> None:
        """Close UDP client and cancel tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        await self.async_stop_listener()
