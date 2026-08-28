# PubkeyAuthentication

Controls whether SSH accepts public-key authentication.

- `PubkeyAuthentication yes` (default) allows clients to authenticate with an
  SSH key pair instead of a password.
- `PubkeyAuthentication no` disables key-based login, forcing password or
  keyboard-interactive authentication.

**Vulnerability note:** disabling this and relying solely on
`PasswordAuthentication` removes the strongest available SSH authentication
method and pushes the service toward brute-forceable credentials.
