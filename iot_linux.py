#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental Linux replacement for IoT Manager 0.1.8's HID API.

Reimplemented from the vendor's protobuf definitions in locally cached qmk.top
JS and service names in the supplied Windows installer. No vendor code runs.
The vendor interface is limited to a verified NJ81 MAX-CP. Optional firmware
mode follows only that keyboard's physical USB port through re-enumeration.
"""
import argparse
import base64
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import struct
import threading
import time
from urllib.parse import urlsplit
from bridge import Keyboard, candidates

ORIGINS = {'https://qmk.top', 'https://www.qmk.top', 'https://iotdriver.qmk.top',
           'https://keydousnj.rongyuan.tech'}
# The firmware path is intentionally absent until exact boot re-enumeration
# and packet timing have been tested on record 4207.
READS = {0x8f, 0x80, 0x83, 0x84, 0x86, 0x87, 0x89, 0x8a, 0x8b, 0x90, 0x91, 0x97, 0xad, 0xe5, 0xe6}
WRITES = {0x03, 0x04, 0x07, 0x09, 0x0a, 0x0b, 0x10, 0x11, 0x17, 0x28, 0x65}


def varint(n):
    data = bytearray()
    while n > 127:
        data.append((n & 127) | 128)
        n >>= 7
    data.append(n)
    return bytes(data)


def field(n, value):
    if isinstance(value, str):
        value = value.encode()
    if isinstance(value, bytes):
        return varint(n*8+2) + varint(len(value)) + value
    return varint(n*8) + varint(value)


def parse(data):
    pos = 0
    def read():
        nonlocal pos
        n = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError('Truncated protobuf')
            b = data[pos]; pos += 1; n |= (b & 127) << shift
            if not b & 128:
                return n
        raise ValueError('Oversized protobuf integer')
    result = {}
    while pos < len(data):
        tag = read(); number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError('Invalid protobuf tag')
        if wire == 0:
            value = read()
        elif wire == 2:
            size = read()
            if size > len(data)-pos:
                raise ValueError('Truncated protobuf field')
            value = data[pos:pos+size]; pos += size
        else:
            raise ValueError('Unsupported protobuf field type')
        result.setdefault(number, []).append(value)
    return result


def one(message, number, default=b''):
    return message.get(number, [default])[0]


def frame(data, trailer=False):
    return bytes([128 if trailer else 0]) + struct.pack('>I', len(data)) + data


def usb_parent(path):
    node = Path('/sys/class/hidraw') / Path(path).name / 'device'
    node = node.resolve()
    for parent in (node, *node.parents):
        if (parent/'idVendor').exists() and (parent/'idProduct').exists():
            return str(parent)
    raise ValueError('Cannot determine the keyboard USB port')


class RawHandle:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(self.fd)
            raise

    def close(self):
        os.close(self.fd)


class Backend:
    def __init__(self, firmware_mode=False):
        self.firmware_mode = firmware_mode
        self.physical_port = None
        self.session = secrets.token_hex(24)
        self.lock = threading.RLock()
        self.handles = {}
        self.database = {}
        self.stop = threading.Event()

    def arm_firmware(self):
        paths = candidates()
        if len(paths) != 1:
            raise ValueError('Connect exactly one NJ81 MAX-CP by USB cable before starting the update bridge')
        keyboard = Keyboard(paths[0])
        try:
            if keyboard.device_id != 4207:
                raise ValueError('Firmware bridge is supported only for device record 4207')
            self.physical_port = usb_parent(paths[0])
        except Exception:
            keyboard.close()
            raise
        self.handles[paths[0]] = keyboard

    def devices(self, filters=()):
        result = []
        paths = candidates()
        if self.firmware_mode and self.physical_port:
            paths = []
            for entry in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
                path = '/dev/'+entry.name
                try:
                    if usb_parent(path) != self.physical_port:
                        continue
                    desc = (entry/'device/report_descriptor').read_bytes()
                    if b'\x06\xff\xff\x09\x02' in desc:
                        paths.append(path)
                except OSError:
                    continue
        for path in paths:
            node = Path('/sys/class/hidraw') / Path(path).name / 'device'
            try:
                info = dict(line.split('=',1) for line in (node/'uevent').read_text().splitlines() if '=' in line)
                _, vid, pid = info['HID_ID'].split(':')
                vid, pid = int(vid,16), int(pid,16)
            except (OSError, ValueError, KeyError):
                continue
            interface = 2
            for parent in (node.resolve(), *node.resolve().parents):
                if (parent/'bInterfaceNumber').exists():
                    interface = int((parent/'bInterfaceNumber').read_text().strip(), 16)
                    break
            record = {1: path, 2: vid, 3: pid, 4: info.get('HID_NAME', 'Keydous'), 6: interface, 7: 0xffff, 8: 2, 10: 0}
            filter_fields = {1:2, 2:3, 3:7, 4:8, 5:6}
            if filters and not any(all(one(f,n,record.get(target)) == record.get(target) for n,target in filter_fields.items()) for f in filters):
                continue
            blob = b''.join(field(n, v) for n, v in record.items())
            blob += field(11, field(1, 0)+field(4, 64))
            result.append((path, blob))
        return result

    def authenticate(self, message, session_field):
        if one(message, session_field) != self.session.encode():
            raise ValueError('Invalid local IoT session')

    def keyboard(self, path):
        if path not in dict(self.devices()):
            raise ValueError('This interface is not on the verified keyboard USB port')
        if path not in self.handles:
            if path in candidates():
                keyboard = Keyboard(path)
                if keyboard.device_id != 4207:
                    keyboard.close()
                    raise ValueError('IoT bridge is supported only for device record 4207')
                self.handles[path] = keyboard
            elif self.firmware_mode and usb_parent(path) == self.physical_port:
                self.handles[path] = RawHandle(path)
            else:
                raise ValueError('Unverified HID interface')
        return self.handles[path]

    def rpc(self, service, method, message):
        if method == 'GetVersion':
            version = '0.1.8' if service == 'iot_manager.IotManager' else '0.1.0'
            return field(1, version)+field(2, 'omarchy-linux')+field(3, version+'-linux-experimental')+field(4, 'linux')
        if service == 'iot_manager.IotManager':
            if method == 'IsRunning':
                return b''
            if method == 'ControlService':
                self.authenticate(message, 4)
                # CommonHID is already running. Other Windows services are not
                # claimed as implemented.
                if one(message, 1, 0) != 4:
                    raise ValueError('Only the HID compatibility service is implemented')
                return field(1, 1)+field(2, 'Linux HID service')+field(3, os.getpid())
            if method in ('ControlDeviceLoopCheckStatus', 'ControlAllDeviceLoopCheckStatus'):
                self.authenticate(message, 4)
                return field(1, 1)
            if method in ('GetAutostart',):
                return b''
            if method == 'AddDeviceFilter':
                self.authenticate(message, 1)
                return field(1, 1)
            if method in ('InsertDb', 'DeleteItemFromDb', 'GetItemFromDb'):
                self.authenticate(message, 4)
                key = (one(message,1),one(message,2))
                if method == 'InsertDb':
                    self.database[key] = one(message,3)
                    return field(1,1)+field(2,'OK')
                if method == 'DeleteItemFromDb':
                    self.database.pop(key,None)
                    return field(1,1)+field(2,'OK')
                return field(1,int(key in self.database))+field(2,self.database.get(key,b''))
            if method in ('GetAllKeysFromDb', 'GetAllValuesFromDb'):
                self.authenticate(message,2)
                dbpath=one(message,1)
                values=[key[1] if method == 'GetAllKeysFromDb' else value for key,value in self.database.items() if key[0]==dbpath]
                return b''.join(field(1,value) for value in values)+field(2,'OK')
            raise ValueError('IoT manager method not implemented: '+method)
        if service != 'hid.HidService':
            raise ValueError('Unsupported service')
        if method in ('LockDevice', 'UnlockDevice'):
            self.authenticate(message, 2)
            path = one(message, 1).decode()
            with self.lock:
                if method == 'LockDevice':
                    self.keyboard(path)
                elif path in self.handles:
                    self.handles.pop(path).close()
            return field(1, 1)+field(2, 'OK')
        if method in ('SendFeatureReport', 'GetFeatureReport'):
            self.authenticate(message, 4)
            path = one(message, 1).decode()
            data = one(message, 2)
            if len(data) != 65 or data[0] != 0:
                raise ValueError('Expected a 65-byte report with ID zero')
            with self.lock:
                keyboard = self.keyboard(path)
                if method == 'SendFeatureReport':
                    if not self.firmware_mode and data[1] not in READS | WRITES:
                        raise ValueError(f'Opcode 0x{data[1]:02x} is not enabled. Firmware/erase/calibration are not ported.')
                    buf = bytearray(data)
                    fcntl.ioctl(keyboard.fd, 0xC0414806, buf, True)
                    if self.firmware_mode and data[1:6] == bytes([0x7f,0x55,0xaa,0x55,0xaa]):
                        self.handles.pop(path).close()
                    return b''
                buf = bytearray(data)
                fcntl.ioctl(keyboard.fd, 0xC0414807, buf, True)
                return field(1, bytes(buf))
        raise ValueError('HID method not implemented: '+method)

    def close(self):
        self.stop.set()
        with self.lock:
            for keyboard in self.handles.values():
                keyboard.close()
            self.handles.clear()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *args):
        pass

    def allowed(self):
        return self.headers.get('Origin') in ORIGINS and self.client_address[0] == '127.0.0.1'

    def headers_for(self, length=None, stream=False):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
        self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Headers', 'content-type,x-grpc-web,x-user-agent,grpc-timeout,x-accept-response-streaming,x-accept-content-transfer-encoding')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Expose-Headers', 'grpc-status,grpc-message')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        if length is not None:
            self.send_header('Content-Length', str(length))
        if stream:
            self.send_header('Transfer-Encoding', 'chunked')
        if self.command == 'POST':
            self.send_header('Content-Type', 'application/grpc-web-text+proto' if self.text_mode else 'application/grpc-web+proto')
        self.end_headers()

    def do_OPTIONS(self):
        if not self.allowed():
            self.send_error(403); return
        self.headers_for(0)

    def encode(self, data):
        return base64.b64encode(data) if self.text_mode else data

    def do_POST(self):
        if not self.allowed():
            self.send_error(403); return
        self.text_mode = 'grpc-web-text' in self.headers.get('Content-Type', '')
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 128*1024:
                raise ValueError('Invalid request length')
            data = self.rfile.read(size)
            if self.text_mode:
                data = base64.b64decode(data, validate=True)
            if len(data) < 5 or data[0] != 0 or struct.unpack('>I', data[1:5])[0] != len(data)-5:
                raise ValueError('Invalid gRPC frame')
            service, method = self.path.strip('/').split('/')
            message = parse(data[5:])
            if method in ('StartClientMonitoring', 'StartDeviceMonitoring', 'ListenManyReports', 'ListenToReports'):
                return self.monitor(service, method, message)
            result = self.server.backend.rpc(service, method, message)
            output = self.encode(frame(result)+frame(b'grpc-status: 0\r\n', True))
        except (OSError, ValueError, UnicodeError) as error:
            reason = str(error).replace('\r', ' ').replace('\n', ' ')[:250]
            print(json.dumps(dict(event='rpc-error', path=self.path, error=reason)), flush=True)
            output = self.encode(frame(('grpc-status: 9\r\ngrpc-message: '+reason+'\r\n').encode(), True))
        self.headers_for(len(output))
        try:
            self.wfile.write(output)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def chunk(self, payload):
        encoded = self.encode(frame(payload))
        self.wfile.write(f'{len(encoded):x}\r\n'.encode()+encoded+b'\r\n')
        self.wfile.flush()

    def monitor(self, service, method, message):
        backend = self.server.backend
        if method.startswith('Listen'):
            backend.authenticate(message,3)
        self.headers_for(stream=True)
        try:
            if method.startswith('Start'):
                self.chunk(field(1, field(1, 1)+field(2, backend.session)))
            previous = {}
            filters = [parse(data) for data in message.get(1, [])] if method == 'StartDeviceMonitoring' else []
            while not backend.stop.wait(1):
                if method == 'StartDeviceMonitoring':
                    now = dict(backend.devices(filters))
                    events = [field(1, field(1, 2)+field(2, blob)) for path, blob in previous.items() if path not in now or now[path] != blob]
                    events += [field(1, field(1, 1)+field(2, blob)) for path, blob in now.items() if path not in previous or previous[path] != blob]
                    if events:
                        with backend.lock:
                            for path,blob in previous.items():
                                if path not in now or now[path] != blob:
                                    handle=backend.handles.pop(path,None)
                                    if handle:
                                        handle.close()
                        self.chunk(field(2, b''.join(events)))
                    previous = now
                elif method == 'StartClientMonitoring':
                    # Valid application-level heartbeat, also detects a closed tab.
                    self.chunk(field(1, field(1, 1)+field(2, backend.session)))
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', action='store_true', help='Forward vendor update packets on the verified keyboard USB port')
    args = parser.parse_args()
    backend = Backend(args.firmware)
    if args.firmware:
        backend.arm_firmware()
    servers = []
    try:
        for port in (3838, 6015):
            server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
            server.daemon_threads = True
            server.backend = backend
            threading.Thread(target=server.serve_forever, daemon=True).start()
            servers.append(server)
        def stop(*_):
            backend.stop.set()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        print(json.dumps(dict(event='ready', ports=[3838, 6015], firmware=args.firmware)), flush=True)
        backend.stop.wait()
    finally:
        backend.close()
        for server in servers:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(json.dumps(dict(event='error', error='Cannot start Linux IoT bridge: '+str(error))), flush=True)
        sys.exit(1)
