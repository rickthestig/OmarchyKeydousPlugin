# Firmware and IoT compatibility

**Experimental and unverified end to end. No successful firmware update on
this keyboard is claimed by this release.**

## Catalogue checks

The helper sends the same device-ID request used by the vendor app:

- POST `https://api2.rongyuan.tech:3816/api/v2/get_fw_version`
- JSON: `{"dev_id": 4207}`

HTTP errors, invalid responses and network failures leave update status
**unknown**. A server-side HTTP 500 may indicate a backend failure or an absent
catalogue record; it is not proof that the keyboard is up to date.

A failed response is recorded in
`~/.local/state/omarchy-keydous/firmware/last-check-error.json` with the endpoint,
device ID, HTTP status and a bounded response body. Review it before attaching
it to a public issue. Package downloads and SHA-256 metadata are saved in the
same folder. Downloading does not flash anything.

## Linux IoT bridge

The vendor's current IoT Manager uses separate services. This project
reimplements its manager/HID subset using Python's standard library:

| Endpoint | Purpose |
| --- | --- |
| `127.0.0.1:3838` | `hid.HidService`, feature reports and discovery |
| `127.0.0.1:6015` | `iot_manager.IotManager`, session and manager subset |

The bridge checks vendor web origins and session tokens. It does not execute
the vendor's Windows programs. The settings-only mode allows a restricted
opcode list. Update mode first verifies device record 4207 and records its
physical USB port, then forwards vendor traffic through app/boot
re-enumeration on that port. It does not expose unrelated USB ports or guess a
boot PID. Boot mode may require an additional udev permission rule based on
the actual device identity observed on that keyboard.

### Optional vendor updater flow

1. Connect by USB cable and close other configurators.
2. Open the widget's Firmware tab.
3. Start **vendor firmware update bridge** and wait for it to report ready.
4. Open the official updater using the explicit **Chromium** button.
5. Enable the vendor site's IoT mode. The site chooses and sends its firmware.
6. Keep the cable connected until the vendor reports completion.
7. Stop the compatibility service, then refresh native controls.

The vendor updater owns package selection, integrity checks, timing and
recovery. Native firmware flashing and independent firmware backup are not
implemented. Do not infer firmware compatibility from a shared USB ID.

The bridge is started manually and does not install autostart/root services.
Native controls pause while it owns the keyboard. Its small vendor settings
database exists only for that process's lifetime.

## Unimplemented services and editors

Audio and screen capture, live key-travel input streams, complex macro
recording, DKS/mod-tap/snap editors, animated display uploads, switch calibration,
and backup restoration are not implemented. Manager process-killing and
Windows autostart methods are also unsupported.

## Evidence and validation

The API shape was recovered from static inspection of IoT Manager 0.1.8 and
corresponding vendor scripts. Proprietary artifacts are not distributed.
Protocol tests exercise simulated HID responses, API framing, session checks
and USB-port isolation. Actual browser interoperability, firmware package
availability, boot permissions and physical updates need hardware validation.
