# Keydous Keyboard v0.3.0

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
