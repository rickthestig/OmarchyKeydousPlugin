# Contributing

Python 3.11+ is sufficient for the core helpers and tests; no pip packages are
required. ImageMagick 7 is optional for the real image-conversion test.

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/package.py --check
```

Use a separate development clone. Install it with `scripts/install.py --enable`
when you intend to change the running widget. Restart the shell if QML remains
cached. Python helpers are launched afresh for each native operation.

For bug reports include the keyboard model, device record, connection mode,
firmware version, plugin version, action and exact error. Distinguish simulated
tests from physical hardware checks. For firmware HTTP errors, review and
attach the bounded `last-check-error.json` diagnostic if appropriate.

Keep model identity guards, slot bounds, stale-state checks and backups intact.
Add protocol evidence before supporting another model or changing units,
packet shapes, boot transport or firmware writes. USB IDs alone are shared
across boards. Report firmware changes as experimental until validated on the
exact hardware. Keep proprietary installers, firmware packages, vendor source
bundles, personal keymaps and machine-specific configuration out of commits.
