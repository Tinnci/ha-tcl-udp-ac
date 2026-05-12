#!/usr/bin/env python3
"""Check device status using captured request template.

Usage:
  python3 tools/check_status.py                      # uses default capture file and will perform request
  python3 tools/check_status.py --capture-file file  # use specific jsonl file
  python3 tools/check_status.py --url <url>          # override URL
  python3 tools/check_status.py --no-verify          # skip TLS verification (useful with mitmproxy)
  python3 tools/check_status.py --tid 2743138       # build URL from tid (optional)

This script will try to extract the most recent getdevicestatus request from the capture jsonl and reuse its headers
when issuing the live request.
"""

from pathlib import Path
import argparse
import json
import re
import urllib.request, ssl
import sys

DEFAULT_CAPTURE = "../tcl_1770274433.jsonl"


def find_last_getdevicestatus(capture_file: Path):
    text = capture_file.read_text(encoding="utf-8", errors="replace")
    # parse each json line and find the last request entry with getdevicestatus
    last = None
    for line in text.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("type") == "request":
            url = j.get("url", "")
            if "device/getdevicestatus" in url:
                last = j
    return last


def build_headers_from_capture(req_obj):
    headers = {}
    if not req_obj:
        return headers
    raw = req_obj.get("headers", {})
    # Only include common headers we observed that matter for this endpoint
    for k in (
        "user-agent",
        "origin",
        "x-requested-with",
        "accept",
        "accept-encoding",
        "accept-language",
    ):
        if k in raw:
            headers[k] = raw[k]
        elif k.title() in raw:
            headers[k] = raw[k.title()]
    return headers


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--capture-file", default=DEFAULT_CAPTURE, help="jsonl capture file")
    p.add_argument("--url", help="override URL to query")
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="do not verify TLS certs (useful with mitmproxy)",
    )
    p.add_argument("--tid", help="device tid to build url (if no url provided)")
    p.add_argument("--category", default="AC")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    capture = Path(args.capture_file)
    if not capture.exists():
        print(f"Capture file {capture} not found", file=sys.stderr)
        sys.exit(2)

    req = find_last_getdevicestatus(capture)
    if args.url:
        url = args.url
    elif args.tid:
        url = (
            "https://io.zx.tcljd.com/device/getdevicestatus"
            f"?tid={args.tid}&category={args.category}&v={int(__import__('time').time()*1000)}"
        )
    elif req:
        url = req.get("url")
    else:
        print(
            "No getdevicestatus request found in capture file and no --url/--tid provided",
            file=sys.stderr,
        )
        sys.exit(3)

    headers = build_headers_from_capture(req) if req else {}
    if args.verbose:
        print("Using URL:", url)
        print("Using headers:")
        print(json.dumps(headers, indent=2, ensure_ascii=False))

    # use urllib to avoid external dependency
    ctx = None
    if args.no_verify:
        ctx = ssl._create_unverified_context()

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp_fp:
            status_code = resp_fp.getcode()
            reason = getattr(resp_fp, "reason", "")
            ct = resp_fp.headers.get("Content-Type", "")
            body_bytes = resp_fp.read()
            try:
                body = body_bytes.decode("utf-8", errors="replace")
            except Exception:
                body = body_bytes.decode("latin-1", errors="replace")
    except Exception as e:
        print("Request failed:", e, file=sys.stderr)
        sys.exit(4)

    print(f"HTTP/{status_code} - {reason}")

    if "application/json" in ct or body.strip().startswith("{") or body.strip().startswith("["):
        try:
            j = json.loads(body)
            print(json.dumps(j, indent=2, ensure_ascii=False))
            # If it contains curStatus, print some fields
            if isinstance(j, dict) and "curStatus" in j:
                cs = j["curStatus"]
                print("\nDetected curStatus keys:")
                for k in ["setTemp", "inTemp", "outTemp", "windSpd", "turnOn", "beepEn"]:
                    if k in cs:
                        print(f" - {k}: {cs[k]}")
        except Exception:
            print(body[:4000])
    else:
        print(body[:4000])


if __name__ == "__main__":
    main()
