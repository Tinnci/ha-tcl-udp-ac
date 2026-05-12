#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Analyze TCL AC pcap files to understand the protocol."""

import sys

from scapy.all import IP, Raw, UDP, rdpcap


def analyze_pcap(filename: str) -> None:
    """Analyze a pcap file for TCL AC protocol."""
    print(f"\n{'=' * 80}")
    print(f"Analyzing: {filename}")
    print(f"{'=' * 80}")

    try:
        packets = rdpcap(filename)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return

    from scapy.all import TCP

    ac_packets = []
    tcp_packets = []

    for pkt in packets:
        # Check UDP
        if UDP in pkt and Raw in pkt:
            sport = pkt[UDP].sport
            dport = pkt[UDP].dport

            # Filter for AC-related ports
            if sport in (10074, 10075, 6666) or dport in (10074, 10075, 6666):
                try:
                    payload = pkt[Raw].load.decode("utf-8", errors="ignore")
                except Exception:
                    continue

                src_ip = pkt[IP].src if IP in pkt else "?"
                dst_ip = pkt[IP].dst if IP in pkt else "?"

                ac_packets.append(
                    {
                        "src": f"{src_ip}:{sport}",
                        "dst": f"{dst_ip}:{dport}",
                        "payload": payload,
                        "len": len(payload),
                        "proto": "UDP",
                    }
                )

        # Check TCP
        if TCP in pkt and Raw in pkt:
            sport = pkt[TCP].sport
            dport = pkt[TCP].dport

            # Filter for AC-related ports (especially 6666)
            if sport in (6666,) or dport in (6666,):
                try:
                    payload = pkt[Raw].load.decode("utf-8", errors="ignore")
                except Exception:
                    continue

                src_ip = pkt[IP].src if IP in pkt else "?"
                dst_ip = pkt[IP].dst if IP in pkt else "?"

                tcp_packets.append(
                    {
                        "src": f"{src_ip}:{sport}",
                        "dst": f"{dst_ip}:{dport}",
                        "payload": payload,
                        "len": len(payload),
                        "proto": "TCP",
                    }
                )

    print(f"\nFound {len(ac_packets)} AC-related UDP packets\n")

    # Group by packet type
    discovery = []
    status = []
    control = []
    query = []
    other = []

    for pkt in ac_packets:
        payload = pkt["payload"]
        if "<searchDevice>" in payload or "<deviceInfo>" in payload:
            discovery.append(pkt)
        elif 'cmd="status"' in payload:
            status.append(pkt)
        elif 'cmd="control"' in payload:
            control.append(pkt)
        elif 'cmd="query"' in payload or 'type="query"' in payload:
            query.append(pkt)
        else:
            other.append(pkt)

    print(f"Discovery packets: {len(discovery)}")
    print(f"Status packets: {len(status)}")
    print(f"Control packets: {len(control)}")
    print(f"Query packets: {len(query)}")
    print(f"Other packets: {len(other)}")

    # Show control packets in detail
    if control:
        print(f"\n{'=' * 40}")
        print("CONTROL PACKETS (commands sent to AC):")
        print(f"{'=' * 40}")
        seen = set()
        for pkt in control:
            # Extract just the control element
            payload = pkt["payload"]
            if payload not in seen:
                seen.add(payload)
                print(f"\n[{pkt['src']} -> {pkt['dst']}]")
                # Pretty print the XML
                print(payload[:500] if len(payload) > 500 else payload)

    # Show query packets
    if query:
        print(f"\n{'=' * 40}")
        print("QUERY PACKETS:")
        print(f"{'=' * 40}")
        seen = set()
        for pkt in query:
            payload = pkt["payload"]
            if payload not in seen:
                seen.add(payload)
                print(f"\n[{pkt['src']} -> {pkt['dst']}]")
                print(payload[:500] if len(payload) > 500 else payload)

    # Show sample status packets
    if status:
        print(f"\n{'=' * 40}")
        print("SAMPLE STATUS PACKETS (first 3 unique):")
        print(f"{'=' * 40}")
        seen = set()
        count = 0
        for pkt in status:
            payload = pkt["payload"]
            # Normalize seq for comparison
            import re

            normalized = re.sub(r'seq="[^"]*"', 'seq="X"', payload)
            if normalized not in seen and count < 3:
                seen.add(normalized)
                count += 1
                print(f"\n[{pkt['src']} -> {pkt['dst']}]")
                print(payload[:800] if len(payload) > 800 else payload)

    # Show other packets
    if other:
        print(f"\n{'=' * 40}")
        print("OTHER PACKETS:")
        print(f"{'=' * 40}")
        seen = set()
        for pkt in other[:5]:  # First 5
            payload = pkt["payload"]
            if payload not in seen:
                seen.add(payload)
                print(f"\n[{pkt['src']} -> {pkt['dst']}]")
                print(payload[:500] if len(payload) > 500 else payload)

    # Show TCP packets
    if tcp_packets:
        print(f"\n{'=' * 40}")
        print(f"TCP PACKETS (port 6666): {len(tcp_packets)}")
        print(f"{'=' * 40}")
        for pkt in tcp_packets[:10]:  # First 10
            print(f"\n[TCP {pkt['src']} -> {pkt['dst']}]")
            payload = pkt["payload"]
            print(payload[:500] if len(payload) > 500 else payload)


if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files:
        print("Usage: python tools/analyze_pcap.py <file1.pcap> [file2.pcap] ...")
        sys.exit(1)

    # Also write to file
    import io
    from contextlib import redirect_stdout

    output = io.StringIO()
    with redirect_stdout(output):
        for f in files:
            analyze_pcap(f)

    result = output.getvalue()
    print(result)

    # Write to file
    with open("pcap_analysis.txt", "w", encoding="utf-8") as f:
        f.write(result)
    print("\n\nResults also saved to pcap_analysis.txt")
