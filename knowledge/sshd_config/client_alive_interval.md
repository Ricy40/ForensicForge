# ClientAliveInterval / ClientAliveCountMax

Together these control how long an idle SSH session is kept open before the
server forcibly disconnects it. The server sends a keepalive every
`ClientAliveInterval` seconds, and disconnects after `ClientAliveCountMax`
unanswered checks.

- `ClientAliveInterval 0` (default) disables the keepalive check entirely.
- A finite interval (e.g. `300`) with `ClientAliveCountMax 0` drops unresponsive
  sessions automatically.

**Vulnerability note:** with keepalives disabled, abandoned or hijacked
sessions (e.g. from an unlocked terminal) can remain authenticated
indefinitely, widening the window for session-based attacks.
