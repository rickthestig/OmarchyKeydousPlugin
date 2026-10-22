# Changelog

## 0.5.1 — 2026-10-22

- Stage installations outside the watched plugin tree and replace existing
  plugins with Linux atomic directory exchange. Do not rewrite unchanged bar
  configuration. Installation never launches or restarts Quickshell.
- Lock requests immediately while helpers are starting, preventing rapid clicks
  from replacing a queued command before Quickshell reports it running.
- Collect worker output at process exit, stop helpers during widget destruction,
  detach output parsers first and ignore callbacks after teardown starts.
- Recover from helper launch failure and reject out-of-range painter slots.
- Add an isolated, mock-only Quickshell lifecycle check covering repeated
  creation/destruction, completed replies, rapid requests, helper cleanup and
  keyboard hit testing.

Validation uses native Omarchy UI components with an offscreen popup host. It
covers this plugin's lifecycle, not the Wayland popup backend or all other shell
plugins. The earlier host shutdown crash was not proven to originate in Keydous.

## 0.5.0 — 2026-10-22

- Rework the panel with native Omarchy buttons, dropdowns, sliders, toggles,
  number fields, theme typography, section headers and separators.
- Share one graphical keyboard between Paint, Keys and the renamed Travel tab.
- Click a key to read its travel settings; highlight the selection and annotate
  previously read actuation distances on the drawing.
- Add validated millimetre inputs and sliders, with Apply to key pinned in the
  footer. Keep backups, stale-state checks and per-key readback verification.
- Resolve Fn drawings using base physical positions while retaining live Fn
  assignment labels. Preserve the existing model capability restrictions.

Validation: 64 Python tests, QML lint and an isolated offscreen preview with
keyboard selection/erase hit checks. Desktop positioning and physical switch
writes still require a live keyboard session.

## 0.4.0 — 2026-10-22

- Replace NJ81-only discovery with an exact-record Keydous model catalogue,
  capability checks and model-specific profile counts.
- Enable gen2 `v` lighting/painting on compatible NJ68, NJ80, NJ81, NJ98-CP and
  AJ100 records; add the legacy NJ98-CP yc500 painting and keymap-read formats.
- Isolate local paintings by model, label numpad usages and record the actual
  device identity in snapshots.
- Gate advanced settings and IoT/firmware bridges to record 4207. Unknown
  families and unsupported lighting tables stay detection-only or read-only.
- Add catalogue refresh tooling, expanded USB permission rules and a model
  compatibility table. Other physical layouts use hardware slot view.

Cross-model support is experimental, with simulated protocol coverage rather
than hardware validation on every model. This is not universal Keydous support.
See docs/compatibility.md for enabled records and limitations.

## 0.3.0 — 2026-10-22

- Add a Paint tab with drag painting, right-drag erasing, colour picker, swatches,
  fill/clear, discard edits and independent brightness.
- Switch between the NJ81 MAX 75% / 81-key physical view and hardware slot view.
- Resolve unique live key assignments to physical positions and remember mappings
  across remaps; leave ambiguous positions dimmed and editable in slot view.
- Correct the Del key above PgUp/PgDn in the navigation column.
- Keep local painting copies and pre-upload snapshots; limit uploads to one per
  ten seconds and verify custom lighting mode after transfer.
- Extend simulated protocol and layout coverage to 55 tests.

Pattern slot 1 is shared across onboard profiles. Pattern colour readback is
unreliable; check uploaded colours on the keyboard. Physical layout slot mapping
requires unique live assignments on the first load. Other keyboard models remain
unsupported. Firmware updating remains experimental and unverified end to end.

## 0.2.1 — 2026-10-20

Initial public source package, marked experimental.

- Native Lighting, Keys, Switches, Device and Firmware tabs.
- Remapping, ASCII text macros, rapid-trigger settings and device options.
- Display clock and still-image uploads.
- Local write snapshots, readback and stale-state checks.
- Experimental Linux IoT Manager HID compatibility and vendor-update bridge.
- Firmware HTTP-error diagnostics with update status kept unknown.
- User-local installer, allowlisted source packaging and GitHub Actions checks.

Firmware updates and advanced physical writes require further hardware
validation. See docs/firmware.md for the current support boundary.
