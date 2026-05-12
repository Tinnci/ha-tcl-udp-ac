#!/usr/bin/env python3
"""Batch toggle swing (directH/directV/optSolidWd), wind speed and other options, test beep control, then verify status.

Usage:
    python3 tools/control_wind.py [--capture-file FILE] [--no-verify] [--verbose] [--delay 2]
"""
from pathlib import Path
from collections import OrderedDict
import json, re, sys, argparse, ssl, urllib.request, time

DEFAULT_CAPTURE = 'captures/tcl_1770274433.jsonl'


def find_last_convert(capture_file: Path):
    text = capture_file.read_text(encoding='utf-8', errors='replace')
    last = None
    for line in text.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get('type') == 'request' and '/v1/control/convertMqtt/' in j.get('url',''):
            last = j
    return last


def build_headers(raw):
    out = {}
    for k in ['platform','user-agent','apppackagename','systemversion','brand','appversion','sdkversion','accesstoken','channel','appbuildversion','t-app-version','t-platform-type','t-store-uuid','content-type','accept-encoding']:
        if k in raw:
            out[k] = raw[k]
        elif k.title() in raw:
            out[k] = raw[k.title()]
    if 'content-type' not in out:
        out['content-type'] = 'application/json; charset=UTF-8'
    return out


def http_get(url, headers=None, no_verify=False):
    ctx = ssl._create_unverified_context() if no_verify else None
    req = urllib.request.Request(url, headers=headers or {}, method='GET')
    with urllib.request.urlopen(req, timeout=15, context=ctx) as fp:
        return fp.getcode(), fp.headers, fp.read().decode('utf-8', errors='replace')


def http_post(url, headers, body_bytes, no_verify=False):
    ctx = ssl._create_unverified_context() if no_verify else None
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=15, context=ctx) as fp:
        return fp.getcode(), fp.headers, fp.read().decode('utf-8', errors='replace')


def extract_from_to(params_xml):
    m_from = re.search(r'from="([^"]+)"', params_xml)
    m_to = re.search(r'to="([^"]+)"', params_xml)
    return (m_from.group(1) if m_from else None, m_to.group(1) if m_to else None)


