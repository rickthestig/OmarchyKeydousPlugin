# SPDX-License-Identifier: GPL-3.0-or-later
"""Model-aware Keydous lighting; advanced writes limited to NJ81 MAX-CP.

Protocol reference: dniminenn/sharkfin docs/PROTOCOL.md. No boot/erase opcodes.
"""
import datetime
import hashlib
import json
import math
import os
import re
from pathlib import Path
import struct
import subprocess
import time

from bridge import Keyboard, DEVICE_ID, packet
from models import spec

NAMES = {0: 'Disabled / inherited', 40: 'Enter', 41: 'Escape', 42: 'Backspace',
         43: 'Tab', 44: 'Space', 45: '-', 46: '=', 47: '[', 48: ']', 49: '\\',
         51: ';', 52: "'", 53: '`', 54: ',', 55: '.', 56: '/', 57: 'Caps Lock',
         70: 'Print Screen', 71: 'Scroll Lock', 72: 'Pause', 73: 'Insert',
         74: 'Home', 75: 'Page Up', 76: 'Delete', 77: 'End', 78: 'Page Down',
         79: 'Right', 80: 'Left', 81: 'Down', 82: 'Up',
         224: 'Left Ctrl', 225: 'Left Shift', 226: 'Left Alt', 227: 'Left Super',
         228: 'Right Ctrl', 229: 'Right Shift', 230: 'Right Alt', 231: 'Right Super'}
NAMES.update({83: 'Num Lock', 84: 'Num /', 85: 'Num *', 86: 'Num -', 87: 'Num +', 88: 'Num Enter', 98: 'Num 0', 99: 'Num .'})
NAMES.update({89+i: 'Num '+str(i+1) for i in range(9)})
NAMES.update({4+i: chr(65+i) for i in range(26)})
NAMES.update({30+i: str((i+1) % 10) for i in range(10)})
NAMES.update({58+i: 'F'+str(i+1) for i in range(12)})
SUBOPS = {'actuation': 0, 'release': 1, 'pressStep': 2, 'releaseStep': 3,
          'deadzone': 6, 'keyMode': 7}


def integer(value, lo, hi, label):
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise ValueError(f'{label} must be an integer in {lo}..{hi}')
    return value


def key_label(value):
    kind, modifier, code, extra = value
    if kind == 0:
        name = NAMES.get(code, f'HID {code:02x}')
        mods = [n for bit, n in enumerate(['Ctrl', 'Shift', 'Alt', 'Super', 'RCtrl', 'RShift', 'RAlt', 'RSuper']) if modifier & (1 << bit)]
        return '+'.join(mods+[name]) + (f' + HID {extra:02x}' if extra else '')
    if kind == 10 and modifier == 1:
        return 'Fn'
    if kind == 9:
        return f'Macro {code + 1}'
    if kind == 3:
        return f'Media 0x{code | extra << 8:04x}'
    return f'Type {kind:02x} · ' + bytes(value).hex(' ')


def key_choices():
    choices = [dict(label=name, value=[0, 0, code, 0]) for code, name in sorted(NAMES.items())]
    choices += [dict(label=name, value=[3, 0, code & 255, code >> 8]) for name, code in
                [('Volume up', 0xe9), ('Volume down', 0xea), ('Mute', 0xe2), ('Play / pause', 0xcd), ('Next track', 0xb5), ('Previous track', 0xb6)]]
    return choices


