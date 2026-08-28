# LoginGraceTime

Sets how long the server waits for a client to successfully authenticate
before disconnecting an unauthenticated connection.

- Default is typically `120` seconds.
- `LoginGraceTime 0` disables the timeout, holding the connection open
  indefinitely while unauthenticated.

**Vulnerability note:** a disabled or very long grace time lets an attacker
hold open large numbers of unauthenticated connections, which can be used to
exhaust the server's `MaxStartups` connection slots as a denial-of-service
against legitimate logins.
