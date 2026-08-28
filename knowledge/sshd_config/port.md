# Port

Sets the TCP port the SSH daemon listens on.

- Default is `22`.
- Changing it (e.g. `Port 2222`) is sometimes used to reduce automated
  scanning noise, but is not a security control on its own.

**Note for training scenarios:** leaving SSH on the well-known default port
22 makes it trivially discoverable by any port scan (e.g. `nmap -p 22`),
which is realistic and expected for a intentionally exposed training target.
