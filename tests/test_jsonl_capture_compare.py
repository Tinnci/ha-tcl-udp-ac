"""Unit tests for comparing JSONL cloud captures."""

from __future__ import annotations

import json
from typing import Any


STATUS_ONLY_ENTRIES = [
    {
        "ts": 1,
        "type": "request",
        "method": "GET",
        "url": "https://io.zx.tcljd.com/device/getdevicestatus?tid=1&category=AC&v=1",
        "headers": {
            "user-agent": "Mozilla/5.0",
            "accept": "text/plain, */*; q=0.01",
            "origin": "https://h5.zx.tcljd.com",
            "x-requested-with": "com.tcl.tclplus",
        },
        "body": "",
    },
    {
        "ts": 2,
        "type": "request",
        "method": "GET",
        "url": "https://io.zx.tcljd.com/device/getdevicestatus?tid=1&category=AC&v=2",
        "headers": {
            "user-agent": "Mozilla/5.0",
            "accept": "text/plain, */*; q=0.01",
            "origin": "https://h5.zx.tcljd.com",
            "x-requested-with": "com.tcl.tclplus",
        },
        "body": "",
    },
]

MIXED_ENTRIES = [
    {
        "ts": 10,
        "type": "request",
        "method": "POST",
        "url": "https://io.zx.tcljd.com/v1/control/convertMqtt/1",
        "headers": {
            "platform": "android",
            "user-agent": "com.tcl.tclplus/6.0.3, Android",
            "apppackagename": "com.tcl.tclplus",
            "accesstoken": "REDACTED",
            "content-type": "application/json; charset=UTF-8",
        },
        "body": "{\"source\":\"APP\",\"params\":\"<message>...</message>\"}",
    },
    {
        "ts": 11,
        "type": "response",
        "url": "https://io.zx.tcljd.com/v1/control/convertMqtt/1",
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "body": "{\"success\":true}",
    },
    {
        "ts": 12,
        "type": "request",
        "method": "GET",
        "url": "https://io.zx.tcljd.com/device/getdevicestatus?tid=1&category=AC&v=3",
        "headers": {
            "user-agent": "Mozilla/5.0",
            "accept": "text/plain, */*; q=0.01",
            "origin": "https://h5.zx.tcljd.com",
            "x-requested-with": "com.tcl.tclplus",
        },
        "body": "",
    },
    {
        "ts": 13,
        "type": "response",
        "url": "https://io.zx.tcljd.com/device/getdevicestatus?tid=1&category=AC&v=3",
        "status_code": 200,
        "headers": {"content-type": "text/html;charset=UTF-8"},
        "body": (
            "{\"curStatus\":{\"turnOn\":\"1\",\"setTemp\":\"75\","
            "\"baseMode\":\"4\",\"actionJid\":"
            "\"user@tcl.com/PH-android-zx01-2\"},\"LINE_STATUS\":\"2\"}"
        ),
    },
]

CAPTURE_STATUS_ONLY = "\n".join(json.dumps(item) for item in STATUS_ONLY_ENTRIES)
CAPTURE_MIXED = "\n".join(json.dumps(item) for item in MIXED_ENTRIES)


def parse_jsonl(text: str) -> list[dict[str, Any]]:
    """Parse JSONL text into a list of dictionaries."""
    entries: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        entries.append(json.loads(line))
    return entries


def find_entries(
    entries: list[dict[str, Any]],
    method: str | None,
    url_substr: str,
) -> list[dict[str, Any]]:
    """Filter entries by method (if provided) and URL substring."""
    matched: list[dict[str, Any]] = []
    for entry in entries:
        if method is not None and entry.get("method") != method:
            continue
        if url_substr not in entry.get("url", ""):
            continue
        matched.append(entry)
    return matched


def test_status_only_capture_has_no_control() -> None:
    """Status-only capture should have GETs and no control requests."""
    entries = parse_jsonl(CAPTURE_STATUS_ONLY)
    status_gets = find_entries(entries, "GET", "/device/getdevicestatus")
    control_posts = find_entries(entries, "POST", "/v1/control/convertMqtt/")
    responses = [entry for entry in entries if entry.get("type") == "response"]

    assert len(status_gets) >= 1
    assert len(control_posts) == 0
    assert len(responses) == 0


def test_mixed_capture_has_control_and_status() -> None:
    """Mixed capture should include control and status response entries."""
    entries = parse_jsonl(CAPTURE_MIXED)
    status_gets = find_entries(entries, "GET", "/device/getdevicestatus")
    control_posts = find_entries(entries, "POST", "/v1/control/convertMqtt/")
    status_responses = [
        entry
        for entry in entries
        if entry.get("type") == "response"
        and "/device/getdevicestatus" in entry.get("url", "")
    ]

    assert len(status_gets) >= 1
    assert len(control_posts) >= 1
    assert len(status_responses) >= 1


def test_header_sets_differ_between_get_and_post() -> None:
    """GET and POST requests should keep distinct header sets."""
    entries = parse_jsonl(CAPTURE_MIXED)
    post_headers = find_entries(entries, "POST", "/v1/control/convertMqtt/")[0][
        "headers"
    ]
    get_headers = find_entries(entries, "GET", "/device/getdevicestatus")[0][
        "headers"
    ]

    assert "platform" in post_headers
    assert "apppackagename" in post_headers
    assert "origin" in get_headers
    assert "x-requested-with" in get_headers
