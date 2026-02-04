"""UDP API Client for TCL Air Conditioner."""

from __future__ import annotations

import asyncio
import socket
import xml.etree.ElementTree as ET
from typing import Any

from .const import LOGGER, UDP_BROADCAST_PORT, UDP_COMMAND_PORT


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
        self._listener_transport: asyncio.DatagramTransport | None = None
        self._listener_protocol: UDPListenerProtocol | None = None
        self._command_sock: socket.socket | None = None
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

    async def async_start_listener(self, status_callback: Any) -> None:
        """Start the UDP listener for broadcast messages."""
        self._status_callback = status_callback
        loop = asyncio.get_event_loop()

        try:
            # Create socket with broadcast capability
            # This socket will be used for both receiving and sending
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # CRITICAL for sending broadcasts
            sock.bind(("0.0.0.0", UDP_BROADCAST_PORT))
            sock.setblocking(False)
            
            # Create UDP listener using our pre-configured socket
            self._listener_protocol = UDPListenerProtocol(self._handle_status_update)
            self._listener_transport, _ = await loop.create_datagram_endpoint(
                lambda: self._listener_protocol,
                sock=sock,  # Use our socket instead of local_addr
            )
            LOGGER.info("UDP listener started on port %s", UDP_BROADCAST_PORT)
        except OSError as exception:
            msg = f"Failed to start UDP listener: {exception}"
            raise TclUdpApiClientCommunicationError(msg) from exception

    async def async_stop_listener(self) -> None:
        """Stop the UDP listener."""
        if self._listener_transport:
            self._listener_transport.close()
            self._listener_transport = None
            LOGGER.info("UDP listener stopped")

    def _handle_status_update(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming status update from device."""
        try:
            message = data.decode("utf-8")
            # Log to verify packets are being received
            LOGGER.debug("Received UDP message from %s: %s", addr, message)

            # Update Device IP from the sender's address
            # addr is (ip, port)
            sender_ip = addr[0]
            if self._device_ip != sender_ip:
                LOGGER.info("Device IP discovered/changed: %s -> %s", self._device_ip, sender_ip)
                self._device_ip = sender_ip

            # Parse XML - Local network only, using safe parser
            # Disable entity resolution to prevent XML attacks
            parser = ET.XMLParser()  # noqa: S314
            parser.entity = {}  # Disable entity resolution
            root = ET.fromstring(message, parser=parser)  # noqa: S314

            # Check if it's a deviceInfo response (Discovery)
            if root.tag == "deviceInfo":
                dev_ip = root.findtext("devIP")
                dev_mac = root.findtext("devMac")
                
                if dev_ip and self._device_ip != dev_ip:
                    LOGGER.info("Device IP discovered via deviceInfo: %s -> %s", self._device_ip, dev_ip)
                    self._device_ip = dev_ip
                
                if dev_mac and self._device_mac != dev_mac:
                    LOGGER.info("Device MAC discovered via deviceInfo: %s", dev_mac)
                    self._device_mac = dev_mac
                return

            # Capture device MAC if available (standard msg)
            dev_id = root.get("devid")
            if dev_id and dev_id != self._device_mac:
                LOGGER.info("Device MAC discovered via header: %s", dev_id)
                self._device_mac = dev_id

            # Check if it's a status message
            if root.get("cmd") == "status":
                status_msg = root.find("statusUpdateMsg")
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

        return status

    def _parse_bool_feature(self, status_msg: ET.Element, tag: str, status_key: str, status: dict[str, Any]) -> None:
        """Helper to parse boolean features."""
        node = status_msg.find(tag)
        if node is not None:
             status[status_key] = node.get("value") == "1"

    def _parse_status(self, status_msg: ET.Element) -> dict[str, Any]:
        """Parse status message XML."""
        status = {}

        # Parse power state
        turn_on = status_msg.find("turnOn")
        if turn_on is not None:
            status["power"] = turn_on.get("value") == "1"

        # Parse set temperature
        set_temp = status_msg.find("setTemp")
        if set_temp is not None:
            try:
                status["target_temp"] = int(set_temp.get("value", "0"))
            except ValueError:
                LOGGER.warning("Invalid setTemp value")

        # Parse indoor temperature
        in_temp = status_msg.find("inTemp")
        if in_temp is not None:
            try:
                status["current_temp"] = int(in_temp.get("value", "0"))
            except ValueError:
                LOGGER.warning("Invalid inTemp value")

        # Parse outdoor temperature
        out_temp = status_msg.find("outTemp")
        if out_temp is not None:
            try:
                # 176 is often used as a default/invalid value in some protocols
                # We interpret it as is, entity layer can filter if needed
                status["outdoor_temp"] = int(out_temp.get("value", "0"))
            except ValueError:
                LOGGER.warning("Invalid outTemp value")

        # Parse boolean features
        self._parse_bool_feature(status_msg, "optECO", "eco_mode", status)
        self._parse_bool_feature(status_msg, "optDisplay", "display", status)
        self._parse_bool_feature(status_msg, "optHealthy", "health_mode", status)
        self._parse_bool_feature(status_msg, "optSleepMd", "sleep_mode", status)
        self._parse_bool_feature(status_msg, "optSuper", "turbo_mode", status)
        self._parse_bool_feature(status_msg, "beepEn", "beep", status)

        # Parse fan speed (windSpd)
        wind_spd = status_msg.find("windSpd")
        if wind_spd is not None:
             try:
                status["fan_speed"] = int(wind_spd.get("value", "0"))
             except ValueError:
                LOGGER.warning("Invalid windSpd value")

        # Parse swing mode (directH/directV)
        direct_h = status_msg.find("directH")
        if direct_h is not None:
            status["swing_h"] = direct_h.get("value") == "1"

        direct_v = status_msg.find("directV")
        if direct_v is not None:
            status["swing_v"] = direct_v.get("value") == "1"

        # Parse mode (baseMode)
        base_mode = status_msg.find("baseMode")
        if base_mode is not None:
            try:
                status["mode"] = int(base_mode.get("value", "0"))
            except ValueError:
                LOGGER.warning("Invalid baseMode value")

        return status

    async def async_send_command(self, command: str, value: str) -> None:
        """Send a command to the device."""
        try:
            self._sequence += 1
            seq = str(self._sequence)
            
            # Construct full spoofed XML packet
            # Strict ordering: cmd -> type -> seq -> devid
            xml_command = (
                f'<msg cmd="control" type="control" seq="{seq}" devid="{self._device_mac}">'
                f'<control>'
                f'<actionJid value="{self._action_jid}"/>'
                f'<actionSource value="{self._action_source}"/>'
                f'<account value="{self._account}"/>'
                f'<{command} value="{value}"/>'
                f'</control>'
                f'</msg>'
            )
            
            LOGGER.debug("Sending command: %s", xml_command)

            # Determine target address
            target_addr = ("<broadcast>", UDP_COMMAND_PORT)
            if self._device_ip:
                target_addr = (self._device_ip, UDP_COMMAND_PORT)
                LOGGER.debug("Sending command to %s (Unicast): %s", self._device_ip, xml_command)
            else:
                LOGGER.debug("Sending command to Broadcast: %s", xml_command)

            # Send via UDP using listener transport
            # This ensures we send from port 10074 (same port we listen on)
            # so the AC will reply to the correct port
            self._listener_transport.sendto(
                xml_command.encode("utf-8"),
                target_addr,
            )
        except OSError as exception:
            msg = f"Error sending command: {exception}"
            # If unicast fails, we might want to clear IP and try broadcast next time
            # For now, just raise
            if self._device_ip:
                 LOGGER.warning("Unicast failed to %s, clearing discovered IP. Error: %s", self._device_ip, exception)
                 self._device_ip = None
            raise TclUdpApiClientCommunicationError(msg) from exception



    async def async_set_power(self, *, power_on: bool) -> None:
        """Turn the AC on or off."""
        value = "1" if power_on else "0"
        await self.async_send_command("turnOn", value)

    async def async_set_temperature(self, temperature: int) -> None:
        """Set target temperature."""
        await self.async_send_command("setTemp", str(temperature))

    async def async_set_fan_speed(self, speed: int) -> None:
        """Set fan speed."""
        await self.async_send_command("windSpd", str(speed))

    async def async_set_swing(self, vertical: bool, horizontal: bool) -> None:
        """Set swing mode."""
        # This might need refinement based on exact protocol behavior
        await self.async_send_command("directV", "1" if vertical else "0")
        await self.async_send_command("directH", "1" if horizontal else "0")

    async def async_set_mode(self, mode: int) -> None:
        """Set operation mode."""
        await self.async_send_command("baseMode", str(mode))

    async def async_set_eco_mode(self, enabled: bool) -> None:
        """Set ECO mode."""
        await self.async_send_command("optECO", "1" if enabled else "0")

    async def async_set_display(self, enabled: bool) -> None:
        """Set display on/off."""
        await self.async_send_command("optDisplay", "1" if enabled else "0")

    async def async_set_health_mode(self, enabled: bool) -> None:
        """Set health mode."""
        await self.async_send_command("optHealthy", "1" if enabled else "0")

    async def async_set_sleep_mode(self, enabled: bool) -> None:
        """Set sleep mode."""
        await self.async_send_command("optSleepMd", "1" if enabled else "0")

    async def async_set_turbo_mode(self, enabled: bool) -> None:
        """Set turbo (super) mode."""
        await self.async_send_command("optSuper", "1" if enabled else "0")

    async def async_set_beep(self, enabled: bool) -> None:
        """Set beep on/off."""
        await self.async_send_command("beepEn", "1" if enabled else "0")

    async def async_send_discovery(self) -> None:
        """Send a discovery packet to find devices."""
        try:
            self._sequence += 1
            seq = str(self._sequence)
            
            # Discovery command
            # Using type="get" to request status. 
            # devid is unknown so using default or empty.
            # Discovery command
            # Confirmed via pcap: The device responds to <searchDevice></searchDevice>
            # It also responds to JSON but we use XML.
            xml_command = '<searchDevice></searchDevice>'
            
            LOGGER.debug("Sending discovery: %s", xml_command)

            # Send via UDP Broadcast using listener transport
            self._listener_transport.sendto(
                xml_command.encode("utf-8"),
                ("<broadcast>", UDP_COMMAND_PORT),
            )
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
        if self._command_sock:
            self._command_sock.close()
            self._command_sock = None


class UDPListenerProtocol(asyncio.DatagramProtocol):
    """UDP listener protocol."""

    def __init__(self, callback: Any) -> None:
        """Initialize the protocol."""
        self._callback = callback

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle received datagram."""
        self._callback(data, addr)
