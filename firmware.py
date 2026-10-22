# SPDX-License-Identifier: GPL-3.0-or-later
"""Firmware metadata/download only. The exact board's boot transport is not yet verified."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

API = 'https://api2.rongyuan.tech:3816/api/v2/get_fw_version'
DOWNLOAD = 'https://api2.rongyuan.tech:3816/download/'
MAX_PACKAGE = 32 * 1024 * 1024


def record_failure(device_id, status, body):
    folder = Path.home() / '.local/state/omarchy-keydous/firmware'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = folder / 'last-check-error.json'
    detail = body.decode('utf-8', errors='replace')[:8192]
    try:
        detail = json.loads(detail)
    except ValueError:
        pass
    diagnostic = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      endpoint=API, request={'dev_id':device_id}, httpStatus=status,
                      response=detail, updateStatus='unknown')
    temp = folder / '.last-check-error.tmp'
    temp.write_text(json.dumps(diagnostic,indent=2)+'\n')
    temp.chmod(0o600)
    temp.replace(target)


def server_error(device_id, status, body=b''):
    record_failure(device_id,status,body)
    if status == 500:
        return ValueError(f'Vendor firmware server returned HTTP 500 for device {device_id}. '
                          'The service may be failing or have no published package for this model. '
                          'Update status is unknown; try again later.')
    return ValueError(f'Vendor firmware server returned HTTP {status}. Update status is unknown.')


def check(device_id, current):
    request = urllib.request.Request(API, data=json.dumps({'dev_id': device_id}).encode(),
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                                              'Origin': 'https://qmk.top', 'Referer': 'https://qmk.top/',
                                              'User-Agent': 'Omarchy-Keydous/0.2'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(1024*1024+1)
    except urllib.error.HTTPError as error:
        try:
            detail = error.read(8192)
        finally:
            error.close()
        raise server_error(device_id,error.code,detail) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ValueError('Could not reach the vendor firmware server. Update status is unknown.') from error
    try:
        if len(raw) > 1024*1024:
            raise ValueError('Oversized response')
        body = json.loads(raw)
        if not isinstance(body,dict):
            raise ValueError('Expected a response object')
    except ValueError as error:
        record_failure(device_id,200,raw[:8192])
        raise ValueError('Vendor firmware server returned an invalid response. Update status is unknown.') from error
    code = body.get('code', body.get('errCode'))
    if code != 0 or not isinstance(body.get('data'), dict):
        record_failure(device_id,200,raw[:8192])
        raise ValueError('Vendor firmware catalogue could not return a package for this model. Update status is unknown.')
    data = body['data']
    version = data.get('version_str', '')
    if not isinstance(version, str) or len(version) > 500:
        raise ValueError('Invalid firmware version response')
    match = re.search(r'(?:^|_)usb_([0-9a-fA-F]+)(?:_|$)', version)
    newer = int(match[1], 16) > int(current, 16) if match else None
    return dict(kind='firmware', deviceId=device_id, current=current, version=version,
                available=newer, downloadPath=data.get('file_path', data.get('path', '')),
                message=('Update available' if newer else 'No newer USB version reported') if match else 'Vendor replied without a comparable USB version',
                flashSupported=False)


def package_url(path):
    if not isinstance(path, str) or not path or len(path) > 2048:
        raise ValueError('Vendor returned no firmware package path')
    parts = urllib.parse.urlsplit(path)
    if parts.scheme or parts.netloc or '..' in path.split('/') or '\\' in path or parts.query or parts.fragment:
        raise ValueError('Unexpected firmware download path')
    return DOWNLOAD + urllib.parse.quote(path.lstrip('/'), safe='/._-')


def download(metadata):
    url = package_url(metadata['downloadPath'])
    folder = Path.home() / '.local/state/omarchy-keydous/firmware'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=25) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname != 'api2.rongyuan.tech':
            raise ValueError('Firmware download redirected to an unexpected host')
        data = response.read(MAX_PACKAGE+1)
    if not data or len(data) > MAX_PACKAGE:
        raise ValueError('Firmware package is empty or exceeds 32 MB')
    checksum = hashlib.sha256(data).hexdigest()
    path = folder / f'4207-{checksum[:16]}.package'
    path.write_bytes(data)
    metadata = dict(metadata, sha256=checksum, path=str(path), bytes=len(data))
    metadata_path = path.with_suffix('.json')
    metadata_path.write_text(json.dumps(metadata, indent=2)+'\n')
    members = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [dict(name=i.filename, bytes=i.file_size) for i in archive.infolist()[:100]]
    return dict(kind='firmware', **{k:v for k,v in metadata.items() if k!='kind'}, members=members,
                downloadMessage='Package saved for inspection; keyboard firmware was not changed')
