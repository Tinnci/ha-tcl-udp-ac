"""Standalone UDP test for TCL AC (Windows).

Listen for broadcast status packets on port 10074 and optionally send
unicast SyncStatusReq to the device on port 10075.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import socket
import threading
import time


LOGGER = logging.getLogger("tcl_udp_test")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def _safe_decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def create_listener_socket(port: int) -> socket.socket:
    """Create and bind a UDP listener socket for broadcasts."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.5)

    try:
        sock.bind(("", port))
    except OSError:
        LOGGER.exception("Bind failed on port %d", port)
        sock.close()
        raise

    return sock


def listen_broadcast(sock: socket.socket, stop_event: threading.Event) -> None:
    """Listen for UDP broadcast status packets using a bound socket."""
    LOGGER.info("Listening on %s:%d (broadcast)", *sock.getsockname())

    try:
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(8192)
            except TimeoutError:
                continue
            except OSError:
                LOGGER.exception("Recv failed")
                break

            payload = _safe_decode(data)
            LOGGER.info("RECV %d bytes from %s:%d", len(data), addr[0], addr[1])
            LOGGER.info("%s", payload)
    finally:
        LOGGER.info("Listener stopped")


def send_discovery(sock: socket.socket, device_port: int) -> None:
    """Broadcast multiple discovery payload variants to the specified port."""
    payloads = {
        "old_xml": b'<message msgid="SearchDevice"></message>',
        "new_xml": b"<searchDevice></searchDevice>",
        "json_q": b'{"msgId":"123","version":"123","q":"searchReq"}',
        "json_method": b'{"msgId":"123","version":"123","method":"searchReq"}',
    }

    for name, payload in payloads.items():
        try:
            sock.sendto(payload, ("255.255.255.255", device_port))
            LOGGER.info(
                "Sent discovery (%s) to 255.255.255.255:%d: %s",
                name,
                device_port,
                payload.decode("utf-8", errors="replace"),
            )
        except OSError:
            LOGGER.exception("Discovery send failed (%s)")


@dataclasses.dataclass(frozen=True)
class SyncRequest:
    """SyncStatusReq request parameters."""

    device_ip: str
    device_port: int
    tclid: str
    seq: int
    msg_type: str
    timeout: float
    attr_mode: str


@dataclasses.dataclass(frozen=True)
class KeepAliveRequest:
    """keepAlive request parameters."""

    device_ip: str
    device_port: int
    seq: int


def _build_attr_string(attr_mode: str, tclid: str) -> str:
    """Build the attribute portion for a msg tag."""
    tclid_value = tclid.strip().upper()
    if attr_mode == "none":
        return ""
    if attr_mode == "tclid":
        return f' tclid="{tclid_value}"'
    if attr_mode == "devid":
        return f' devid="{tclid_value}"'
    if attr_mode == "both":
        return f' tclid="{tclid_value}" devid="{tclid_value}"'
    return f' tclid="{tclid_value}"'


def send_sync_status(req: SyncRequest) -> None:
    """Send a SyncStatusReq unicast request and listen for replies."""
    attr_str = _build_attr_string(req.attr_mode, req.tclid)
    xml = (
        f'<msg{attr_str} msgid="SyncStatusReq" '
        f'type="{req.msg_type}" seq="{req.seq}">'
        f"<SyncStatusReq></SyncStatusReq></msg>"
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)

    # Bind to an ephemeral port so we can receive replies on the same socket
    sock.bind(("", 0))
    local_addr = sock.getsockname()

    LOGGER.info(
        "Sending SyncStatusReq (%s) from %s:%d -> %s:%d",
        req.msg_type,
        local_addr[0],
        local_addr[1],
        req.device_ip,
        req.device_port,
    )

    try:
        sock.sendto(xml.encode("utf-8"), (req.device_ip, req.device_port))
    except OSError:
        LOGGER.exception("Send failed")
        sock.close()
        return

    end_time = time.time() + req.timeout
    received_any = False

    while time.time() < end_time:
        try:
            data, addr = sock.recvfrom(8192)
        except TimeoutError:
            continue
        except OSError:
            LOGGER.exception("Recv failed")
            break

        received_any = True
        payload = _safe_decode(data)
        LOGGER.info("RECV %d bytes from %s:%d", len(data), addr[0], addr[1])
        LOGGER.info("%s", payload)

    if not received_any:
        LOGGER.info("No unicast reply received within %.1fs", req.timeout)

    sock.close()