def fetch_status(stat_url, headers, no_verify=False, label='Status'):
    try:
        code, _, body = http_get(
            stat_url,
            headers=headers,
            no_verify=no_verify,
        )
    except Exception as exc:
        print(f"{label} HTTP failed:", exc)
        return {}

    print(f"{label} HTTP", code)
    try:
        j = json.loads(body)
        cs = j.get('curStatus', {})
        status = {
            k: cs.get(k)
            for k in [
                'windSpd',
                'directH',
                'directV',
                'optSolidWd',
                'optECO',
                'optSuper',
                'optDisplay',
                'optSleepMd',
                'beepEn',
                'baseMode',
            ]
        }
        print(f"{label}:", status)
        return status
    except Exception:
        print(f"Failed to parse {label} status")
        return {}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--capture-file', default=DEFAULT_CAPTURE)
    p.add_argument('--no-verify', action='store_true')
    p.add_argument('--verbose', action='store_true')
    p.add_argument('--delay', type=float, default=2.0, help='seconds to wait between steps')
    p.add_argument('--wind-values', help='comma-separated windSpd values to test (e.g. 0,1,2,3)')
    p.add_argument('--wind-only', action='store_true', help='only change windSpd, do not toggle other options')
    p.add_argument('--skip-beep', action='store_true', help='skip beep tests')
    p.add_argument('--set', action='append', default=[], help='extra tag=value pairs to include (e.g. optSleepMd=0)')
    args = p.parse_args()

    cap = Path(args.capture_file)
    if not cap.exists():
        print('Capture file not found:', cap, file=sys.stderr); sys.exit(2)

    last = find_last_convert(cap)
    if not last:
        print('No convertMqtt request in capture', file=sys.stderr); sys.exit(3)

    url = last['url']
    tid = url.rstrip('/').split('/')[-1]
    headers = build_headers(last.get('headers', {}))
    post_headers = dict(headers)
    post_headers['Content-Type'] = 'application/json; charset=UTF-8'

    body_str = last.get('body','')
    params_match = re.search(r'"params"\s*:\s*"(.*?)"', body_str, re.S)
    params_xml = params_match.group(1).replace('\\"','"') if params_match else ''
    from_attr, to_attr = extract_from_to(params_xml)
    if not from_attr:
        from_attr = '14427826@tcl.com/PH-android-zx01-2'
    if not to_attr:
        to_attr = f"{tid}@tcl.com/AC-linux-zx01-1"

    if args.verbose:
        print('Using tid:', tid)

    stat_url = f"https://io.zx.tcljd.com/device/getdevicestatus?tid={tid}&category=AC&v={int(time.time()*1000)}"
    status_headers = {
        'user-agent': headers.get('user-agent','Mozilla/5.0'),
        'origin': 'https://h5.zx.tcljd.com',
        'x-requested-with': 'com.tcl.tclplus',
        'accept': 'text/plain, */*; q=0.01',
        'accept-encoding': headers.get('accept-encoding','gzip, deflate, br, zstd'),
    }
    before = fetch_status(stat_url, status_headers, no_verify=args.no_verify, label='Before')

    # ensure still in heat mode (baseMode == '4' observed in prior status)
    if before.get('baseMode') not in (None, '4'):
        print('Warning: baseMode is not heat (4). Current:', before.get('baseMode'))

    wind_values = None
    if args.wind_values:
        wind_values = [v.strip() for v in args.wind_values.split(',') if v.strip()]

    wind_only = args.wind_only or bool(wind_values)

    extra_items = []
    for raw in args.set:
        if '=' not in raw:
            print('Ignoring invalid --set value (expected tag=value):', raw)
            continue
        tag, value = raw.split('=', 1)
        tag = tag.strip()
        value = value.strip()
        if not tag:
            print('Ignoring invalid --set value (empty tag):', raw)
            continue
        extra_items.append((tag, value))

    # choose target values
    wind_next = '3' if before.get('windSpd') != '3' else '1'
    directH_next = '1' if before.get('directH') != '1' else '0'
    directV_next = '1' if before.get('directV') != '1' else '0'
    optSolidWd_next = '1' if before.get('optSolidWd') != '1' else '0'
    optECO_next = '1' if before.get('optECO') != '1' else '0'
    optSuper_next = '1' if before.get('optSuper') != '1' else '0'
    optDisplay_next = '1' if before.get('optDisplay') != '1' else '0'
    optSleepMd_next = '1' if before.get('optSleepMd') != '1' else '0'

    def send_control(payload_items, label):
        payload_dict = OrderedDict(payload_items)
        for tag, value in extra_items:
            payload_dict[tag] = value
        payload_items = list(payload_dict.items())

        seq = int(time.time() % 100000)
        msg_id = f"android_{label}_{int(time.time()*1000)}"
        item_str = ''.join(
            f"<{tag} value=\"{value}\"></{tag}>" for tag, value in payload_items
        )
        xml = (
            f"<message id=\"{msg_id}\" from=\"{from_attr}\" to=\"{to_attr}\" type=\"chat\" source=\"0\">"
            f"<x xmlns=\"tcl:im:attribute\"><sendtime>{time.strftime('%Y-%m-%d %H:%M:%S')}</sendtime></x>"
            f"<body><msg cmd=\"set\" type=\"control\" action=\"1\" seq=\"{seq}\" devid=\"{tid}\">"
            f"{item_str}"
            f"</msg></body></message>"
        )
        post_body = json.dumps({"source":"APP","params": xml}).encode('utf-8')

        if args.verbose:
            print('POST XML:', xml)

        code, _, res = http_post(url, headers=post_headers, body_bytes=post_body, no_verify=args.no_verify)
        print('Control POST HTTP', code)
        print(res[:1000])

    control_values = wind_values or [wind_next]
    for wind_value in control_values:
        payload = [("windSpd", wind_value)]
        if not wind_only:
            payload.extend(
                [
                    ("directH", directH_next),
                    ("directV", directV_next),
                    ("optSolidWd", optSolidWd_next),
                    ("optECO", optECO_next),
                    ("optSuper", optSuper_next),
                    ("optDisplay", optDisplay_next),
                    ("optSleepMd", optSleepMd_next),
                ]
            )

        send_control(payload, f"wind_{wind_value}")
        time.sleep(args.delay)
        fetch_status(stat_url, status_headers, no_verify=args.no_verify, label=f"After windSpd={wind_value}")

    # beep tests using different value formats
    def beep_test(value_str, label):
        seq_b = int(time.time() % 100000)
        msg_id_b = f"android_beep_{label}_{int(time.time()*1000)}"
        xml_b = (
            f"<message id=\"{msg_id_b}\" from=\"{from_attr}\" to=\"{to_attr}\" type=\"chat\" source=\"0\">"
            f"<x xmlns=\"tcl:im:attribute\"><sendtime>{time.strftime('%Y-%m-%d %H:%M:%S')}</sendtime></x>"
            f"<body><msg cmd=\"set\" type=\"control\" action=\"1\" seq=\"{seq_b}\" devid=\"{tid}\">"
            f"<BeepEnable>{value_str}</BeepEnable>"
            f"</msg></body></message>"
        )
        post_body_b = json.dumps({"source":"APP","params": xml_b}).encode('utf-8')
        code_b, _, res_b = http_post(url, headers=post_headers, body_bytes=post_body_b, no_verify=args.no_verify)
        print(f"Beep test {label} POST HTTP", code_b)
        if args.verbose:
            print('Beep XML:', xml_b)
        time.sleep(args.delay)
        code_s, _, body_s = http_get(
            stat_url,
            headers={
                'user-agent': headers.get('user-agent','Mozilla/5.0'),
                'origin': 'https://h5.zx.tcljd.com',
                'x-requested-with': 'com.tcl.tclplus',
                'accept': 'text/plain, */*; q=0.01',
                'accept-encoding': headers.get('accept-encoding','gzip, deflate, br, zstd'),
            },
            no_verify=args.no_verify,
        )
        try:
            js = json.loads(body_s)
            beep_now = js.get('curStatus', {}).get('beepEn')
            print(f"Beep test {label} status HTTP {code_s} beepEn:", beep_now)
        except Exception:
            print(f"Beep test {label} failed to parse status")

    if not (args.skip_beep or wind_only):
        beep_test('off', 'off')
        beep_test('on', 'on')
        beep_test('0', '0')
        beep_test('1', '1')

    # restore original state
    restore = before
    seq2 = int(time.time() % 100000)
    msg_id2 = f"android_restore_{int(time.time()*1000)}"
    restore_items = [
        ("windSpd", restore.get('windSpd','1')),
    ]
    if not wind_only:
        restore_items.extend(
            [
                ("directH", restore.get('directH','0')),
                ("directV", restore.get('directV','0')),
                ("optSolidWd", restore.get('optSolidWd','0')),
                ("optECO", restore.get('optECO','0')),
                ("optSuper", restore.get('optSuper','0')),
                ("optDisplay", restore.get('optDisplay','1')),
                ("optSleepMd", restore.get('optSleepMd','0')),
            ]
        )
    for tag, _ in extra_items:
        if tag not in {t for t, _ in restore_items}:
            if tag in restore:
                restore_items.append((tag, restore.get(tag)))
    restore_item_str = ''.join(
        f"<{tag} value=\"{value}\"></{tag}>" for tag, value in restore_items
    )
    xml_restore = (
        f"<message id=\"{msg_id2}\" from=\"{from_attr}\" to=\"{to_attr}\" type=\"chat\" source=\"0\">"
        f"<x xmlns=\"tcl:im:attribute\"><sendtime>{time.strftime('%Y-%m-%d %H:%M:%S')}</sendtime></x>"
        f"<body><msg cmd=\"set\" type=\"control\" action=\"1\" seq=\"{seq2}\" devid=\"{tid}\">"
        f"{restore_item_str}"
        f"</msg></body></message>"
    )
    post_body2 = json.dumps({"source":"APP","params": xml_restore}).encode('utf-8')
    code3, _, res3 = http_post(url, headers=post_headers, body_bytes=post_body2, no_verify=args.no_verify)
    print('Restore POST HTTP', code3)
    print(res3[:1000])

    time.sleep(args.delay)
    fetch_status(stat_url, status_headers, no_verify=args.no_verify, label='After restore')


if __name__ == '__main__':
    main()
