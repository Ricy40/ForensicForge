# Database service exposed without authentication

A database (e.g. MongoDB, Redis, MySQL) bound to a network-reachable
interface with authentication disabled or left on default credentials
allows any network client to read or modify its contents directly.

**Why it's a real vulnerability:** this pattern has caused numerous
real-world mass data breaches, since automated internet-wide scanners
specifically look for exactly this condition. It is a useful training
target for demonstrating data exfiltration without needing to exploit any
application logic — the misconfiguration alone is sufficient.
