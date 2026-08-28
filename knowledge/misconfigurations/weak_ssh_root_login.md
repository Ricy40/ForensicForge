# Weak SSH configuration (root login + password auth)

Combining `PermitRootLogin yes` with `PasswordAuthentication yes` allows an
attacker to brute-force the root account directly over SSH, with no need to
compromise a lower-privileged user first and escalate.

**Why it's a real vulnerability:** it removes a layer of defense-in-depth —
a single guessed, leaked, or reused password grants full root access
immediately, rather than a foothold that still requires privilege escalation.
This is one of the most common intentionally-introduced weaknesses in SSH
pentesting labs because it is realistic and trivially exploitable with
standard brute-force tooling.
