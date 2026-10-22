# Using the widget

Click the keyboard icon in the Omarchy bar. Close other keyboard configurators
before reading or changing settings. **Refresh** reads the current profile and
lighting. Nothing writes to the keyboard just because you open the popup.

## Lighting

Choose an effect, colour, brightness and speed, then apply. **Theme accent**
copies the current accent into the colour field; it does not enable automatic
theme synchronization. Brightness zero turns the lights off. Profile buttons
select the keyboard's four onboard profiles.

## Keys and macros

Select Windows/Mac and base/Fn, then **Load keys**. The list shows live hardware
slots and their current assignments; it is not a physical keyboard drawing.
Choose a slot and a new assignment, then save. The Fn key is protected.

Load a macro slot before replacing its contents. Text macros support US-layout
ASCII, up to 40 characters subject to the keyboard's 256-byte event limit.
Shifted characters consume more events. Macro slots are shared across profiles.
**Assign macro to selected key** binds the currently selected macro slot.

## Switches

Load the keymap, select a key and click **Read selected switch**. Set distances
in millimetres and explicitly save that key. Precision follows the board's
reported feature list, or this exact model's legacy 0.01 mm record. Other
key-mode bits are preserved. DKS, mod-tap, snap and switch calibration do not
have native editors in this release.

## Device and display

Read device settings before editing polling rate, host detection, keyboard
options or sleep timers. Timer units are seconds. Values unavailable in the
firmware remain unavailable in the UI.

The clock button sends local time. Picture uploads crop an image to 160×80 and
replace the selected onboard picture slot. Animated inputs use their first
frame. The display has no picture readback; check the result on the keyboard.

## Backups

Snapshots before advanced changes are stored at:

```
~/.local/state/omarchy-keydous/backups/
```

The lighting helper also writes `before-last-change.json` in the parent folder.
The profile export includes the selected host layer's base/Fn keymaps, lighting
and device settings. It is not a full firmware/display/magnetic-settings
backup. There is no automatic restore feature yet.

## Troubleshooting

- Old popup still visible: run `omarchy restart shell` from your terminal.
- Permission denied: install the documented udev rule and reconnect.
- Changed profile/key/switch since loading: reload before applying; stale writes
  are intentionally refused.
- Native controls disabled: stop the IoT compatibility service first.
- Firmware HTTP 500: see [firmware diagnostics](firmware.md).
