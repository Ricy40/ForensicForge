# Disabled or missing audit logging

A host with system/authentication logging disabled (e.g. `rsyslog`/`auditd`
stopped, or SSH login logging suppressed) leaves no trail of who accessed
the system or what they did once inside.

**Why it's a real vulnerability:** it is not an initial-access vector on its
own, but it removes the ability to detect or investigate a compromise after
the fact — directly relevant to forensic training scenarios, since it forces
learners to rely on artifacts other than the usual log files (e.g. shell
history, filesystem timestamps, memory) when logs have been disabled or
tampered with.
