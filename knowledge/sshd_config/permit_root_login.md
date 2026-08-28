# PermitRootLogin

Controls whether the root user can log in directly over SSH.

- `PermitRootLogin yes` allows direct root login with a password or key.
- `PermitRootLogin no` (secure default on modern distributions) disables it entirely.
- `PermitRootLogin prohibit-password` allows root login only via public key, never a password.

**Vulnerability note:** setting this to `yes` removes the need to compromise
a low-privileged account and then escalate — a single guessed or leaked
credential grants full root access immediately.
