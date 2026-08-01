"""Shared UDP socket hub with deterministic per-device routing."""

from __future__ import annotations

import asyncio
import json
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from .const import LOGGER, UDP_BROADCAST_PORT


def normalize_device_identity(value: str | None) -> str | None:
    """Normalize MAC-like identities for stable matching."""
    if not value:
        return None
    normalized = "".join(char for char in str(value).upper() if char.isalnum())
    return normalized or None


def packet_identity(data: bytes) -> str | None:
    """Extract a device MAC/identity from known TCL datagram formats."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        root = ET.fromstring(text)  # noqa: S314
    except ET.ParseError:
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        return normalize_device_identity(
            payload.get("mac") or payload.get("deviceMac") or payload.get("tclid")
        )

    identity = root.get("tclid") or root.get("devid")
    if root.tag == "deviceInfo":
        identity = (
            root.findtext("DevMAC")
            or root.findtext("devMac")
            or root.findtext("devMAC")
            or identity
        )
    return normalize_device_identity(identity)


@dataclass
class UdpSubscription:
    """Routing information for one device session."""

    subscription_id: int
    callback: Any
    expected_mac: str | None = None
    bound_mac: str | None = None
    bound_ip: str | None = None


class UdpHub:
    """Own one listener/send socket and route traffic to device subscriptions."""

    def __init__(self) -> None:
        """Initialize an inactive hub with no subscriptions."""
        self._listener_sock: socket.socket | None = None
        self._send_sock: socket.socket | None = None
        self._subscriptions: dict[int, UdpSubscription] = {}
        self._next_subscription_id = 0
        self._users = 0

    def subscribe(
        self,
        callback: Any,
        *,
        expected_mac: str | None = None,
    ) -> UdpSubscription:
        """Register a device callback without starting sockets."""
        self._next_subscription_id += 1
        subscription = UdpSubscription(
            subscription_id=self._next_subscription_id,
            callback=callback,
            expected_mac=normalize_device_identity(expected_mac),
        )
        self._subscriptions[subscription.subscription_id] = subscription
        return subscription

    def unsubscribe(self, subscription: UdpSubscription | None) -> None:
        """Remove a device callback."""
        if subscription is not None:
            self._subscriptions.pop(subscription.subscription_id, None)

    def route_datagram(self, data: bytes, addr: tuple[str, int]) -> int:
        """Route a datagram and return the number of callbacks invoked."""
        identity = packet_identity(data)
        sender_ip = addr[0]
        exact: list[UdpSubscription] = []
        for subscription in self._subscriptions.values():
            known_mac = subscription.bound_mac or subscription.expected_mac
            identity_matches = identity is not None and known_mac == identity
            ip_matches = identity is None and subscription.bound_ip == sender_ip
            if identity_matches or ip_matches:
                exact.append(subscription)

        if exact:
            targets = exact
        else:
            unknown = [
                subscription
                for subscription in self._subscriptions.values()
                if subscription.expected_mac is None
                and subscription.bound_mac is None
                and subscription.bound_ip is None
            ]
            if len(unknown) != 1:
                if unknown:
                    LOGGER.warning(
                        "Ambiguous TCL UDP packet from %s; %d unbound devices",
                        sender_ip,
                        len(unknown),
                    )
                return 0
            targets = unknown

        for subscription in targets:
            subscription.bound_ip = sender_ip
            if identity is not None:
                subscription.bound_mac = identity
            subscription.callback(data, addr)
        return len(targets)

    async def async_acquire(self) -> None:
        """Start shared sockets for the first active device session."""
        self._users += 1
        if self._listener_sock is not None:
            return
        try:
            loop = asyncio.get_running_loop()
            self._listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._listener_sock.setblocking(False)  # noqa: FBT003
            self._listener_sock.bind(("0.0.0.0", UDP_BROADCAST_PORT))  # noqa: S104
            loop.add_reader(self._listener_sock.fileno(), self._on_listener_readable)

            self._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._send_sock.setblocking(False)  # noqa: FBT003
            loop.add_reader(self._send_sock.fileno(), self._on_send_readable)
        except OSError:
            self._users -= 1
            await self._async_close_sockets()
            raise

    async def async_release(self) -> None:
        """Release one user and close sockets after the final session unloads."""
        self._users = max(0, self._users - 1)
        if self._users == 0:
            await self._async_close_sockets()

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        """Send a datagram through the shared send socket."""
        if self._send_sock is None:
            msg = "TCL UDP hub is not started"
            raise OSError(msg)
        self._send_sock.sendto(data, addr)

    def _on_listener_readable(self) -> None:
        if self._listener_sock is None:
            return
        try:
            data, addr = self._listener_sock.recvfrom(4096)
            self.route_datagram(data, addr)
        except BlockingIOError:
            return

    def _on_send_readable(self) -> None:
        if self._send_sock is None:
            return
        try:
            data, addr = self._send_sock.recvfrom(4096)
            self.route_datagram(data, addr)
        except BlockingIOError:
            return

    async def _async_close_sockets(self) -> None:
        loop = asyncio.get_running_loop()
        for sock in (self._listener_sock, self._send_sock):
            if sock is None:
                continue
            loop.remove_reader(sock.fileno())
            sock.close()
        self._listener_sock = None
        self._send_sock = None
