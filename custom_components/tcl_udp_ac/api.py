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

    def __init__(self) -> None:
        """Initialize the API client."""
        self._listener_transport: asyncio.DatagramTransport | None = None
        self._listener_protocol: UDPListenerProtocol | None = None
        self._command_sock: socket.socket | None = None
        self._status_callback: Any = None
        self._last_status: dict[str, Any] = {}
        self._tasks: set[asyncio.Task] = set()

    async def async_start_listener(self, status_callback: Any) -> None:
        """Start the UDP listener for broadcast messages."""
        self._status_callback = status_callback
        loop = asyncio.get_event_loop()

        try:
            # Create UDP listener
            self._listener_protocol = UDPListenerProtocol(self._handle_status_update)
            self._listener_transport, _ = await loop.create_datagram_endpoint(
                lambda: self._listener_protocol,
                local_addr=("0.0.0.0", UDP_BROADCAST_PORT),  # noqa: S104
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
            LOGGER.debug("Received UDP message from %s: %s", addr, message)

            # Parse XML - Local network only, trusted source
            root = ET.fromstring(message)  # noqa: S314

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

        return status

    async def async_send_command(self, command: str, value: str) -> None:
        """Send a command to the device."""
        try:
            # Build XML command
            xml_command = f'<msg cmd="control"><{command} value="{value}"/></msg>'
            LOGGER.debug("Sending command: %s", xml_command)

            # Send via UDP
            loop = asyncio.get_event_loop()
            await loop.sock_sendto(
                self._get_command_socket(),
                xml_command.encode("utf-8"),
                ("<broadcast>", UDP_COMMAND_PORT),
            )
        except OSError as exception:
            msg = f"Error sending command: {exception}"
            raise TclUdpApiClientCommunicationError(msg) from exception

    def _get_command_socket(self) -> socket.socket:
        """Get or create command socket."""
        if self._command_sock is None:
            self._command_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._command_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._command_sock.setblocking(False)  # noqa: FBT003
        return self._command_sock

    async def async_set_power(self, *, power_on: bool) -> None:
        """Turn the AC on or off."""
        value = "1" if power_on else "0"
        await self.async_send_command("turnOn", value)

    async def async_set_temperature(self, temperature: int) -> None:
        """Set target temperature."""
        await self.async_send_command("setTemp", str(temperature))

    def get_last_status(self) -> dict[str, Any]:
        """Get the last received status."""
        return self._last_status

    async def async_close(self) -> None:
        """Close the API client."""
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
