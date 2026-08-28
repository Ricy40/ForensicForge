# PermitEmptyPasswords

Controls whether accounts with a blank password are allowed to log in over
SSH when `PasswordAuthentication` is enabled.

- `PermitEmptyPasswords yes` allows login with no password at all.
- `PermitEmptyPasswords no` (default) rejects blank-password accounts.

**Vulnerability note:** this is almost never intentional outside a deliberately
vulnerable training host — an empty password is a zero-effort compromise for
any account so configured.
