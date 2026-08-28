# X11Forwarding

Controls whether SSH clients can forward their X11 display through the
connection to run graphical applications remotely.

- `X11Forwarding yes` enables it.
- `X11Forwarding no` (recommended when not needed) disables it.

**Vulnerability note:** X11 forwarding has a history of implementation
vulnerabilities and, if misconfigured (e.g. `xhost +`), can expose the
client's display to injected input or screen capture from the remote host.
