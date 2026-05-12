#!/usr/bin/env python3
"""Send BeepEnable off and verify using captures (independent, avoids editing truncated file).

Usage:
  python3 tools/control_beep_run.py --verbose
"""
from pathlib import Path
import json,re,sys,ssl,urllib.request,time

CAPTURE='captures/tcl_1770274433.jsonl'


def find_last_convert(capture_file:Path):
    text=capture_file.read_text(encoding='utf-8',errors='replace')
    last=None
    for line in text.splitlines():
        try:
            j=json.loads(line)
        except Exception:
            continue
        if j.get('type')=='request' and '/v1/control/convertMqtt/' in j.get('url',''):
            last=j
    return last


def http_get(url, headers=None, no_verify=False):
    ctx=None
    if no_verify:
        ctx=ssl._create_unverified_context()
    req=urllib.request.Request(url, headers=headers or {}, method='GET')
    with urllib.request.urlopen(req, timeout=15, context=ctx) as fp:
        return fp.getcode(), fp.headers, fp.read().decode('utf-8',errors='replace')


def http_post(url, headers, data_bytes, no_verify=False):
    ctx=None
    if no_verify:
        ctx=ssl._create_unverified_context()
    req=urllib.request.Request(url, data=data_bytes, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=15, context=ctx) as fp:
        return fp.getcode(), fp.headers, fp.read().decode('utf-8',errors='replace')


def extract_from_to(params_xml):
    m_from=re.search(r'from="([^"]+)"', params_xml)
    m_to=re.search(r'to="([^"]+)"', params_xml)
    return (m_from.group(1) if m_from else None, m_to.group(1) if m_to else None)


def main():
    cap=Path(CAPTURE)
    if not cap.exists():
        print('capture not found', cap); sys.exit(2)
    last=find_last_convert(cap)
    if not last:
        print('no convert entry in capture'); sys.exit(3)
    url=last['url']
    tid=url.rstrip('/').split('/')[-1]
    raw_headers=last.get('headers',{})
    headers={}
    for k in ['platform','user-agent','apppackagename','systemversion','brand','appversion','sdkversion','accesstoken','channel','appbuildversion','t-app-version','t-platform-type','t-store-uuid','content-type','accept-encoding']:
        if k in raw_headers:
            headers[k]=raw_headers[k]
        elif k.title() in raw_headers:
            headers[k]=raw_headers[k.title()]
    headers['Content-Type']='application/json; charset=UTF-8'

    # extract from/to
    body_str=last.get('body','')
    pm=re.search(r'"params"\s*:\s*"(.*?)"', body_str, re.S)
    params_xml=pm.group(1).replace('\\"','"') if pm else ''
    frm,to = extract_from_to(params_xml)
    if not frm: frm='14427826@tcl.com/PH-android-zx01-2'
    if not to: to=f"{tid}@tcl.com/AC-linux-zx01-1"

    print('Sending BeepEnable off ->', tid)
    # check before
    stat_url=f"https://io.zx.tcljd.com/device/getdevicestatus?tid={tid}&category=AC&v={int(time.time()*1000)}"
    code,_,b = http_get(stat_url, headers={'user-agent': headers.get('user-agent','Mozilla/5.0'),'origin':'https://h5.zx.tcljd.com'}, no_verify=False)
    print('Before status HTTP', code)
    try:
        j=json.loads(b)
        print('beepEn before:', j.get('curStatus',{}).get('beepEn'))
    except Exception:
        print('could not parse before')

    seq=int(time.time()%100000)
    mid=f"android_beep_{int(time.time()*1000)}"
    xml=f'<message id="{mid}" from="{frm}" to="{to}" type="chat" source="0"><x xmlns="tcl:im:attribute"><sendtime>{time.strftime("%Y-%m-%d %H:%M:%S")}</sendtime></x><body><msg cmd="set" type="control" action="1" seq="{seq}" devid="{tid}"><BeepEnable>off</BeepEnable></msg></body></message>'
    post_body=json.dumps({"source":"APP","params": xml}).encode('utf-8')
    code2,_,r = http_post(url, headers=headers, data_bytes=post_body, no_verify=False)
    print('Control POST HTTP', code2)
    print(r[:1000])

    time.sleep(1.5)
    code3,_,b2 = http_get(stat_url, headers={'user-agent': headers.get('user-agent','Mozilla/5.0'),'origin':'https://h5.zx.tcljd.com'}, no_verify=False)
    print('After status HTTP', code3)
    try:
        j2=json.loads(b2)
        print('beepEn after:', j2.get('curStatus',{}).get('beepEn'))
    except Exception:
        print('could not parse after')

if __name__=='__main__':
    main()
