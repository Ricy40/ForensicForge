# MaxAuthTries

Sets the maximum number of authentication attempts permitted per SSH
connection before the server disconnects the client.

- Default is typically `6`.
- A high value (e.g. `MaxAuthTries 1000`) effectively removes the per-connection
  attempt limit.

**Vulnerability note:** a high or unset limit makes online brute-force and
password-spraying attacks against the service far more efficient, since an
attacker can attempt many credentials per TCP connection instead of
reconnecting after each failure.