def send_sync_status_via_listener(
    sock: socket.socket, req: SyncRequest
) -> None:
    """Send SyncStatusReq using the listener socket (source port 10074)."""
    attr_str = _build_attr_string(req.attr_mode, req.tclid)
    xml = (
        f'<msg{attr_str} msgid="SyncStatusReq" '
        f'type="{req.msg_type}" seq="{req.seq}">'
        f"<SyncStatusReq></SyncStatusReq></msg>"
    )

    try:
        sock.sendto(xml.encode("utf-8"), (req.device_ip, req.device_port))
        LOGGER.info(
            "Sent SyncStatusReq (%s) via listener to %s:%d",
            req.msg_type,
            req.device_ip,
            req.device_port,
        )
    except OSError:
        LOGGER.exception("Send failed (listener socket)")


def send_keepalive_via_listener(
    sock: socket.socket, req: KeepAliveRequest
) -> None:
    """Send keepAlive using the listener socket (source port 10074)."""
    xml = (
        f'<msg msgid="keepAlive" type="Control" seq="{req.seq}">'
        f"<keepAlive></keepAlive></msg>"
    )

    try:
        sock.sendto(xml.encode("utf-8"), (req.device_ip, req.device_port))
        LOGGER.info(
            "Sent keepAlive via listener to %s:%d",
            req.device_ip,
            req.device_port,
        )
    except OSError:
        LOGGER.exception("keepAlive send failed")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="TCL AC UDP test (broadcast listen + SyncStatusReq unicast)"
    )
    parser.add_argument("--listen-seconds", type=int, default=30)
    parser.add_argument("--listen-port", type=int, default=10074)

    parser.add_argument("--device-ip", type=str, default=None)
    parser.add_argument("--device-port", type=int, default=10075)
    parser.add_argument("--tclid", type=str, default=None)
    parser.add_argument("--seq", type=int, default=101)
    parser.add_argument(
        "--sync-attr",
        type=str,
        default="tclid",
        choices=["tclid", "devid", "both", "none"],
    )
    parser.add_argument("--sync-from-listener", action="store_true")
    parser.add_argument("--send-keepalive", action="store_true")

    parser.add_argument("--send-discovery", action="store_true")
    parser.add_argument("--send-sync", action="store_true")
    parser.add_argument("--send-both", action="store_true")
    parser.add_argument("--timeout", type=float, default=3.0)

    return parser.parse_args()


def main() -> None:
    """Run the broadcast listener and optional SyncStatusReq test."""
    _setup_logging()
    args = parse_args()

    try:
        listener_sock = create_listener_socket(args.listen_port)
    except OSError:
        return

    stop_event = threading.Event()
    listener_thread = threading.Thread(
        target=listen_broadcast,
        args=(listener_sock, stop_event),
        daemon=True,
    )
    listener_thread.start()

    time.sleep(0.3)

    if args.send_discovery:
        send_discovery(listener_sock, args.device_port)

    if args.send_sync:
        if not args.device_ip:
            LOGGER.error("--device-ip is required for --send-sync")
        elif not args.tclid:
            LOGGER.error("--tclid is required for --send-sync")
        else:
            msg_types = ["Control", "Notify"] if args.send_both else ["Control"]
            for offset, msg_type in enumerate(msg_types):
                req = SyncRequest(
                    device_ip=args.device_ip,
                    device_port=args.device_port,
                    tclid=args.tclid,
                    seq=args.seq + offset,
                    msg_type=msg_type,
                    timeout=args.timeout,
                    attr_mode=args.sync_attr,
                )
                if args.sync_from_listener:
                    send_sync_status_via_listener(listener_sock, req)
                else:
                    send_sync_status(req)

    if args.send_keepalive:
        if not args.device_ip:
            LOGGER.error("--device-ip is required for --send-keepalive")
        else:
            send_keepalive_via_listener(
                listener_sock,
                KeepAliveRequest(
                    device_ip=args.device_ip,
                    device_port=args.device_port,
                    seq=args.seq,
                ),
            )

    time.sleep(max(0, args.listen_seconds))
    stop_event.set()
    listener_thread.join(timeout=2.0)
    listener_sock.close()


if __name__ == "__main__":
    main()
