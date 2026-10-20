#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate or build an allowlisted, reproducible plugin source archive."""
import argparse
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    '.gitignore', '.github/workflows/checks.yml', 'manifest.json', 'Panel.qml',
    'bridge.py', 'advanced.py', 'native.py', 'firmware.py', 'iot_linux.py',
    'README.md', 'LICENSE', 'CHANGELOG.md', 'CONTRIBUTING.md', 'PUBLISHING.md',
    'docs/usage.md', 'docs/firmware.md', 'docs/github-upload.md', 'udev/70-keydous-nj81-max.rules',
    'scripts/install.py', 'scripts/package.py',
    'tests/test_bridge.py', 'tests/test_native.py', 'tests/test_distribution.py', 'tests/test_install.py',
)


def validate(root=ROOT):
    root=Path(root)
    for name in FILES:
        path=root/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or linked distribution file: '+name)
        content=path.read_text(encoding='utf-8')
        if re.search(r'/home/[A-Za-z0-9_.-]+/',content):
            raise ValueError('Personal absolute path in distribution: '+name)
    metadata=json.loads((root/'manifest.json').read_text())
    if metadata.get('id') != 'eg.keydous' or metadata.get('license') != 'GPL-3.0-or-later':
        raise ValueError('Unexpected plugin identity or license')
    version=metadata.get('version','')
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):
        raise ValueError('Invalid release version')
    entry=metadata.get('entryPoints',{}).get('barWidget')
    if entry not in FILES or not entry.endswith('.qml'):
        raise ValueError('Entry point missing from package')
    return version


def build(root=ROOT, output=None):
    root=Path(root)
    version=validate(root)
    output=Path(output) if output else root/'dist'/f'omarchy-keydous-{version}.zip'
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(FILES):
            info=zipfile.ZipInfo('eg.keydous/'+name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.create_system=3
            info.external_attr=0o100644<<16
            archive.writestr(info,(root/name).read_bytes())
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.check:
        print(f'Validated {len(FILES)} source files for {validate()}')
    else:
        print(build())


if __name__ == '__main__':
    main()
