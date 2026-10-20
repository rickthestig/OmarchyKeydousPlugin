#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the user-owned plugin, optionally adding it to the bar. No root changes."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile

PLUGIN_ID = 'eg.keydous'
RUNTIME = ('manifest.json', 'Panel.qml', 'bridge.py', 'advanced.py', 'native.py',
           'firmware.py', 'iot_linux.py', 'README.md', 'LICENSE')


def install(source, config_home, state_home, enable=False):
    source, config_home, state_home = map(Path, (source, config_home, state_home))
    for name in RUNTIME:
        if not (source/name).is_file():
            raise ValueError('Missing package file: '+name)
    if not (source/'docs').is_dir():
        raise ValueError('Missing package documentation')
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest.get('id') != PLUGIN_ID:
        raise ValueError('Unexpected plugin ID')
    destination = config_home/'omarchy/plugins'/PLUGIN_ID
    shell = config_home/'omarchy/shell.json'
    config = None
    if enable:
        config = json.loads(shell.read_text()) if shell.exists() else {'version':1}
        if not isinstance(config,dict):
            raise ValueError('shell.json must contain an object')
        layout = config.setdefault('bar',{}).setdefault('layout',{})
        if not isinstance(layout,dict):
            raise ValueError('bar.layout must contain an object')
        exists = any(isinstance(row,dict) and row.get('id') == PLUGIN_ID
                     for rows in layout.values() if isinstance(rows,list) for row in rows)
        if not exists:
            layout.setdefault('right',[]).append({'id':PLUGIN_ID})
        disabled = config.get('disabledPlugins')
        if isinstance(disabled,list):
            config['disabledPlugins'] = [value for value in disabled if value != PLUGIN_ID]
    if source.resolve() == destination.resolve():
        raise ValueError('Already running from the installed plugin folder; use Omarchy to enable it')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    backup = state_home/'omarchy-keydous/install-backups'/stamp
    backup.mkdir(parents=True,mode=0o700)
    if destination.exists():
        shutil.copytree(destination,backup/'plugin',symlinks=True)
    if config is not None and shell.exists():
        shutil.copy2(shell,backup/'shell.json')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.keydous-install-',dir=destination.parent) as temp:
        staging = Path(temp)/PLUGIN_ID
        staging.mkdir()
        for name in RUNTIME:
            shutil.copy2(source/name,staging/name)
        shutil.copytree(source/'docs',staging/'docs')
        retired = Path(temp)/'previous'
        if destination.exists() or destination.is_symlink():
            destination.rename(retired)
        try:
            staging.rename(destination)
        except Exception:
            if retired.exists() or retired.is_symlink():
                retired.rename(destination)
            raise
    if config is not None:
        with tempfile.NamedTemporaryFile(mode='w',prefix='.keydous-shell-',dir=shell.parent,delete=False) as stream:
            path=Path(stream.name)
            json.dump(config,stream,indent=2)
            stream.write('\n')
        path.chmod(shell.stat().st_mode & 0o777 if shell.exists() else 0o600)
        path.replace(shell)
    return destination,backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable',action='store_true',help='Add the widget to the right side of the bar if absent')
    args=parser.parse_args()
    home=Path.home()
    config=Path(os.environ.get('XDG_CONFIG_HOME') or home/'.config')
    state=Path(os.environ.get('XDG_STATE_HOME') or home/'.local/state')
    destination,backup=install(Path(__file__).resolve().parent.parent,config,state,args.enable)
    print('Installed:',destination)
    print('Backup:',backup)
    print('If the old widget remains visible, run: omarchy restart shell')


if __name__ == '__main__':
    main()
