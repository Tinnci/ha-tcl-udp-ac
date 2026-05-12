#!/usr/bin/env python3
# pyright: reportMissingImports=false
import sys

from scapy.all import IP, Raw, TCP, UDP, rdpcap


def dump_packets(filename):
    print(f"Dumping packets from {filename}")
    packets = rdpcap(filename)
    for i, pkt in enumerate(packets[:50]):
        if IP in pkt:
            src = pkt[IP].src
            dst = pkt[IP].dst
            proto = "UDP" if UDP in pkt else "TCP" if TCP in pkt else "Other"
            sport = pkt[proto].sport if proto != "Other" else ""
            dport = pkt[proto].dport if proto != "Other" else ""

            payload = ""
            if Raw in pkt:
                payload = pkt[Raw].load.decode("utf-8", errors="ignore")

            print(f"[{i}] {src}:{sport} -> {dst}:{dport} ({proto}) | {payload[:100]}")


if __name__ == "__main__":
    dump_packets(sys.argv[1])
