"""UDP API Client for TCL Air Conditioner."""

from __future__ import annotations

import asyncio
import json
import secrets
import socket
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


class TclUdpApiClientError(Exception):
    """Exception to indicate a general API error."""


class TclUdpApiClientCommunicationError(TclUdpApiClientError):
    """Exception to indicate a communication error."""


class TclUdpApiClient:
    """TCL UDP API Client for local communication."""

    def __init__(
        self,
        action_jid: str = "homeassistant@tcl.com/ha-plugin",
        action_source: str = "1",
        account: str = "homeassistant",
    ) -> None:
        """Initialize the API client."""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._listener_sock: socket.socket | None = None
        self._listener_transport: asyncio.DatagramTransport | None = (
            None  # Keep for compatibility
        )
        self._status_callback: Any = None
        self._last_status: dict[str, Any] = {}
        self._tasks: set[asyncio.Task] = set()

        # Configurable protocol fields
        self._action_jid = action_jid
        self._action_source = action_source
        self._account = account
        self._sequence = 0
        self._device_mac = "00:00:00:00:00:00"  # Will be discovered
        self._device_ip: str | None = None  # Will be discovered
        self._device_port: int = 10075  # Default, may be updated from deviceInfo

    async def async_start_listener(self, status_callback: Any) -> None:
        """Start the UDP listener for broadcast messages."""
        self._status_callback = status_callback
        # Use get_running_loop() in async context - more reliable than get_event_loop()
        loop = asyncio.get_running_loop()
        self._loop = loop

        try:
            # Create raw socket manually - more reliable than create_datagram_endpoint
            # in some environments (especially Docker containers)
            self._listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._listener_sock.setblocking(flag=False)
            self._listener_sock.bind(("0.0.0.0", UDP_BROADCAST_PORT))  # noqa: S104

            LOGGER.debug("UDP socket bound to %s", self._listener_sock.getsockname())

            # Use add_reader for direct event loop integration
            # This bypasses asyncio's DatagramProtocol which may have issues
            loop.add_reader(self._listener_sock.fileno(), self._on_socket_readable)

            # Store transport reference for sending (will use the same socket)
            self._listener_transport = None  # Not using transport anymore

            LOGGER.info(
                "UDP listener started on port %s (using raw socket)", UDP_BROADCAST_PORT
            )
        except OSError as exception:
            msg = f"Failed to start UDP listener: {exception}"
            raise TclUdpApiClientCommunicationError(msg) from exception

    def _on_socket_readable(self) -> None:
        """Handle readable socket events."""
        if not self._listener_sock:
            return
        try:
            data, addr = self._listener_sock.recvfrom(4096)
            LOGGER.debug("Received %d bytes from %s", len(data), addr)
            self._handle_status_update(data, addr)
        except BlockingIOError:
            return
        except OSError as exc:
            LOGGER.error("Error reading from socket: %s", exc)

    async def async_stop_listener(self) -> None:
        """Stop the UDP listener."""
        if self._listener_sock:
            if self._loop:
                self._loop.remove_reader(self._listener_sock.fileno())
            self._listener_sock.close()
            self._listener_sock = None
            LOGGER.info("UDP listener stopped")

    def _handle_status_update(  # noqa: PLR0912
        self, data: bytes, addr: tuple[str, int]
    ) -> None:
        """Handle incoming status update from device."""
        try:
            message = data.decode("utf-8")
            # Log to verify packets are being received
            LOGGER.debug("Received UDP message from %s: %s", addr, message)

            # Update Device IP from the sender's address
            sender_ip = addr[0]
            if self._device_ip != sender_ip:
                LOGGER.info(
                    "Device IP discovered/changed: %s -> %s", self._device_ip, sender_ip
                )
                self._device_ip = sender_ip

            # Parse XML - Local network only
            # Using defusedxml would be safer but for local network this is acceptable
            root = ET.fromstring(message)  # noqa: S314

            # Check if it's a deviceInfo response (Discovery)
            if root.tag == "deviceInfo":
                # Java protocol uses PascalCase (DevIP, DevMac, DevPort),
                # but old logs saw camelCase. We check both for robustness.
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

                # Save device port from deviceInfo (CRITICAL for control)
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

            # Capture device MAC if available in msg header
            # Java: tclid, Old: devid
            dev_id = root.get("tclid") or root.get("devid")
            if dev_id and dev_id != self._device_mac:
                LOGGER.info("Device MAC discovered via header: %s", dev_id)
                self._device_mac = dev_id

            # Check if it's a status message
            # Matches cmd="status" (old) or type="Notify" (new/Java)
            if root.get("cmd") == "status" or root.get("type") == "Notify":
                status_msg = root.find("statusUpdateMsg") or root.find(
                    "StatusUpdateMsg"
                )
                if status_msg is not None:
                    status = self._parse_status(status_msg)
                    self._last_status = status
                    LOGGER.debug("Parsed status: %s", status)

                    # Call the callback with new status
                    if self._status_callback:
                        task = asyncio.create_task(self._status_callback(status))
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)
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
        # Try attribute first (old style)
        val = node.get("value")
        if val is None:
            # Try text content (new/Java style)
            val = node.text
        return val

    def _parse_bool_feature(
        self, status_msg: ET.Element, tag: str, status_key: str, status: dict[str, Any]
    ) -> None:
        """Parse boolean features from multiple XML formats."""
        # Try PascalCase (Java) and camelCase (Old)
        node = status_msg.find(tag) or status_msg.find(tag[0].lower() + tag[1:])
        val = self._get_node_value(node)

        if val is not None:
            # Handle 'on'/'off' and '1'/'0'
            status[status_key] = val.lower() == "on" or val == "1"

    def _parse_status(  # noqa: PLR0912, PLR0915
        self, status_msg: ET.Element
    ) -> dict[str, Any]:
        """Parse status message XML, supporting multiple formats."""
        status = {}

        # Parse power state (TurnOn/turnOn)
        node = status_msg.find("TurnOn") or status_msg.find("turnOn")
        val = self._get_node_value(node)
        if val:
            status["power"] = val.lower() == "on" or val == "1"

        # Parse set temperature (SetTemp/setTemp)
        node = status_msg.find("SetTemp") or status_msg.find("setTemp")
        val = self._get_node_value(node)
        if val:
            try:
                temp_val = int(val)
                status["target_temp"] = temp_val
            except ValueError:
                LOGGER.warning("Invalid SetTemp value: %s", val)

        # Parse indoor temperature (InTemp/inTemp)
        node = status_msg.find("InTemp") or status_msg.find("inTemp")
        val = self._get_node_value(node)
        if val:
            try:
                temp_val = int(val)
                status["current_temp"] = temp_val
            except ValueError:
                LOGGER.warning("Invalid InTemp value: %s", val)

        # Parse outdoor temperature (OutTemp/outTemp)
        node = status_msg.find("OutTemp") or status_msg.find("outTemp")
        val = self._get_node_value(node)
        if val:
            try:
                temp_val = int(val)
                status["outdoor_temp"] = temp_val
            except ValueError:
                LOGGER.warning("Invalid OutTemp value: %s", val)

        # Parse boolean features using helper (handles case variations)
        self._parse_bool_feature(status_msg, "OptECO", "eco_mode", status)
        self._parse_bool_feature(status_msg, "OptDisplay", "display", status)
        self._parse_bool_feature(status_msg, "OptHealthy", "health_mode", status)
        self._parse_bool_feature(
            status_msg, "Opt_sleepMode", "sleep_mode", status
        )  # Java tag uses underscore
        self._parse_bool_feature(status_msg, "Opt_super", "turbo_mode", status)
        self._parse_bool_feature(status_msg, "BeepEnable", "beep", status)
        # Parse fan speed (WindSpeed/windSpd)
        node = status_msg.find("WindSpeed") or status_msg.find("windSpd")
        val = self._get_node_value(node)
        if val:
            # Map string values to HA integers or keep strings?
            # Integration expects integers 0-3 usually? Let's check consumer.
            # Wait, `fan_speed` in HA implies mode.
            # Java values: high, middle, low, auto
            # Mapping: high=3, middle=2, low=1, auto=0 (example)
            v = val.lower()
            if v == "high":
                status["fan_speed"] = FAN_HIGH
            elif v == "middle":
                status["fan_speed"] = FAN_MIDDLE
            elif v == "low":
                status["fan_speed"] = FAN_LOW
            elif v == "auto":
                status["fan_speed"] = FAN_AUTO
            else:
                status["fan_speed"] = v  # Fallback

        # Parse swing mode (WindDirection_H/V or directH/V)
        node_h = status_msg.find("WindDirection_H") or status_msg.find("directH")
        val_h = self._get_node_value(node_h)
        if val_h:
            status["swing_h"] = val_h.lower() == "on" or val_h == "1"

        node_v = status_msg.find("WindDirection_V") or status_msg.find("directV")
        val_v = self._get_node_value(node_v)
        if val_v:
            status["swing_v"] = val_v.lower() == "on" or val_v == "1"

        # Parse mode (BaseMode/baseMode)
        node = status_msg.find("BaseMode") or status_msg.find("baseMode")
        val = self._get_node_value(node)
        if val:
            # Java values: cool, heat, fan, dehumi, selffeel
            # Mapping to integers expected by Entity?
            # Looking at previous code, it expected int(value).
            # We need to map string back to int if entity expects int.
            v = val.lower()
            # 1=cool, 2=heat, 3=fan, 4=dry, 5=auto (Standard guess)
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
                status["mode"] = v  # Fallback

        return status

    async def async_send_command(self, command: str, value: str) -> None:
        """
        Send a command using SetMessage XML format (per Java source code).

        Args:
            command: XML tag name (e.g., 'TurnOn', 'SetTemp', 'BaseMode')
            value: Tag value (e.g., 'on', 'off', '78', 'cool')

        """
        try:
            self._sequence += 1
            seq = str(self._sequence)

            # Construct SetMessage XML (from UdpComm.java / TclDeviceSendTool.java)
            # <msg tclid="MAC" msgid="SetMessage" type="Control" seq="123">
            #   <SetMessage>
            #     <TurnOn>on</TurnOn>
            #   </SetMessage>
            # </msg>
            xml_command = (
                f'<msg tclid="{self._device_mac}" msgid="SetMessage" '
                f'type="Control" seq="{seq}">'
                f"<SetMessage>"
                f"<{command}>{value}</{command}>"
                f"</SetMessage>"
                f"</msg>"
            )

            LOGGER.debug("Sending SetMessage: %s", xml_command)

            if not self._listener_sock:
                LOGGER.warning("UDP listener not started. Cannot send command.")
                return

            # Send to discovered device port (mandatory per Java logic)
            if self._device_ip and self._device_port:
                target_addr = (self._device_ip, self._device_port)
                LOGGER.debug("Sending to %s:%d", target_addr[0], target_addr[1])
                self._listener_sock.sendto(xml_command.encode("utf-8"), target_addr)
            else:
                LOGGER.warning("Device not discovered. Cannot send command.")

        except OSError as exception:
            LOGGER.error("Failed to send command: %s", exception)
            if self._device_ip:
                LOGGER.warning("Clearing discovered IP after failure")
                self._device_ip = None
            raise TclUdpApiClientCommunicationError from exception

    async def async_set_power(self, *, power: bool) -> None:
        """Set power on/off."""
        # Java: <TurnOn>on</TurnOn> or <TurnOn>off</TurnOn>
        await self.async_send_command("TurnOn", "on" if power else "off")

    async def async_set_temperature(self, temperature: int) -> None:
        """Set target temperature (converts Celsius to Fahrenheit)."""
        # Java: <SetTemp>78</SetTemp> (Fahrenheit integer)
        fahrenheit = int(temperature * 9 / 5 + 32)
        await self.async_send_command("SetTemp", str(fahrenheit))

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

    async def async_set_beep(self, *, enabled: bool) -> None:
        """Set beep on/off."""
        # Java: <BeepEnable>on</BeepEnable>
        await self.async_send_command("BeepEnable", "on" if enabled else "off")

    async def async_send_discovery(self) -> None:
        """Send a discovery packet to find devices."""
        try:
            if not self._listener_sock:
                LOGGER.warning("UDP listener not started. Cannot send discovery.")
                return

            self._sequence += 1
            # Java: sendMulticast() -> <message msgid="SearchDevice"></message>
            xml_command = '<message msgid="SearchDevice"></message>'

            LOGGER.debug("Sending Discovery: %s", xml_command)

            self._listener_sock.sendto(
                xml_command.encode("utf-8"),
                ("<broadcast>", UDP_COMMAND_PORT),  # 10075
            )

            # JSON Discovery (Optional/Alternative seen in some packet dumps)
            # Keeping it as a backup but Java source relies on XML.
            json_search = json.dumps(
                {
                    "msgId": str(secrets.randbelow(9000) + 1000),
                    "version": "123",
                    "method": "searchReq",
                }
            )
            self._listener_sock.sendto(
                json_search.encode("utf-8"),
                ("<broadcast>", UDP_COMMAND_PORT),
            )

            LOGGER.debug("Sent discovery (XML and JSON)")
        except OSError as exception:
            LOGGER.warning("Failed to send discovery packet: %s", exception)

    def get_last_status(self) -> dict[str, Any]:
        """Get the last received status."""
        return self._last_status

    async def async_close(self) -> None:
        """Close the API client."""
        # Cancel all pending tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete/cancel
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        await self.async_stop_listener()
        self._loop = None


class UDPListenerProtocol(asyncio.DatagramProtocol):
    """UDP listener protocol."""

    def __init__(self, callback: Any) -> None:
        """Initialize the protocol."""
        self._callback = callback

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle received datagram."""
        LOGGER.debug("UDP datagram received from %s, %d bytes", addr, len(data))
        self._callback(data, addr)
