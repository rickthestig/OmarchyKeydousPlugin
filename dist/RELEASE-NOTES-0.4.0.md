# Keydous Keyboard v0.4.0

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