def paint_layout(device_id, matrix):
    """Detect geometry by exact device record; resolve only unique live usages.

    Remaps cannot reveal physical locations. Persist resolved positions once,
    and leave ambiguous/unmapped positions disabled rather than guessing.
    """
    if spec(device_id).get('keyLayout') != 'Common81_NJ81MAX':
        return dict(name=spec(device_id)['displayName'] + ' · hardware slots', keys=[], width=16, height=6.4, unresolved=0)
    positions = []
    def row(y, entries):
        x = 0
        for code, label, width in entries:
            positions.append(dict(code=code, label=label, x=x, y=y, w=width, h=1))
            x += width
    positions.append(dict(code=41, label='Esc', x=0, y=0, w=1, h=1))
    for i in range(12):
        positions.append(dict(code=58+i, label=f'F{i+1}', x=1.5+i+(i//4)*0.25, y=0, w=1, h=1))
    row(1.4, [(53,'`',1)] + [(30+i,str((i+1)%10),1) for i in range(10)] +
        [(45,'-',1),(46,'=',1),(42,'Backspace',2),(76,'Del',1)])
    row(2.4, [(43,'Tab',1.5)] + [(ord(c)-97+4,c.upper(),1) for c in 'qwertyuiop'] +
        [(47,'[',1),(48,']',1),(49,'Backslash',1.5),(75,'PgUp',1)])
    row(3.4, [(57,'Caps',1.75)] + [(ord(c)-97+4,c.upper(),1) for c in 'asdfghjkl'] +
        [(51,';',1),(52,"'",1),(40,'Enter',2.25),(78,'PgDn',1)])
    row(4.4, [(225,'Shift',2.25)] + [(ord(c)-97+4,c.upper(),1) for c in 'zxcvbnm'] +
        [(54,',',1),(55,'.',1),(56,'/',1),(229,'Shift',1.75),(82,'↑',1),(77,'End',1)])
    row(5.4, [(224,'Ctrl',1.25),(227,'Super',1.25),(226,'Alt',1.25),(44,'Space',6.25),
              (230,'Alt',1),('fn','Fn',1),(228,'Ctrl',1),(80,'←',1),(81,'↓',1),(79,'→',1)])
    folder = Path.home() / '.local/state/omarchy-keydous'
    path = folder / f'layout-{device_id}.json'
    cached = json.loads(path.read_text()) if path.exists() else {}
    tokens = {str(key['code']) for key in positions}
    cached = {token: slot for token, slot in cached.items() if token in tokens}
    slots = {}
    for i, value in enumerate(matrix[:126]):
        token = 'fn' if value[:2] == [10, 1] else value[2] if value[:2] == [0, 0] and value[3] == 0 else None
        if token is not None:
            slots.setdefault(str(token), []).append(i)
    # Cached positions remain stable when the user later remaps a key.
    used = set(cached.values())
    for key in positions:
        token = str(key['code'])
        candidates = slots.get(token, [])
        if token not in cached and len(candidates) == 1 and candidates[0] not in used:
            cached[token] = candidates[0]
            used.add(candidates[0])
        key['slot'] = cached.get(token, -1)
        key['assignment'] = key_label(matrix[key['slot']]) if key['slot'] >= 0 else 'Unresolved — use slot view'
    if cached:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(cached) + '\n')
        temp.chmod(0o600)
        temp.replace(path)
    return dict(name='Keydous NJ81 MAX · 75% · 81 keys', keys=positions, width=16, height=6.4,
                unresolved=sum(k['slot'] < 0 for k in positions))


def snapshot(kind, value, device_id=DEVICE_ID):
    folder = Path.home() / '.local/state/omarchy-keydous/backups'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = folder / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + kind + '.json')
    body = dict(schemaVersion=1, deviceId=device_id, kind=kind, savedAt=datetime.datetime.now().isoformat(), data=value)
    with target.open('x') as stream:
        json.dump(body, stream, indent=2)
        stream.write('\n')
    target.chmod(0o600)
    return str(target)


def screen_pixels(path):
    source = Path(path).expanduser().resolve()
    if not source.is_file() or source.stat().st_size > 32*1024*1024:
        raise ValueError('Choose an image file smaller than 32 MB')
    result = subprocess.run(['magick', '-limit', 'memory', '128MiB', '-limit', 'disk', '256MiB',
                             str(source)+'[0]', '-auto-orient', '-resize', '160x80^',
                             '-gravity', 'center', '-extent', '160x80', '-depth', '8', 'rgb:-'],
                            capture_output=True, timeout=20, check=True)
    if len(result.stdout) != 160*80*3:
        raise ValueError('Image conversion returned an unexpected size')
    return rgb565_columns(result.stdout)


def rgb565_columns(rgb):
    if len(rgb) != 160*80*3:
        raise ValueError('Expected a 160 by 80 RGB image')
    pixels = bytearray()
    for x in range(160):
        for y in range(80):
            at = (y*160+x)*3
            r,g,b = rgb[at:at+3]
            word = ((r>>3)<<11) | ((g>>2)<<5) | (b>>3)
            pixels.extend(word.to_bytes(2,'big'))
    return bytes(pixels)


class AdvancedKeyboard(Keyboard):
    def snapshot(self, kind, value):
        return snapshot(kind, value, device_id=self.device_id)

    def exchange(self, op, payload=(), raw=False):
        request = packet(op, payload)
        self.send(request)
        for _ in range(5):
            import fcntl
            buf = bytearray(65)
            fcntl.ioctl(self.fd, 0xC0414807, buf, True)
            reply = bytes(buf[1:])
            # Raw bulk pages do not echo the command. A full request echo means
            # unsupported; an all-FF response is also unhandled on this family.
            if (not raw or reply != bytes(request)) and reply != b'\xff'*64 and (raw or reply[0] == op):
                return reply
            time.sleep(0.04)
        raise ValueError(f'Command 0x{op:02x} is unsupported or returned a stale reply.')

    def guard_profile(self, request):
        expected = integer(request.get('profile'), 0, self.model['profiles']-1, 'Profile')
        actual = self.get(self.profile_opcode)[1]
        if expected != actual:
            raise ValueError('The onboard profile changed. Reload this tab before applying.')
        return actual

    def matrix(self, profile, host, layer):
        integer(profile, 0, self.model['profiles']-1, 'Profile')
        integer(host, 0, 3, 'Host layer')
        if layer not in ('base', 'fn'):
            raise ValueError('Layer must be base or fn')
        if not self.caps['keymap']:
            raise ValueError('Keymap reads are unsupported for this model')
        if self.model['family'] == 'yc500' and host != 0:
            raise ValueError('Separate host layers are unavailable on this protocol')
        data = bytearray()
        for page in range(8):
            payload = [profile, 255, page, host] if layer == 'base' else [host, profile, 255, page]
            # First put a distinct known response in the receive slot. If the
            # page opcode is ignored, a stale profile reply is rejected.
            baseline = self.get(self.profile_opcode)
            if self.model['family'] == 'yc500':
                payload = [profile, page]
            op = (0x89 if self.model['family'] == 'yc500' else 0x8a) if layer == 'base' else 0x90
            reply = self.exchange(op, payload, raw=True)
            if reply == baseline:
                raise ValueError('Keymap read returned the preceding profile reply.')
            data.extend(reply)
        return [list(data[i:i+4]) for i in range(0, 512, 4)]

    def keys(self, req):
        profile = self.guard_profile(req)
        host = integer(req.get('host', 0), 0, 3, 'Host layer')
        layer = req.get('layer', 'base')
        keys = self.matrix(profile, host, layer)
        return dict(kind='keys', profile=profile, host=host, layer=layer,
                    keys=[dict(slot=i, value=v, label=f'{i:03d} · {key_label(v)}') for i, v in enumerate(keys)],
                    layout=paint_layout(self.device_id, keys if host == 0 and layer == 'base' else self.matrix(profile, 0, 'base')),
                    choices=key_choices())

    def remap(self, req):
        profile = self.guard_profile(req)
        host = integer(req.get('host', 0), 0, 3, 'Host layer')
        layer = req.get('layer', 'base')
        slot = integer(req.get('slot'), 0, 127, 'Slot')
        value = req.get('value')
        if not isinstance(value, list) or len(value) != 4:
            raise ValueError('Key assignment must contain four bytes')
        for n in value:
            integer(n, 0, 255, 'Key byte')
        if value[0] not in (0, 3, 9):
            raise ValueError('Only normal, media and macro assignments are supported')
        if value[0] == 9:
            integer(value[1], 0, 2, 'Macro mode')
            integer(value[2], 0, 49, 'Macro number')
        before = self.matrix(profile, host, layer)
        if before[slot] != req.get('expected'):
            raise ValueError('This key changed since it was loaded. Reload before remapping.')
        if before[slot][0:2] == [10, 1]:
            raise ValueError('The Fn key is protected to retain access to onboard shortcuts.')
        path = self.snapshot('keymap', dict(profile=profile, host=host, layer=layer, keys=before))
        payload = [profile, slot, 0, 0, 1, host] if layer == 'base' else [host, profile, slot]
        data = packet(0x0a if layer == 'base' else 0x10, payload)
        data[8:12] = bytes(value)
        self.send(data)
        time.sleep(0.25)
        after = self.matrix(profile, host, layer)
        if after[slot] != value:
            raise ValueError('Key assignment did not read back. Original map saved at '+path)
        result = self.keys(req)
        result.update(message='Key assignment saved and verified', backup=path)
        return result

    @property
    def paint_count(self):
        return 128 if self.model['family'] == 'yc500' else 126

    def paint_path(self, profile):
        folder = Path.home() / '.local/state/omarchy-keydous'
        if self.device_id != DEVICE_ID:
            folder /= str(self.device_id)
        return folder / f'paint-{profile}.json'

    def paint(self, req):
        profile = self.guard_profile(req)
        path = self.paint_path(profile)
        colors = ['#000000'] * self.paint_count
        if path.exists():
            colors = json.loads(path.read_text())['colors']
        keys = self.matrix(profile, 0, 'base')
        return dict(kind='paint', profile=profile, colors=colors,
                    layout=paint_layout(self.device_id, keys),
                    labels=[f'{i:03d} · {key_label(v)}' for i, v in enumerate(keys[:self.paint_count])],
                    message='Local painting loaded. Existing keyboard patterns cannot be read reliably.')

    def set_paint(self, req):
        if not self.caps['paint']:
            raise ValueError('Per-key painting is not supported for this model lighting table')
        profile = self.guard_profile(req)
        colors = req.get('colors')
        if not isinstance(colors, list) or len(colors) != self.paint_count or any(
                not isinstance(c, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in colors):
            raise ValueError(f'Painting requires exactly {self.paint_count} #RRGGBB colours')
        brightness = integer(req.get('brightness', 4), 0, 4, 'Brightness')
        path = self.paint_path(profile)
        cooldown = path.parent / 'paint-last-upload'
        if cooldown.exists() and time.time() - cooldown.stat().st_mtime < 10:
            raise ValueError('Wait 10 seconds between painting uploads')
        before = self.state()
        previous = json.loads(path.read_text()) if path.exists() else None
        backup = self.snapshot('paint', dict(profile=profile, lighting=before, localPainting=previous,
                                       note='Previous device pattern cannot be read reliably'))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        cooldown.touch(mode=0o600)
        blob = b''.join(bytes.fromhex(c[1:]) for c in colors)
        # USERPIC uses distinct gen2 / yc500 headers and colour counts.
        # Reserve pattern slot 0; mode 13 selects that slot in its high nibble.
        for page, start in enumerate(range(0, len(blob), 56)):
            chunk = blob[start:start+56]
            header = [0, 255, page, len(chunk), int(page == 6)]
            if self.model['family'] == 'yc500':
                header = [0, len(blob) & 255, len(blob) >> 8, page, 0]
            data = packet(0x0c, header)
            data[8:8+len(chunk)] = chunk
            self.send(data)
            time.sleep(0.1)
        time.sleep(2)
        wire_speed = 1 if self.model['family'] == 'yc500' else 0
        self.send(packet(0x07, [13, wire_speed, brightness, 7, 0, 200, 200], bit8=True))
        check = self.get(0x87)
        if check[1:8] != bytes([13, wire_speed, brightness, 7, 0, 200, 200]):
            raise ValueError('Pattern uploaded but lighting mode did not read back. Reload before retrying.')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(dict(colors=colors, profile=profile)) + '\n')
        temp.chmod(0o600)
        temp.replace(path)
        return dict(kind='paint-saved', profile=profile,
                    message='Painting uploaded; custom mode verified. Check colours on the keyboard.', backup=backup)

    def column(self, subop, slot, wide=True):
        per_page = 32 if wide else 64
        baseline = self.get(self.profile_opcode)
        data = self.exchange(0xe5, [subop, 1, slot // per_page], raw=True)
        if data == baseline:
            raise ValueError('Switch settings are unavailable on this firmware')
        offset = (slot % per_page) * (2 if wide else 1)
        return int.from_bytes(data[offset:offset+(2 if wide else 1)], 'little')

    def switches(self, req):
        profile = self.guard_profile(req)
        slot = integer(req.get('slot'), 0, 127, 'Slot')
        version = int(self.firmware, 16)
        if version < 0x300:
            raise ValueError('Switch editing requires a supported firmware scale (3.00 or newer)')
        # The exact 4207 record specifies travel.step=0.01. Unlike many
        # ry5088 boards it stays at 100 counts/mm on legacy firmware >=5.00.
        # Newer firmware announces precision explicitly through E6.
        scale = 100
        try:
            features = self.exchange(0xe6)
            if features[1] == 0xaa:
                if features[2] not in (0, 1, 2):
                    raise ValueError('Unrecognised switch precision')
                scale = (100, 200, 1000)[features[2]]
        except ValueError as error:
            if 'precision' in str(error):
                raise
        values = {name: self.column(op, slot, name != 'keyMode') for name, op in SUBOPS.items()}
        if values['keyMode'] & 127 not in (0, 2, 3, 4, 5, 7):
            raise ValueError('Unexpected switch-mode response; editing disabled')
        if any(values[name] > 1000 for name in ('actuation', 'release', 'pressStep', 'releaseStep', 'deadzone')):
            raise ValueError('Unexpected switch travel response; editing disabled')
        return dict(kind='switches', profile=profile, slot=slot, scale=scale, raw=values,
                    rapidTrigger=bool(values['keyMode'] & 128),
                    **{name: values[name] / scale for name in SUBOPS if name != 'keyMode'})

    def set_switches(self, req):
        before = self.switches(req)
        if req.get('expected') != before['raw']:
            raise ValueError('Switch settings changed. Reload before applying.')
        values = req.get('values', {})
        if not isinstance(values, dict) or not values or set(values) - set(SUBOPS):
            raise ValueError('Unrecognised switch settings')
        raw = {}
        for name, value in values.items():
            if name == 'keyMode':
                if not isinstance(value, bool):
                    raise ValueError('Rapid trigger must be true or false')
                raw[name] = (before['raw']['keyMode'] & 127) | (128 if value else 0)
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Travel values must be finite numbers')
            lo, hi = (0, 1) if name == 'deadzone' else (0.1, 3.3)
            if not lo <= value <= hi:
                raise ValueError(f'{name} must be in {lo}..{hi} mm')
            raw[name] = round(value * before['scale'])
        path = self.snapshot('switches', before)
        # Preserve the lower mode bits; changing RT never changes DKS/mod-tap.
        for name, value in raw.items():
            data = packet(0x65, [SUBOPS[name], 0, before['slot'], 1])
            data[8:10] = value.to_bytes(2, 'little')
            self.send(data)
            time.sleep(0.16)
            check = self.column(SUBOPS[name], before['slot'], name != 'keyMode')
            if check != value:
                raise ValueError(f'{name} did not read back. Reload; original settings: {path}')
        result = self.switches(req)
        result.update(message='Switch settings saved and verified', backup=path)
        return result

    def device(self, req):
        result = dict(kind='device', profile=self.get(self.profile_opcode)[1], firmware=self.firmware,
                      deviceId=self.device_id, options={}, warnings=[])
        for name, op in [('sleep', 0x91), ('autoOS', 0x97), ('reportRateRaw', 0x83), ('keyboardOptions', 0x89)]:
            try:
                data = self.exchange(op)
                if name == 'sleep':
                    result['sleep'] = list(struct.unpack('<4H', data[8:16]))
                elif name == 'autoOS':
                    if data[1] > 1:
                        raise ValueError('Invalid host detection reply')
                    result['autoOS'] = bool(data[1])
                elif name == 'keyboardOptions':
                    if data[1] > 3 or data[4] > 5 or data[5] > 1:
                        raise ValueError('Invalid keyboard-options response')
                    result[name] = list(data[1:6])
                else:
                    result[name] = data[1:7].hex(' ')
                    rates = [8000,4000,2000,1000,500,250,125]
                    if data[2] < len(rates):
                        result['reportRate'] = rates[data[2]]
            except ValueError as e:
                result['warnings'].append(str(e))
        return result

    def set_device(self, req):
        self.guard_profile(req)
        before = self.device(req)
        change = req.get('setting')
        path = self.snapshot('device', before)
        if change == 'sleep':
            values = req.get('value')
            if not isinstance(values, list) or len(values) != 4:
                raise ValueError('Four sleep timer values required')
            for value in values:
                integer(value, 0, 65535, 'Sleep seconds')
            if before.get('sleep') != req.get('expected'):
                raise ValueError('Sleep timers changed. Reload first.')
            data = packet(0x11)
            data[8:16] = struct.pack('<4H', *values)
            self.send(data)
            time.sleep(0.2)
            if list(struct.unpack('<4H', self.exchange(0x91)[8:16])) != values:
                raise ValueError('Sleep timers did not read back')
        elif change == 'reportRate':
            rates = [8000,4000,2000,1000,500,250,125]
            value = req.get('value')
            if isinstance(value, bool) or value not in rates or before.get('reportRate') != req.get('expected'):
                raise ValueError('Invalid or stale polling rate. Reload first.')
            self.send(packet(0x03, [0, rates.index(value)]))
            time.sleep(0.2)
            if self.exchange(0x83)[2] != rates.index(value):
                raise ValueError('Polling rate did not read back')
        elif change == 'keyboardOptions':
            old = before.get('keyboardOptions')
            if old is None or old != req.get('expected'):
                raise ValueError('Keyboard options changed. Reload first.')
            value = req.get('value', {})
            if not isinstance(value, dict) or set(value) != {'wasdSwap', 'antiAccidental', 'stabilization'}:
                raise ValueError('Invalid keyboard options')
            if not isinstance(value['wasdSwap'], bool) or not isinstance(value['antiAccidental'], bool):
                raise ValueError('Keyboard switches must be boolean')
            stabilization = integer(value['stabilization'], 0, 5, 'Stabilization level')
            updated = old[:]
            updated[2:] = [int(value['antiAccidental']), stabilization, int(value['wasdSwap'])]
            self.send(packet(0x09, updated))
            time.sleep(0.2)
            if list(self.exchange(0x89)[1:6]) != updated:
                raise ValueError('Keyboard options did not read back')
        elif change == 'autoOS':
            value = req.get('value')
            if not isinstance(value, bool) or before.get('autoOS') != req.get('expected'):
                raise ValueError('Host detection state changed. Reload first.')
            self.send(packet(0x17, [int(value)]))
            if self.exchange(0x97)[1] != int(value):
                raise ValueError('Host detection change did not read back')
        else:
            raise ValueError('Unsupported device setting')
        result = self.device(req)
        result.update(message='Device settings saved and verified', backup=path)
        return result

    def macro_read(self, slot):
        data = bytearray()
        for page in range(4):
            baseline = self.get(self.profile_opcode)
            reply = self.exchange(0x8b, [slot, page], raw=True)
            if reply == baseline:
                raise ValueError('Macro read is unsupported')
            data.extend(reply)
        return bytes(data)

    def macro(self, req):
        slot = integer(req.get('macro'), 0, 49, 'Macro')
        data = self.macro_read(slot)
        return dict(kind='macro', macro=slot, digest=hashlib.sha256(data).hexdigest(),
                    raw=data.hex(), repeat=int.from_bytes(data[:2], 'little'),
                    message=f'Macro {slot+1} loaded')

    def macro_text(self, req):
        slot = integer(req.get('macro'), 0, 49, 'Macro')
        text = req.get('text')
        if not isinstance(text, str) or not 1 <= len(text) <= 40:
            raise ValueError('Enter 1..40 ASCII characters')
        before = self.macro_read(slot)
        if hashlib.sha256(before).hexdigest() != req.get('expected'):
            raise ValueError('Macro changed. Reload it first.')
        blob = bytearray([1, 0])
        # Keyboard usages, with explicit shift transitions for uppercase.
        # Delays are 10 ms; each event is code + pressed-bit/delay.
        specials = {' ':44, '\n':40, '\t':43, '-':45, '=':46, '[':47, ']':48,
                    '\\':49, ';':51, "'":52, '`':53, ',':54, '.':55, '/':56}
        shifted = dict(zip('!@#$%^&*()_+{}|:\"~<>?', '1234567890-=[]\\;\'`,./'))
        for char in text:
            base = shifted.get(char, char.lower())
            if 'a' <= base <= 'z':
                usage = ord(base)-ord('a')+4
            elif base in '1234567890':
                usage = '1234567890'.index(base)+30
            elif base in specials:
                usage = specials[base]
            else:
                raise ValueError('Text macros currently support US-layout ASCII only')
            shift = char.isupper() or char in shifted
            if shift:
                blob.extend([225, 128|10])
            blob.extend([usage, 128|10, usage, 10])
            if shift:
                blob.extend([225, 10])
        blob.extend(bytes(4))
        if len(blob) > 256:
            raise ValueError('This text needs more than one macro slot; use fewer characters')
        path = self.snapshot('macro', dict(macro=slot, raw=before.hex()))
        padded = bytes(blob).ljust(256, b'\0')
        for page in range(5):
            data = packet(0x0b, [slot, page, 56, int(page == 4)])
            data[8:64] = padded[page*56:page*56+56].ljust(56, b'\0')
            self.send(data)
            time.sleep(0.1)
        if self.macro_read(slot) != padded:
            raise ValueError('Macro did not read back. Original saved at '+path)
        result = self.macro(req)
        result.update(message='Text macro saved and verified', backup=path)
        return result

    def clock(self, req):
        now = datetime.datetime.now()
        data = packet(0x28)
        data[8:15] = bytes([now.year >> 8, now.year & 255, now.month, now.day, now.hour, now.minute, now.second])
        self.send(data)
        return dict(kind='display', message='Local time sent to the display. This command has no readback.')

    def display_image(self, req):
        slot = integer(req.get('slot'), 0, 4, 'Picture slot')
        path = req.get('path')
        if not isinstance(path, str):
            raise ValueError('Choose an image first')
        data = screen_pixels(path)
        # Announce: exact 160x80 RGB565 geometry from model 4207's record.
        payload = [slot,1,0,len(data)&255,len(data)>>8,0,0,0,0,160,80,0,0,0,0,0,0,slot]
        ready = False
        for _ in range(10):
            reply = self.exchange(0xa5, payload)
            if reply[1] == 1:
                ready = True
                break
            time.sleep(0.1)
        if not ready:
            raise ValueError('Display did not accept the image transfer')
        self.snapshot('display-upload', dict(slot=slot, source=path, sha256=hashlib.sha256(data).hexdigest(),
                                       note='Previous display picture cannot be read back'))
        for page, start in enumerate(range(0,len(data),56)):
            chunk = data[start:start+56]
            report = packet(0x25,[slot,1,0,page&255,page>>8,len(chunk)])
            report[8:8+len(chunk)] = chunk
            self.send(report)
        time.sleep(0.5)
        return dict(kind='display', message=f'Image sent to picture slot {slot+1}. Select it on the keyboard to check; the display has no image readback.')

    def export(self, req):
        profile = self.guard_profile(req)
        host = integer(req.get('host', 0), 0, 3, 'Host layer')
        body = dict(profile=profile, host=host, lighting=self.state(), device=self.device(req),
                    base=self.matrix(profile, host, 'base'), fn=self.matrix(profile, host, 'fn'))
        path = self.snapshot('profile-export', body)
        return dict(kind='export', message='Profile keymaps, lighting and device settings exported', path=path)

    def execute(self, req):
        actions = {'paint': self.paint, 'set-paint': self.set_paint, 'keys': self.keys, 'remap': self.remap, 'switches': self.switches,
                   'set-switches': self.set_switches, 'device': self.device,
                   'set-device': self.set_device, 'clock': self.clock, 'export': self.export,
                   'macro': self.macro, 'macro-text': self.macro_text, 'display-image': self.display_image}
        action = req.get('action')
        if action not in actions:
            raise ValueError('Unsupported native action')
        if not self.caps['advanced'] and action not in ('keys', 'paint', 'set-paint'):
            raise ValueError('Advanced writes are not validated for this model')
        if action in ('paint', 'set-paint') and not self.caps['paint']:
            raise ValueError('Per-key painting is not supported for this model lighting table')
        result = actions[action](req)
        result.update(ok=True, connected=True)
        return result
