#!/usr/bin/env python3
"""Local UDP control attempt: discover device and send BeepEnable on/off.

Usage:
  python3 tools/udp_beep_control.py --off
  python3 tools/udp_beep_control.py --on
  python3 tools/udp_beep_control.py --mac <MAC> --ip <IP> --port <PORT> --off

Notes:
- Sends UDP broadcast SearchDevice to 255.255.255.255:10075
- Listens on UDP port 10074 for responses
- Sends SetMessage with <BeepEnable>on/off</BeepEnable>
"""
import argparse
import socket
import time
import xml.etree.ElementTree as ET

BCAST_IP = "255.255.255.255"
BCAST_PORT = 10075
LISTEN_PORT = 10074


def discover(timeout=3.0):
    devices = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("0.0.0.0", LISTEN_PORT))
    except OSError:
        # fallback to ephemeral if port busy
        sock.bind(("0.0.0.0", 0))
    sock.settimeout(0.5)

    msg = b"<message msgid=\"SearchDevice\"></message>"
    sock.sendto(msg, (BCAST_IP, BCAST_PORT))

    end = time.time() + timeout
    while time.time() < end:
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        try:
            text = data.decode("utf-8", errors="replace")
            if "DevMAC" not in text:
                continue
            dev = parse_device_xml(text)
            if dev and dev not in devices:
                devices.append(dev)
        except Exception:
            continue
    sock.close()
    return devices


def parse_device_xml(text):
    try:
        root = ET.fromstring(text)
    except Exception:
        return None

    def get(tag):
        el = root.find(f".//{tag}")
        return el.text.strip() if el is not None and el.text else None

    dev = {
        "mac": get("DevMAC"),
        "ip": get("DevIP"),
        "port": get("DevPort"),
        "name": get("DevName"),
        "type": get("DevType"),
    }
    if not dev["mac"] or not dev["ip"] or not dev["port"]:
        return None
    return dev


def build_setmessage(mac, seq, value):
    # value: 'on'/'off'
    msg = (
        f"<msg msgid=\"SetMessage\" type=\" Control\" seq=\"{seq}\">"
        f"<SetMessage><BeepEnable>{value}</BeepEnable></SetMessage></msg>"
    )
    # insert tclid attribute
    msg = msg.replace("<msg ", f"<msg tclid=\"{mac.upper()}\" ", 1)
    return msg


def send_udp(ip, port, payload, timeout=3.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.sendto(payload.encode("utf-8"), (ip, int(port)))
    try:
        data, addr = sock.recvfrom(2048)
        return data.decode("utf-8", errors="replace")
    except socket.timeout:
        return None
    finally:
        sock.close()


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--off", action="store_true")
    g.add_argument("--on", action="store_true")
    p.add_argument("--mac")
    p.add_argument("--ip")
    p.add_argument("--port")
    p.add_argument("--timeout", type=float, default=3.0)
    args = p.parse_args()

    value = "off" if args.off else "on"

    if args.mac and args.ip and args.port:
        devices = [{"mac": args.mac, "ip": args.ip, "port": args.port}]
    else:
        devices = discover(timeout=args.timeout)

    if not devices:
        print("No UDP devices discovered.")
        return

    dev = devices[0]
    print("Using device:", dev)
    seq = int(time.time()) % 100000
    msg = build_setmessage(dev["mac"], seq, value)
    print("UDP payload:", msg)

    resp = send_udp(dev["ip"], dev["port"], msg, timeout=args.timeout)
    if resp:
        print("UDP response:", resp)
    else:
        print("No UDP response received (timeout).")


if __name__ == "__main__":
    main()
