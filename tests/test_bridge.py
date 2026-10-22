# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from unittest.mock import patch
import bridge


class FakeKeyboard(bridge.Keyboard):
    def __init__(self, identity=4207):
        self.device_id = identity
        self.firmware = '0500'
        self.light = bytes([0x87, 1, 2, 4, 0x18, 255, 0, 0]) + bytes(56)
        self.profile = 0
        self.sent = []

    def get(self, op):
        if op == 0x87:
            return self.light
        if op == 0x84:
            return bytes([op, self.profile]) + bytes(62)
        raise AssertionError(op)

    def send(self, data):
        self.sent.append(data)
        if data[0] == 7:
            self.light = bytes([0x87]) + bytes(data[1:])
        elif data[0] == 4:
            self.profile = data[1]
        else:
            raise AssertionError('Unexpected write opcode')

    def backup(self, state):
        self.backed_up = state


class ProtocolTests(unittest.TestCase):
    def test_checksums(self):
        for bit8 in (False, True):
            packet = bridge.packet(7, [4, 2, 3, 7, 120, 80, 200], bit8)
            offset = 8 if bit8 else 7
            self.assertEqual(len(packet), 64)
            self.assertEqual(sum(packet[:offset+1]) & 255, 255)

    def test_color_preserves_options_and_inverts_speed(self):
        keyboard = FakeKeyboard()
        args = type('Args', (), dict(action='light', mode=None, speed=4, brightness=2,
                                    color='#112233', rainbow=False))()
        result = keyboard.apply(args)
        self.assertEqual(keyboard.sent[0][1:8], bytes([1, 0, 2, 0x17, 17, 34, 51]))
        self.assertEqual(result['speed'], 4)
        self.assertEqual(keyboard.backed_up['brightness'], 4)

    def test_profile_opcode(self):
        keyboard = FakeKeyboard()
        with patch('bridge.time.sleep'):
            result = keyboard.apply(type('Args', (), dict(action='profile', profile=3))())
        self.assertEqual(keyboard.sent[0][0:2], bytes([4, 3]))
        self.assertEqual(result['profile'], 3)

    def test_unknown_identity_is_detection_only(self):
        with patch('bridge.os.open', return_value=5), patch('bridge.fcntl.flock'), \
             patch.object(bridge.Keyboard, 'get', return_value=bytes([0x8f, 1]) + bytes(62)), \
             patch('bridge.os.close') as close:
            keyboard = bridge.Keyboard('/dev/fake')
            self.assertFalse(keyboard.caps['paint'])
            self.assertFalse(keyboard.caps['lighting'])
            self.assertIn('Writes are disabled', keyboard.state()['compatibility'])
            with self.assertRaisesRegex(ValueError, 'not supported'):
                keyboard.apply(type('Args', (), dict(action='light'))())
            keyboard.close()
            close.assert_called_once_with(5)

    def test_model_profile_counts_and_names(self):
        for identity in (2454, 2515, 2576, 3459, 3466, 3496, 3793, 4142, 4207):
            keyboard = FakeKeyboard(identity)
            state = keyboard.state()
            self.assertTrue(state['capabilities']['paint'])
            self.assertEqual(state['profileCount'], keyboard.model['profiles'])
            self.assertEqual(state['modelName'], keyboard.model['displayName'])
            with self.assertRaisesRegex(ValueError, 'out of range'):
                keyboard.apply(type('Args', (), dict(action='profile', profile=state['profileCount']))())
            self.assertFalse(keyboard.sent)

    def test_usb_discovery_includes_keydous_pairs_but_excludes_typing_collections(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for i, (usb, desc) in enumerate([
                    ('0003:00003151:00005030', b'\x06\xff\xff\x09\x02'),
                    ('0003:000039AB:00009016', b'\x05\x01\x09\x06'),
                    ('0003:00001234:00005678', b'\x06\xff\xff\x09\x02')]):
                node = root / f'hidraw{i}' / 'device'
                node.mkdir(parents=True)
                (node / 'uevent').write_text('HID_ID=' + usb)
                (node / 'report_descriptor').write_bytes(desc)
            with patch('bridge.Path', return_value=root):
                self.assertEqual(bridge.candidates(), ['/dev/hidraw0'])

    def test_legacy_profile_opcode_and_count(self):
        keyboard = FakeKeyboard(1259)
        with patch.object(keyboard, 'get', return_value=bytes([0x85,0])+bytes(62)), \
             patch.object(keyboard, 'send') as send, patch('bridge.time.sleep'):
            result = keyboard.apply(type('Args', (), dict(action='profile', profile=0))())
            self.assertEqual(result['profileCount'], 1)
            self.assertEqual(send.call_args.args[0][:2], bytes([5, 0]))

    def test_stale_reply_rejected(self):
        keyboard = object.__new__(bridge.Keyboard)
        keyboard.fd = 5
        with patch.object(keyboard, 'send'), patch('bridge.fcntl.ioctl'), patch('bridge.time.sleep'):
            with self.assertRaisesRegex(ValueError, 'valid reply'):
                keyboard.get(0x8f)

    def test_invalid_inputs(self):
        for value in ('0;reboot', '#12345', 'gggggg'):
            with self.assertRaises(Exception):
                bridge.rgb(value)
        with self.assertRaises(Exception):
            bridge.bounded(0, 3)('4')


if __name__ == '__main__':
    unittest.main()
