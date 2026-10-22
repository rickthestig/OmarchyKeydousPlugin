# SPDX-License-Identifier: GPL-3.0-or-later
"""Keydous records, never inferred from product names or a shared USB ID.

Evidence: https://github.com/dniminenn/sharkfin/blob/master/app/src-tauri/data/devices.json
Protocol: https://github.com/dniminenn/sharkfin/blob/master/docs/PROTOCOL.md
Unknown families are deliberately detection-only. New records can be imported
with scripts/sync_models.py; importing metadata does not enable new protocols.
"""
import json
from pathlib import Path

MODELS = {}
for record in json.loads(Path(__file__).with_name('keydous-models.json').read_text()):
    if any(record.get(k, '').lower() == 'keydous' for k in ('company', 'vendor')):
        MODELS[record['id']] = record


def capabilities(record):
    family = record.get('family')
    # Full advanced controls and firmware transport remain exact-model features.
    advanced = record['id'] == 4207
    lighting = family == 'gen2' and record.get('lightLayout') == 'v'
    return dict(lighting=lighting, paint=lighting or record['id'] == 1259, profiles=family in ('gen2', 'yc500'),
                keymap=family in ('gen2', 'yc500'), advanced=advanced, firmware=advanced)


def spec(device_id):
    return MODELS.get(device_id, dict(id=device_id, displayName=f'Unregistered keyboard {device_id}',
                                     family='unknown', profiles=0, keyLayout='Unknown', lightLayout=''))


def profile_op(record):
    return 0x85 if record.get('family') == 'yc500' else 0x84
