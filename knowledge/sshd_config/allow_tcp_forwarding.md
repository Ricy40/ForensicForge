# AllowTcpForwarding

Controls whether SSH clients can set up TCP port forwarding (local, remote,
or dynamic/SOCKS) through the server.

- `AllowTcpForwarding yes` (default) permits forwarding.
- `AllowTcpForwarding no` disables it.

**Vulnerability note:** an authenticated but otherwise low-privileged user
can use forwarding to pivot into internal network segments the SSH server
can reach, turning a single compromised account into a network foothold.
