# Keydous Keyboard for Omarchy

Native Omarchy bar lighting and painting for compatible **Keydous keyboards**,
including NJ98-CP variants. NJ81 MAX-CP TMR also has advanced keymap, magnetic
switch, device and display controls. See the [model compatibility table](docs/compatibility.md).

**Early release.** The owner has reported working lighting controls and a
working tabbed popup. Advanced writes and the experimental vendor firmware
bridge still need broader hardware validation. Firmware updates have not been
verified end to end. This project is independent of Keydous and RongYuan.

## Features

- RGB effects, colour, brightness, speed and four onboard profiles.
- Per-key colour painting with drag strokes, erasing, swatches and a local preview.
- Model-aware USB detection, profile counts and isolated local paintings.
- NJ81 MAX keyboard-shaped painting and hardware slot views, with remembered
  live key mappings and the corrected Del navigation key.
- Live Windows/Mac base and Fn keymaps, normal/media remaps and ASCII text macros.
- Graphical per-key selection for remapping and travel, with millimetre sliders
  for actuation, release, rapid trigger sensitivities and bottom dead zone.
- Polling rate, WASD/arrow swap, accidental-trigger prevention, stabilization,
  OS auto-detection and sleep timers.
- Display clock and still-picture uploads to five 160×80 slots.
- Local snapshots before advanced writes, with readback where supported.
- Vendor firmware catalogue checks and package downloads; an optional,
  experimental Linux replacement for the IoT Manager HID transport.

The keyboard uses the proprietary ROYUAN gen2 protocol. It is not QMK/VIA
firmware, despite the vendor's qmk.top website name. Exact device records select protocol families, profile counts and enabled
features. This is not universal support for every Keydous model: unknown
protocols and unsupported lighting tables have writes disabled. Shared USB
IDs alone do not establish compatibility.

## Requirements

- Linux and Omarchy's Quickshell shell with the `qs.Ui` plugin components.
- Python **3.11 or newer**. No pip dependencies or root daemon.
- A USB cable for configuration.
- Optional: **ImageMagick 7** (`magick`) for display pictures.
- Optional: **Chromium** for the official vendor updater through the IoT bridge.
  Everyday settings stay inside the native popup.

## Install

From a cloned or extracted copy of this repository:

```bash
python3 scripts/install.py --enable
```

The installer copies the plugin to
`${XDG_CONFIG_HOME:-~/.config}/omarchy/plugins/eg.keydous`, adds it to the bar
if absent, and backs up existing plugin/configuration files under
`${XDG_STATE_HOME:-~/.local/state}/omarchy-keydous/install-backups/`.
Use `python3 scripts/install.py` without `--enable` to leave bar placement alone.
Updates are staged outside the watched plugin directory and published atomically.
The installer never launches or restarts a shell instance.

If the previous widget remains visible, restart the shell:

```bash
omarchy restart shell
```

The keyboard icon opens **Lighting**, **Keys**, **Travel**, **Device**,
**Firmware** and **Paint** tabs. See [usage](docs/usage.md).

### Device permissions

If you receive permission errors, install the supplied application-mode rules
(the filename is retained for compatibility; it now covers the bundled models):

```bash
sudo install -m 644 udev/70-keydous-nj81-max.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

Reconnect the keyboard afterward. This rule does not cover an unknown boot
VID/PID. The installer itself never changes system files.

## Firmware status

**A catalogue error does not mean the firmware is current.** The vendor may
return HTTP 500 for this model. The widget reports update status as unknown
and records the response at
`~/.local/state/omarchy-keydous/firmware/last-check-error.json`.

Package downloads do not flash the keyboard. The optional update bridge
forwards the official updater's HID traffic through Linux; firmware selection,
update timing and recovery remain with the vendor updater. Read
[firmware support and limitations](docs/firmware.md) before using it.

## Development

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/package.py --check
# On an Omarchy machine, also check QML with isolated mock helpers:
python3 -B scripts/check_qml.py --cycles 60
python3 -B scripts/package.py
```

The last command creates an allowlisted source archive in `dist/`. The image
conversion test is skipped if ImageMagick 7 is absent. Protocol tests use
simulated devices; passing tests does not validate physical firmware updates.
See [contributing](CONTRIBUTING.md).

## Uninstall

Remove the `eg.keydous` entry from your Omarchy bar settings, stop any running
compatibility bridge, then remove its folder from `~/.config/omarchy/plugins/`.
Local snapshots remain under `~/.local/state/omarchy-keydous/`.

## References and license

Protocol research:
[sharkfin](https://github.com/dniminenn/sharkfin/blob/master/docs/PROTOCOL.md),
[device registry](https://github.com/dniminenn/sharkfin/blob/master/app/src-tauri/data/devices.json),
and [MonsGeek/Akko Linux driver](https://github.com/echtzeit-solutions/monsgeek-akko-linux).
The current IoT API was independently reimplemented from vendor API definitions
and static inspection; no proprietary installer, binaries or cached vendor
JavaScript are included here.

[GPL-3.0-or-later](LICENSE).
