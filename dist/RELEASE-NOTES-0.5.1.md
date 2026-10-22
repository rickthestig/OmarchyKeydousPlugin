# Keydous Keyboard v0.5.1

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
