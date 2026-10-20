# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import json
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import advanced
from advanced import AdvancedKeyboard, integer
import firmware
import iot_linux as iot


class FakeAdvanced(AdvancedKeyboard):
    def __init__(self):
        self.device_id = 4207
        self.firmware = '0500'
        self.profile = 1
        self.keymap = [[0, 0, 4+i%26, 0] for i in range(128)]
        self.keymap[127] = [10, 1, 0, 0]
        self.columns = {0:400, 1:450, 2:40, 3:60, 6:30, 7:2}
        self.sleep = [120, 120, 1800, 1800]
        self.auto = False
        self.macro_bytes = bytes(256)
        self.macro_staging = bytearray(280)
        self.sent = []

    def get(self, op):
        if op == 0x84:
            return bytes([op, self.profile])+bytes(62)
        raise AssertionError(op)

    def state(self):
        return dict(profile=self.profile, deviceId=4207, firmware=self.firmware)

    def matrix(self, profile, host, layer):
        return [v[:] for v in self.keymap]

    def exchange(self, op, payload=(), raw=False):
        if op == 0x91:
            return bytes([op])+bytes(7)+struct.pack('<4H', *self.sleep)+bytes(48)
        if op == 0x97:
            return bytes([op, int(self.auto)])+bytes(62)
        if op == 0x83:
            return bytes([op, 0, getattr(self,'rate_code',3)])+bytes(61)
        if op == 0x89:
            return bytes([op])+bytes(getattr(self,'options',[0,0,0,0,0]))+bytes(58)
        if op == 0xe6:
            return bytes([op])+bytes(63)
        if op == 0x8b:
            return self.macro_bytes[payload[1]*64:payload[1]*64+64]
        raise AssertionError(op)

    def column(self, subop, slot, wide=True):
        return self.columns[subop]

    def send(self, packet):
        self.sent.append(packet)
        if packet[0] == 3:
            self.rate_code = packet[2]
        elif packet[0] == 9:
            self.options = list(packet[1:6])
        elif packet[0] == 10:
            self.keymap[packet[2]] = list(packet[8:12])
        elif packet[0] == 16:
            self.keymap[packet[3]] = list(packet[8:12])
        elif packet[0] == 101:
            self.columns[packet[1]] = int.from_bytes(packet[8:10], 'little')
        elif packet[0] == 17:
            self.sleep = list(struct.unpack('<4H', packet[8:16]))
        elif packet[0] == 23:
            self.auto = bool(packet[1])
        elif packet[0] == 11:
            start = packet[2]*56
            self.macro_staging[start:start+56] = packet[8:64]
            if packet[4]:
                self.macro_bytes = bytes(self.macro_staging[:256])


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.kb = FakeAdvanced()
        self.snapshot = patch('advanced.snapshot', return_value='/tmp/backup.json').start()
        self.delay = patch('advanced.time.sleep').start()

    def tearDown(self):
        patch.stopall()

    def test_remap_preserves_unrelated_keys(self):
        previous = [k[:] for k in self.kb.keymap]
        result = self.kb.remap(dict(profile=1, slot=3, expected=previous[3], value=[0,0,40,0]))
        self.assertEqual(self.kb.keymap[3], [0,0,40,0])
        self.assertEqual(self.kb.keymap[:3]+self.kb.keymap[4:], previous[:3]+previous[4:])
        packet = self.kb.sent[0]
        self.assertEqual(list(packet[:7]), [10,1,3,0,0,1,0])
        self.snapshot.assert_called_once()
        self.assertEqual(result['kind'], 'keys')

    def test_fn_layout_write_shape(self):
        before = self.kb.keymap[4][:]
        self.kb.remap(dict(profile=1, host=1, layer='fn', slot=4, expected=before, value=[0,0,42,0]))
        self.assertEqual(list(self.kb.sent[0][:4]), [16,1,1,4])

    def test_fn_key_is_protected(self):
        with self.assertRaisesRegex(ValueError, 'Fn key'):
            self.kb.remap(dict(profile=1, slot=127, expected=self.kb.keymap[127], value=[0,0,4,0]))
        self.assertFalse(self.kb.sent)

    def test_stale_key_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed since'):
            self.kb.remap(dict(profile=1, slot=3, expected=[0,0,0,0], value=[0,0,4,0]))
        self.assertFalse(self.kb.sent)

    def test_profile_race_rejected(self):
        with self.assertRaisesRegex(ValueError, 'profile changed'):
            self.kb.keys(dict(profile=0))
        self.assertFalse(self.kb.sent)

    def test_rt_keeps_dks_mode_and_correct_scale(self):
        before = self.kb.switches(dict(profile=1, slot=2))
        self.assertEqual(before['scale'], 100)
        self.kb.set_switches(dict(profile=1, slot=2, expected=before['raw'], values={'actuation':1.25, 'keyMode':True}))
        self.assertEqual(self.kb.columns[0], 125)
        self.assertEqual(self.kb.columns[7], 130)
        for p in self.kb.sent:
            self.assertEqual(p[0], 101)
            self.assertEqual(p[4], 1)
            self.assertEqual(sum(p[:8]) & 255, 255)

    def test_invalid_switch_value_does_not_write(self):
        before = self.kb.switches(dict(profile=1, slot=2))
        for value in (float('nan'), 10, -1, True):
            with self.assertRaises(ValueError):
                self.kb.set_switches(dict(profile=1, slot=2, expected=before['raw'], values={'actuation':value}))
        self.assertFalse(self.kb.sent)

    def test_stale_switch_response_does_not_write(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.kb.set_switches(dict(profile=1, slot=2, expected={}, values={'actuation':1}))
        self.assertFalse(self.kb.sent)

    def test_sleep_offset_and_readback(self):
        self.kb.set_device(dict(profile=1, setting='sleep', expected=self.kb.sleep[:], value=[300,600,1800,3600]))
        self.assertEqual(self.kb.sleep, [300,600,1800,3600])
        self.assertEqual(self.kb.sent[0][8:16], struct.pack('<4H',300,600,1800,3600))
        self.assertEqual(self.kb.sent[0][0], 17)

    def test_clock_fields_after_checksum(self):
        self.kb.clock({})
        packet=self.kb.sent[0]
        self.assertEqual(packet[0], 40)
        self.assertEqual(sum(packet[:8]) & 255, 255)
        self.assertGreater(int.from_bytes(packet[8:10], 'big'), 2025)

    def test_text_macro_shift_and_commit(self):
        before = self.kb.macro(dict(macro=2))
        self.kb.macro_text(dict(macro=2, expected=before['digest'], text='A!'))
        self.assertEqual(self.kb.macro_bytes[:6], bytes([1,0,225,138,4,138]))
        self.assertEqual(len(self.kb.sent), 5)
        self.assertEqual(self.kb.sent[-1][4], 1)
        self.assertTrue(all(p[4]==0 for p in self.kb.sent[:-1]))

    def test_unsupported_macro_text_does_not_write(self):
        before = self.kb.macro(dict(macro=2))
        with self.assertRaisesRegex(ValueError, 'ASCII'):
            self.kb.macro_text(dict(macro=2, expected=before['digest'], text='日本語'))
        self.assertFalse(self.kb.sent)

    def test_firmware_version_is_compared_as_hex(self):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*_): pass
        body=dict(code=0,data=dict(version_str='usb_510_oledv_111',file_path='firmware/4207.zip'))
        with patch('firmware.urllib.request.urlopen', return_value=Response(json.dumps(body).encode())) as call:
            result=firmware.check(4207,'0500')
        self.assertTrue(result['available'])
        self.assertEqual(result['downloadPath'], 'firmware/4207.zip')
        req=call.call_args.args[0]
        self.assertEqual(json.loads(req.data), {'dev_id':4207})

    def test_firmware_server_error_is_not_up_to_date(self):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*_): pass
        with patch('firmware.urllib.request.urlopen', return_value=Response(b'{"code":500}')), patch('firmware.record_failure'):
            with self.assertRaisesRegex(ValueError, 'unknown'):
                firmware.check(4207,'0500')

    def test_http500_preserves_server_diagnostic_and_unknown_status(self):
        from urllib.error import HTTPError
        error=HTTPError(firmware.API,500,'Internal Server Error',{},io.BytesIO(b'{"detail":"firmware record missing"}'))
        with tempfile.TemporaryDirectory() as folder, patch('firmware.Path.home',return_value=Path(folder)), \
             patch('firmware.urllib.request.urlopen',side_effect=error):
            with self.assertRaisesRegex(ValueError,'Update status is unknown') as caught:
                firmware.check(4207,'0400')
            self.assertIn('HTTP 500',str(caught.exception))
            diagnostic=json.loads((Path(folder)/'.local/state/omarchy-keydous/firmware/last-check-error.json').read_text())
            self.assertEqual(diagnostic['request'],{'dev_id':4207})
            self.assertEqual(diagnostic['response']['detail'],'firmware record missing')
            self.assertEqual(diagnostic['httpStatus'],500)
            self.assertEqual(diagnostic['updateStatus'],'unknown')

    def test_network_failure_is_distinct_from_server_error(self):
        from urllib.error import URLError
        with patch('firmware.urllib.request.urlopen',side_effect=URLError('DNS failed')):
            with self.assertRaisesRegex(ValueError,'Could not reach'):
                firmware.check(4207,'0400')

    def test_non_json_response_is_not_treated_as_up_to_date(self):
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*_):pass
        with tempfile.TemporaryDirectory() as folder,patch('firmware.Path.home',return_value=Path(folder)), \
             patch('firmware.urllib.request.urlopen',return_value=Response(b'<html>upstream failed</html>')):
            with self.assertRaisesRegex(ValueError,'invalid response'):
                firmware.check(4207,'0400')

    def test_package_path_cannot_escape_vendor(self):
        for path in ('https://evil.example/x', '//evil.example/x', '../x', '/x/../a', 'a?x=1'):
            with self.assertRaises(ValueError):
                firmware.package_url(path)
        self.assertEqual(firmware.package_url('/firmwares/4207.zip'), firmware.DOWNLOAD+'firmwares/4207.zip')

    def test_polling_rate_uses_byte_two(self):
        self.kb.set_device(dict(profile=1,setting='reportRate',expected=1000,value=8000))
        self.assertEqual(list(self.kb.sent[0][:3]),[3,0,0])
        self.assertEqual(self.kb.device({})['reportRate'],8000)

    def test_options_preserve_host_and_fn(self):
        self.kb.options=[1,3,0,2,0]
        self.kb.set_device(dict(profile=1,setting='keyboardOptions',expected=[1,3,0,2,0],
                               value=dict(wasdSwap=True,antiAccidental=True,stabilization=4)))
        self.assertEqual(self.kb.options,[1,3,1,4,1])

    def test_feature_precision_overrides_record_default(self):
        original=self.kb.exchange
        def exchange(op,*args,**kwargs):
            if op==0xe6:
                return bytes([op,0xaa,2])+bytes(61)
            return original(op,*args,**kwargs)
        with patch.object(self.kb,'exchange',side_effect=exchange):
            self.assertEqual(self.kb.switches(dict(profile=1,slot=0))['scale'],1000)

    def test_zero_setting_can_equal_request_echo(self):
        kb=object.__new__(AdvancedKeyboard)
        kb.fd=9
        def ioctl(fd,op,buf,mutable):
            buf[:]=b'\0'+bytes(advanced.packet(0x97))
        with patch.object(kb,'send'),patch('fcntl.ioctl',side_effect=ioctl):
            self.assertEqual(kb.exchange(0x97)[1],0)

    def test_rgb565_column_order(self):
        pixels=bytearray(160*80*3)
        pixels[:3]=bytes([255,0,0])
        pixels[160*3:160*3+3]=bytes([0,255,0])
        pixels[3:6]=bytes([0,0,255])
        wire=advanced.rgb565_columns(pixels)
        self.assertEqual(wire[:4],bytes.fromhex('f80007e0'))
        self.assertEqual(wire[160:162],bytes.fromhex('001f'))
        self.assertEqual(len(wire),25600)

    def test_display_transfer_has_checked_geometry_and_bounded_pages(self):
        original=self.kb.exchange
        def exchange(op,payload=(),raw=False):
            if op==0xa5:
                self.assertEqual(payload[7:11],[0,0,160,80])
                return bytes([0xa5,1])+bytes(62)
            return original(op,payload,raw)
        with patch('advanced.screen_pixels',return_value=bytes(25600)),patch.object(self.kb,'exchange',side_effect=exchange):
            result=self.kb.display_image(dict(slot=2,path='/tmp/test.png'))
        self.assertEqual(len(self.kb.sent),458)
        self.assertEqual(list(self.kb.sent[0][:7]),[37,2,1,0,0,0,56])
        self.assertEqual(self.kb.sent[-1][6],8)
        self.assertTrue(all(sum(p[:8]) & 255==255 for p in self.kb.sent))
        self.assertEqual(result['kind'],'display')

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick 7 is optional")
    def test_image_conversion_on_linux(self):
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/'red.ppm'
            image.write_bytes(b'P6\n160 80\n255\n'+bytes([255,0,0])*12800)
            data=advanced.screen_pixels(str(image))
            self.assertEqual(data,bytes.fromhex('f800')*12800)


