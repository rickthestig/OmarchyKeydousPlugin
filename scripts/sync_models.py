#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Import all Keydous records from an upstream registry or a local registry JSON.

Metadata refresh does not enable unimplemented protocol families or light tables.
"""
import argparse
import json
from pathlib import Path
import urllib.request

URL = 'https://raw.githubusercontent.com/dniminenn/sharkfin/master/app/src-tauri/data/devices.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-file', type=Path)
    args = parser.parse_args()
    if args.from_file:
        raw = args.from_file.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=30) as response:
            raw = response.read(8 * 1024 * 1024)
    records = [r for r in json.loads(raw) if any(r.get(k, '').lower() == 'keydous' for k in ('company', 'vendor'))]
    if not records:
        raise ValueError('Registry contains no Keydous records')
    for record in records:
        for key in ('id', 'vendorId', 'productId', 'profiles'):
            if type(record.get(key)) is not int:
                raise ValueError('Invalid registry field: ' + key)
        if not 1 <= record['profiles'] <= 16:
            raise ValueError('Invalid profile count')
    target = Path(__file__).resolve().parent.parent / 'keydous-models.json'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(records, indent=2) + '\n')
    temp.replace(target)
    rules = '# Application-mode USB IDs are shared; model capabilities are checked after identification.\n'
    for vid, pid in sorted({(r['vendorId'], r['productId']) for r in records}):
        rules += f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{vid:04x}", ATTRS{{idProduct}}=="{pid:04x}", TAG+="uaccess"\n'
    (target.parent / 'udev/70-keydous-nj81-max.rules').write_text(rules)
    print(f'Imported {len(records)} Keydous records to {target.name}')


if __name__ == '__main__':
    main()
