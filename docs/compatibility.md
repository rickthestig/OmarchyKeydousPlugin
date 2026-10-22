# Model compatibility

Compatibility is determined by the exact device record returned over USB. Model
names and shared USB IDs are not sufficient. This release expands software
protocol coverage; it has not been physically validated on every listed board.

| Record | Model | Protocol | Painting | Profiles |
|---|---|---|---|---|
| 655 | NJ80 AP500 | unknown | Unavailable | 1 |
| 699 | NJ80 AP600 | unknown | Unavailable | 1 |
| 732 | NJ81 | unknown | Unavailable | 1 |
| 1021 | NJ98 | unknown | Unavailable | 1 |
| 1259 | NJ98-CP (legacy) | yc500 | Enabled (experimental) | 1 |
| 1321 | NJ80 AP500 | unknown | Unavailable | 1 |
| 1475 | NJ81-CP (legacy) | unknown | Unavailable | 8 |
| 1493 | NJ81 | unknown | Unavailable | 1 |
| 1563 | NJ80-CP (legacy) | unknown | Unavailable | 8 |
| 2454 | NJ81-CP | gen2 | Enabled (experimental) | 3 |
| 2515 | NJ68 PRO-CP | gen2 | Enabled (experimental) | 3 |
| 2576 | NJ98-CP | gen2 | Enabled (experimental) | 3 |
| 3459 | NJ81-CP V3 | gen2 | Enabled (experimental) | 3 |
| 3466 | NJ80-CP V3 | gen2 | Enabled (experimental) | 3 |
| 3496 | NJ98-CP V4 | gen2 | Enabled (experimental) | 3 |
| 3521 | NJ80-AP800 | gen2 | Unavailable | 3 |
| 3793 | NJ98-CP V4S | gen2 | Enabled (experimental) | 3 |
| 4140 | NJ81-MAX | gen2 | Unavailable | 2 |
| 4142 | AJ100 | gen2 | Enabled (experimental) | 4 |
| 4169 | NJ68-AP700 | gen2 | Unavailable | 3 |
| 4207 | NJ81 MAX-CP TMR | gen2 | Enabled (experimental) | 4 |
| 4273 | NJ98EP-UK | gen2 | Unavailable | 4 |
| 4274 | NJ98EP-IT | gen2 | Unavailable | 4 |
| 4275 | NJ98EP-DE | gen2 | Unavailable | 4 |
| 4276 | NJ98EP-FR | gen2 | Unavailable | 4 |
| 4277 | NJ98EP-ES | gen2 | Unavailable | 4 |

Lighting effects and painting are enabled for the registered gen2 `v` lighting
table. Legacy NJ98-CP record 1259 supports painting with the yc500 header, 128
colour slots and the legacy profile opcode; its effects table is unavailable.
Gen2 patterns contain 126 colour slots. Unsupported lighting tables (including
`He`) and unknown families remain disabled. Known gen2/yc500 families can read
keymaps and select only the registered number of onboard profiles.

The NJ81 MAX geometry is included. Other models use hardware slot view until
their exact physical geometry is available; a key count is not a physical map.
Numpad keys are labeled by their live assignments. Saved paintings are isolated
by device record and profile; two units of the same model share the local copy.

Switches, remapping, macros, device writes, display uploads, firmware catalogue
operations and both IoT bridge modes remain restricted to record 4207. Merely
sharing a protocol does not validate those model-specific settings.

## Refreshing the model catalogue

To import all Keydous records from the upstream registry, run:

```bash
python3 scripts/sync_models.py
python3 scripts/install.py
```

For offline preparation use `python3 scripts/sync_models.py --from-file devices.json`
with the upstream registry file. Refreshing metadata does not enable unknown
protocols or lighting tables. Newly listed USB IDs also require updated udev
permissions; follow the device permission instructions in README.md.

Unregistered identities found on a registered USB interface are detection-only.
Entirely new USB IDs require a catalogue refresh. Bluetooth configuration and
receiver relay transport are not implemented; use a USB cable.

Evidence: [device registry](https://github.com/dniminenn/sharkfin/blob/master/app/src-tauri/data/devices.json),
[protocol](https://github.com/dniminenn/sharkfin/blob/master/docs/PROTOCOL.md).
