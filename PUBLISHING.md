# Publishing later

This is a local source repository. No GitHub repository, remote, upload or
release is created by the preparation process.

1. Review the README's experimental-status notes and the current source.
2. Run validation and create the source archive:

   ```bash
   python3 -B -m unittest discover -s tests -v
   python3 -B scripts/package.py --check
   python3 -B scripts/package.py
   ```

3. Create an empty repository on GitHub, then set its URL and push:

   ```bash
   git remote add origin https://github.com/YOUR-USERNAME/omarchy-keydous.git
   git push -u origin main
   ```

4. Optionally create a **prerelease** for v0.4.0 and attach
   `dist/omarchy-keydous-0.4.0.zip`. Keep the firmware bridge's unverified status
   in the release notes. Use the 0.4.0 entry in CHANGELOG.md as the release body. Do not label firmware updating as hardware-validated.

The archive is built from an explicit source-file list. Vendor installers,
extracted binaries, firmware packages, cached JavaScript, personal keyboard
snapshots and local diagnostics are excluded. The development machine's
separate vendor-analysis directory is not part of this repository.

Future edits in the installed widget are not automatically synchronized back
to this source checkout. Copy intentional changes here before committing.
