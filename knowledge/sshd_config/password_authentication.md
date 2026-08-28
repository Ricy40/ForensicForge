# PasswordAuthentication

Controls whether SSH accepts a plain password as a login credential, as
opposed to requiring a public key.

- `PasswordAuthentication yes` allows password-based login.
- `PasswordAuthentication no` forces key-based authentication only.

**Vulnerability note:** password authentication is vulnerable to brute-force
and credential-stuffing attacks in a way key-based authentication is not.
Combined with weak or reused passwords, this is one of the most common
initial-access vectors against internet-facing SSH services.