class IoTTests(unittest.TestCase):
    def test_proto_round_trip(self):
        data=iot.field(1,'/dev/hidraw2')+iot.field(2,bytes(65))+iot.field(3,True)+iot.field(4,'token')
        parsed=iot.parse(data)
        self.assertEqual(iot.one(parsed,1),b'/dev/hidraw2')
        self.assertEqual(iot.one(parsed,2),bytes(65))
        self.assertEqual(iot.one(parsed,3),1)

    def test_proto_truncation_rejected(self):
        for data in (b'\x0a\xff', b'\x0a\x04xx', b'\x00'):
            with self.assertRaises(ValueError):
                iot.parse(data)

    def test_rpc_frame_length(self):
        frame=iot.frame(b'abc')
        self.assertEqual(frame,b'\x00\x00\x00\x00\x03abc')
        self.assertEqual(iot.frame(b'grpc-status: 0\r\n',True)[0],128)

    def test_session_required(self):
        backend=iot.Backend()
        with self.assertRaisesRegex(ValueError,'session'):
            backend.rpc('hid.HidService','SendFeatureReport',{})

    def test_firmware_disabled_in_settings_mode(self):
        backend=iot.Backend()
        fake=type('KB',(),dict(fd=3))()
        req={1:[b'/dev/fake'],2:[bytes([0,127])+bytes(63)],4:[backend.session.encode()]}
        with patch.object(backend,'keyboard',return_value=fake),patch('iot_linux.fcntl.ioctl') as ioctl:
            with self.assertRaisesRegex(ValueError, 'not enabled'):
                backend.rpc('hid.HidService','SendFeatureReport',req)
        ioctl.assert_not_called()

    def test_hid_report_passes_without_changing_bytes(self):
        backend=iot.Backend()
        data=bytes([0,135])+bytes(63)
        req={1:[b'/dev/fake'],2:[data],4:[backend.session.encode()]}
        with patch.object(backend,'keyboard',return_value=type('KB',(),dict(fd=3))()),patch('iot_linux.fcntl.ioctl') as ioctl:
            backend.rpc('hid.HidService','SendFeatureReport',req)
        self.assertEqual(bytes(ioctl.call_args.args[2]),data)
        self.assertEqual(ioctl.call_args.args[1],0xC0414806)

    def test_firmware_mode_must_verify_initial_identity(self):
        backend=iot.Backend(True)
        with patch('iot_linux.candidates',return_value=['/dev/fake']),patch('iot_linux.Keyboard',side_effect=ValueError('wrong model')):
            with self.assertRaisesRegex(ValueError,'wrong model'):
                backend.arm_firmware()
        self.assertIsNone(backend.physical_port)

    def test_firmware_mode_does_not_enumerate_other_usb_ports(self):
        backend=iot.Backend(True)
        backend.physical_port='/sys/devices/usb1/1-2'
        with patch('iot_linux.candidates',return_value=[]),patch('iot_linux.Path.glob',return_value=[Path('/sys/class/hidraw/hidraw9')]),patch('iot_linux.usb_parent',return_value='/sys/devices/usb1/1-3'):
            self.assertEqual(backend.devices(),[])

    def test_process_kill_rpc_is_not_implemented(self):
        with self.assertRaisesRegex(ValueError,'not implemented'):
            iot.Backend().rpc('hid.HidService','KillProcessOnPort',{})

    def test_cors_rejects_unrelated_sites_and_remote_clients(self):
        handler=object.__new__(iot.Handler)
        handler.headers={'Origin':'https://qmk.top'}
        handler.client_address=('127.0.0.1',1000)
        self.assertTrue(handler.allowed())
        handler.headers={'Origin':'https://evil.example'}
        self.assertFalse(handler.allowed())
        handler.headers={'Origin':'https://qmk.top'}
        handler.client_address=('192.168.1.2',1000)
        self.assertFalse(handler.allowed())

    def test_full_unary_grpc_web_handler(self):
        handler=object.__new__(iot.Handler)
        handler.headers={'Origin':'https://qmk.top','Content-Type':'application/grpc-web+proto','Content-Length':'5'}
        handler.client_address=('127.0.0.1',1000)
        handler.path='/iot_manager.IotManager/GetVersion'
        handler.rfile=io.BytesIO(iot.frame(b''))
        handler.wfile=io.BytesIO()
        handler.server=type('Server',(),dict(backend=iot.Backend()))()
        with patch.object(handler,'headers_for') as headers:
            handler.do_POST()
        output=handler.wfile.getvalue()
        size=struct.unpack('>I',output[1:5])[0]
        decoded=iot.parse(output[5:5+size])
        self.assertEqual(iot.one(decoded,1),b'0.1.8')
        self.assertIn(b'grpc-status: 0',output)
        headers.assert_called_once_with(len(output))

    def test_rpc_error_is_a_grpc_trailer(self):
        request=iot.field(1,b'/dev/fake')+iot.field(2,bytes(65))+iot.field(4,'bad-session')
        framed=iot.frame(request)
        handler=object.__new__(iot.Handler)
        handler.headers={'Origin':'https://qmk.top','Content-Type':'application/grpc-web+proto','Content-Length':str(len(framed))}
        handler.client_address=('127.0.0.1',1000)
        handler.path='/hid.HidService/SendFeatureReport'
        handler.rfile=io.BytesIO(framed)
        handler.wfile=io.BytesIO()
        handler.server=type('Server',(),dict(backend=iot.Backend()))()
        with patch.object(handler,'headers_for'),patch('builtins.print'):
            handler.do_POST()
        output=handler.wfile.getvalue()
        self.assertEqual(output[0],128)
        self.assertIn(b'Invalid local IoT session',output)

    def test_transient_vendor_database_round_trip(self):
        backend=iot.Backend()
        session=backend.session.encode()
        backend.rpc('iot_manager.IotManager','InsertDb',{1:[b'db'],2:[b'key'],3:[b'value'],4:[session]})
        result=iot.parse(backend.rpc('iot_manager.IotManager','GetItemFromDb',{1:[b'db'],2:[b'key'],4:[session]}))
        self.assertEqual(iot.one(result,2),b'value')


if __name__ == '__main__':
    unittest.main()
