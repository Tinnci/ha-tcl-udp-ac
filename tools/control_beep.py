#!/usr/bin/env python3
"""Send control to disable beep and verify status change.

Usage:
  python3 tools/control_beep.py [--capture-file FILE] [--no-verify] [--verbose]

Behavior:
 - Extracts last convertMqtt request from capture jsonl to reuse headers and tid.
 - Checks current beepEn via device/getdevicestatus.
 - Sends a POST control with <BeepEnable>off</BeepEnable>.
 - Re-checks status and reports change.
"""
from pathlib import Path
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
        if j.get('type') == 'request':
            url = j.get('url','')
            if '/v1/control/convertMqtt/' in url:
                last = j
    return last


def build_headers(raw):
    # keep relevant headers observed earlier
    out = {}
    for k in ['platform','user-agent','apppackagename','systemversion','brand','appversion','sdkversion','accesstoken','channel','appbuildversion','t-app-version','t-platform-type','t-store-uuid','content-type','accept-encoding']:
        if k in raw:
            out[k] = raw[k]
        elif k.title() in raw:
            out[k] = raw[k.title()]
    # ensure content-type is set
    if 'content-type' not in out:
        out['content-type'] = 'application/json; charset=UTF-8'
    return out


def http_get(url, headers=None, no_verify=False):
    ctx = None
    if no_verify:
        ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=headers or {}, method='GET')
    with urllib.request.urlopen(req, timeout=15, context=ctx) as fp:
        body = fp.read().decode('utf-8', errors='replace')
        return fp.getcode(), fp.headers, body


def http_post(url, headers, body_bytes, no_verify=False):
    ctx = None
    if no_verify:
        ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=15, context=ctx) as fp:
        res = fp.read().decode('utf-8', errors='replace')
        return fp.getcode(), fp.headers, res


def extract_from_to(params_xml):
    m_from = re.search(r'from="([^"]+)"', params_xml)
    m_to = re.search(r'to="([^"]+)"', params_xml)
    return (m_from.group(1) if m_from else None, m_to.group(1) if m_to else None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--capture-file', default=DEFAULT_CAPTURE)
    p.add_argument('--no-verify', action='store_true')
    p.add_argument('--verbose', action='store_true')
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

    # get params sample
    body_str = last.get('body','')
    params_match = re.search(r'"params"\s*:\s*"(.*?)"', body_str, re.S)
    params_xml = params_match.group(1) if params_match else None
    if params_xml:
        params_xml = params_xml.replace('\\"','"')
    from_attr, to_attr = extract_from_to(params_xml or '')
    if not from_attr:
        from_attr = '14427826@tcl.com/PH-android-zx01-2'
    if not to_attr:
        to_attr = f"{tid}@tcl.com/AC-linux-zx01-1"

    if args.verbose:
        print('Using tid:', tid)
        print('Using headers:')
        print(json.dumps(headers, indent=2, ensure_ascii=False))
        print('Using from:', from_attr, 'to:', to_attr)

    # check current status
    stat_url = f"https://io.zx.tcljd.com/device/getdevicestatus?tid={tid}&category=AC&v={int(time.time()*1000)}"
    code, h, body = http_get(
        stat_url,
        headers={
            'user-agent': headers.get('user-agent','Mozilla/5.0'),
            'origin': 'https://h5.zx.tcljd.com',
            'x-requested-with': 'com.tcl.tclplus',
            'accept': 'text/plain, */*; q=0.01',
            'accept-encoding': headers.get('accept-encoding', 'gzip, deflate, br, zstd'),
        },
        no_verify=args.no_verify,
    )
    print('\nBefore control - status HTTP', code)
    try:
        j = json.loads(body)
        beep_before = j.get('curStatus', {}).get('beepEn')
        print('beepEn before:', beep_before)
    except Exception:
        print('Failed to parse status before')

    # build XML message
    seq = int(time.time() % 100000)
    msg_id = f"android_beep_{int(time.time()*1000)}"
    xml = (
        f"<message id=\"{msg_id}\" from=\"{from_attr}\" to=\"{to_attr}\" type=\"chat\" source=\"0\">"
        f"<x xmlns=\"tcl:im:attribute\"><sendtime>{time.strftime('%Y-%m-%d %H:%M:%S')}</sendtime></x>"
        f"<body><msg cmd=\"set\" type=\"control\" action=\"1\" seq=\"{seq}\" devid=\"{tid}\">"
        f"<BeepEnable>off</BeepEnable></msg></body></message>"
    )

    post_body = json.dumps({"source":"APP","params": xml}).encode('utf-8')

    # prepare headers for POST
    post_headers = {}
    for k,v in headers.items():
        post_headers[k] = v
    post_headers['Content-Type'] = 'application/json; charset=UTF-8'

    if args.verbose:
        print('\nPOST', url)
        print('POST headers:', json.dumps(post_headers, indent=2, ensure_ascii=False))
        print('POST body:', xml)

    # send control
    code, h, res = http_post(url, headers=post_headers, body_bytes=post_body, no_verify=args.no_verify)
    print('\nControl POST HTTP', code)
    try:
        print(res)
    except Exception:
        print('[non-text response]')

    # wait a moment and check status again
    time.sleep(1.5)
    code2, h2, body2 = http_get(
        stat_url,
        headers={
            'user-agent': headers.get('user-agent','Mozilla/5.0'),
            'origin': 'https://h5.zx.tcljd.com',
            'x-requested-with': 'com.tcl.tclplus',
            'accept': 'text/plain, */*; q=0.01',
            'accept-encoding': headers.get('accept-encoding', 'gzip, deflate, br, zstd'),
        },
        no_verify=args.no_verify,
    )
    print('\nAfter control - status HTTP', code2)
    try:
        j2 = json.loads(body2)
        beep_after = j2.get('curStatus', {}).get('beepEn')
        print('beepEn after:', beep_after)
    except Exception:
        print('Failed to parse status after')

if __name__ == '__main__':
    main()
