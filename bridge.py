#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Model-aware Keydous controls. Standard-library Linux HID feature reports only."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time
from models import MODELS, spec, capabilities, profile_op

DEVICE_ID = 4207
MODES = {1: 'Static', 2: 'Breathing', 3: 'Spectrum', 4: 'Wave', 5: 'Ripple',
         6: 'Stars', 7: 'Flow', 8: 'Key shadow', 9: 'Layers', 10: 'Sine',
         11: 'Spring', 12: 'Neon', 14: 'Radiant', 15: 'Loop', 16: 'Colour grid',
         17: 'Snowfall', 18: 'Meteor', 19: 'Silent snow'}


def packet(op, payload=(), bit8=False):
    data = bytearray(64)
    data[0] = op
    data[1:1 + len(payload)] = bytes(payload)
    offset = 8 if bit8 else 7
    data[offset] = 255 - (sum(data[:offset]) & 255)
    return data


def candidates():
    result = []
    for entry in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
        try:
            info = dict(line.split('=', 1) for line in (entry / 'device/uevent').read_text().splitlines() if '=' in line)
            desc = (entry / 'device/report_descriptor').read_bytes()
            # Exact vendor feature collection; never open the typing interfaces.
            pairs = {(r['vendorId'], r['productId']) for r in MODELS.values()}
            hid = info.get('HID_ID', '').split(':')
            pair = (int(hid[1], 16), int(hid[2], 16)) if len(hid) == 3 else None
            if pair in pairs and b'\x06\xff\xff\x09\x02' in desc:
                result.append('/dev/' + entry.name)
        except (OSError, ValueError):
            continue
    return result


class Keyboard:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            identity = self.get(0x8f)
            self.device_id = int.from_bytes(identity[1:5], 'little')
            self.firmware = f'{int.from_bytes(identity[7:9], "little"):04x}'
        except Exception:
            os.close(self.fd)
            raise

    @property
    def model(self):
        return spec(self.device_id)

    @property
    def caps(self):
        return capabilities(self.model)

    @property
    def profile_opcode(self):
        return profile_op(self.model)

    def close(self):
        os.close(self.fd)

    def send(self, data):
        # HIDIOCSFEATURE(65), report ID 0 plus 64-byte payload.
        buf = bytearray(b'\0' + bytes(data))
        fcntl.ioctl(self.fd, 0xC0414806, buf, True)
        time.sleep(0.03)

    def get(self, op):
        self.send(packet(op))
        for _ in range(4):
            buf = bytearray(65)
            fcntl.ioctl(self.fd, 0xC0414807, buf, True)
            reply = bytes(buf[1:])
            if reply[0] == op:
                return reply
            time.sleep(0.04)
        raise ValueError(f'Keyboard did not return a valid reply to 0x{op:02x}. Use a USB cable and close other keyboard configurators.')

    def state(self):
        base = dict(connected=True, deviceId=self.device_id, firmware=self.firmware,
                    modelName=self.model['displayName'], family=self.model['family'],
                    profileCount=self.model['profiles'], capabilities=self.caps, modes=[])
        if not self.caps['profiles']:
            return dict(base, profile=0, compatibility='Detected; protocol is not supported. Writes are disabled.')
        profile = self.get(self.profile_opcode)[1]
        if profile >= self.model['profiles']:
            raise ValueError('Unexpected profile response for this model')
        if not self.caps['lighting']:
            return dict(base, profile=profile, compatibility='Keymap reads available; lighting table is not supported for this model.')
        light = self.get(0x87)
        if light[2] > 4 or light[3] > 4 or profile > 3:
            raise ValueError('Unexpected settings response; controls disabled for this firmware.')
        return dict(base, mode=light[1], speed=4-light[2], brightness=light[3],
                    flags=light[4], color='#' + light[5:8].hex(), profile=profile,
                    modes=[dict(value=k, label=v) for k, v in MODES.items()])

    def backup(self, state):
        folder = Path.home() / '.local/state/omarchy-keydous'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = folder / 'before-last-change.json'
        temp = folder / f'.backup-{os.getpid()}'
        temp.write_text(json.dumps(state, indent=2) + '\n')
        temp.chmod(0o600)
        temp.replace(target)

    def apply(self, args):
        if not self.caps.get('lighting' if args.action == 'light' else 'profiles'):
            raise ValueError('This operation is not supported for the detected model')
        if args.action == 'profile' and not 0 <= args.profile < self.model['profiles']:
            raise ValueError('Profile is out of range for the detected model')
        state = self.state()
        self.backup(state)
        if args.action == 'profile':
            self.send(packet(self.profile_opcode & 0x7f, [args.profile]))
            time.sleep(0.25)
            if self.get(self.profile_opcode)[1] != args.profile:
                raise ValueError('Profile change did not read back.')
        elif args.action == 'light':
            mode = args.mode if args.mode is not None else state['mode']
            if mode not in MODES:
                raise ValueError('Choose a built-in lighting effect before applying changes.')
            speed = args.speed if args.speed is not None else state['speed']
            brightness = args.brightness if args.brightness is not None else state['brightness']
            flags = state['flags']
            color = bytes.fromhex(state['color'][1:])
            if args.color:
                color = bytes.fromhex(args.color.lstrip('#'))
                if color == b'\xff\xff\xff':
                    color = b'\xfa\xfa\xfa'
                flags = (flags & 0xf0) | 7
            if args.rainbow:
                flags = (flags & 0xf0) | 8
            if args.mode is not None and mode != state['mode']:
                flags &= 15  # default direction for a new effect
            self.send(packet(0x07, [mode, 4-speed, brightness, flags, *color], bit8=True))
            check = self.get(0x87)
            expected = bytes([mode, 4-speed, brightness, flags, *color])
            if check[1:8] != expected:
                raise ValueError('Lighting write did not read back exactly. Refresh before retrying.')
        return self.state()


def bounded(low, high):
    def parse(value):
        n = int(value)
        if not low <= n <= high:
            raise argparse.ArgumentTypeError(f'expected {low}..{high}')
        return n
    return parse


def rgb(value):
    if not re.fullmatch(r'#?[0-9a-fA-F]{6}', value):
        raise argparse.ArgumentTypeError('expected #RRGGBB')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'light', 'profile'])
    parser.add_argument('--mode', type=int, choices=list(MODES))
    parser.add_argument('--speed', type=bounded(0, 4))
    parser.add_argument('--brightness', type=bounded(0, 4))
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--color', type=rgb)
    group.add_argument('--rainbow', action='store_true')
    parser.add_argument('--profile', type=bounded(0, 15))
    args = parser.parse_args()
    if args.action == 'profile' and args.profile is None:
        parser.error('profile requires --profile (zero-based onboard index)')
    try:
        paths = candidates()
        if not paths:
            raise ValueError('No registered Keydous USB interface found. Connect it with a USB cable.')
        if len(paths) != 1:
            raise ValueError('Multiple matching keyboards found. Connect one Keydous keyboard at a time.')
        keyboard = Keyboard(paths[0])
        try:
            result = keyboard.state() if args.action == 'status' else keyboard.apply(args)
        finally:
            keyboard.close()
    except PermissionError:
        result = dict(connected=False, error='Keyboard access denied. See README.md for the device permission rule.')
    except FileNotFoundError:
        result = dict(connected=False, error='Keyboard HID device is unavailable in this session. Reconnect it and refresh.')
    except (OSError, ValueError) as e:
        result = dict(connected=False, error=str(e))
    print(json.dumps(result))
    return 0 if result.get('connected') else 1


if __name__ == '__main__':
    sys.exit(main())
