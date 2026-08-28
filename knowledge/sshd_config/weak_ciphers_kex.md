# Ciphers / KexAlgorithms

Restricts which symmetric ciphers and key-exchange algorithms the SSH server
will negotiate with a connecting client.

- Modern secure config restricts this list to strong algorithms, e.g.
  `Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com`.
- Leaving the default/legacy list enabled (or explicitly adding entries like
  `aes128-cbc`, `3des-cbc`, or `diffie-hellman-group1-sha1`) permits weak,
  legacy algorithms.

**Vulnerability note:** weak ciphers and key-exchange methods (CBC-mode
ciphers, small Diffie-Hellman groups, SHA-1-based KEX) are susceptible to
known cryptographic attacks and downgrade attacks, undermining the
confidentiality of the SSH channel.
