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

    def test_unknown_identity_closes_handle(self):
        with patch('bridge.os.open', return_value=5), patch('bridge.fcntl.flock'), \
             patch.object(bridge.Keyboard, 'get', return_value=bytes([0x8f, 1]) + bytes(62)), \
             patch('bridge.os.close') as close:
            with self.assertRaisesRegex(ValueError, 'expected NJ81'):
                bridge.Keyboard('/dev/fake')
            close.assert_called_once_with(5)

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
