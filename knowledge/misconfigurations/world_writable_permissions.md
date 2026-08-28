# World-writable files and directories

A file or directory with permissions such as `0777` (or specifically the
world-write bit set, e.g. `0666`/`0777`) can be modified by any local user
on the system, regardless of ownership.

**Why it's a real vulnerability:** if the writable file is a script,
configuration, or binary that runs with elevated privileges (e.g. a cron
job or SUID binary's supporting file), a low-privileged local user can
modify it to achieve privilege escalation. World-writable directories in a
program's `$PATH` are a related and equally exploitable pattern.
