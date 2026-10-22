#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""JSON entry point for native settings. Each invocation holds one device lock."""
import json
import sys
import subprocess
import urllib.error
from advanced import AdvancedKeyboard, snapshot
from bridge import candidates
import firmware


def dispatch(request):
    paths = candidates()
    if len(paths) != 1:
        raise ValueError('Connect exactly one registered Keydous keyboard by USB cable')
    keyboard = AdvancedKeyboard(paths[0])
    try:
        action = request.get('action')
        if action in ('firmware-check', 'firmware-download'):
            if not keyboard.caps['firmware']:
                raise ValueError('Firmware operations are not validated for this model')
            result = firmware.check(keyboard.device_id, keyboard.firmware)
            if action == 'firmware-download':
                result = firmware.download(result)
            return dict(result, ok=True, connected=True)
        return keyboard.execute(request)
    finally:
        keyboard.close()


def main():
    try:
        if len(sys.argv) != 2 or len(sys.argv[1]) > 10000:
            raise ValueError('Expected one settings request')
        request = json.loads(sys.argv[1])
        if not isinstance(request, dict):
            raise ValueError('Settings request must be an object')
        result = dispatch(request)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        result = dict(ok=False, error=str(error))
    print(json.dumps(result))
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
