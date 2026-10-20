# Upload to GitHub later

This directory is the public source project. The experimental firmware bridge
and its validation limits are documented in README.md and docs/firmware.md.

## GitHub website

1. Create an empty repository named `omarchy-keydous` on GitHub. Leave the
   generated README, license and gitignore options unchecked.
2. Upload the project files, including `.github/workflows/checks.yml` and
   `.gitignore`. Do not upload `dist/`, local state or vendor downloads.
3. Use `Initial experimental release` as the commit message.

The source ZIP in `dist/` is also suitable as a release attachment. Extract it
first if using its files to populate a repository; uploading just the ZIP does
not make its contents browsable as repository source.

## Command line

From this project directory, initialize and commit if not already done:

```bash
git init -b main
git add .
git diff --cached --stat
git commit -m "Initial experimental release"
```

After creating the empty GitHub repository, replace `YOUR_USERNAME` below:

```bash
git remote add origin https://github.com/YOUR_USERNAME/omarchy-keydous.git
git push -u origin main
```

GitHub Actions runs the simulated protocol, installer and package checks on
push. Physical firmware updating remains unverified.
