# Keydous Keyboard v0.5.0

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
