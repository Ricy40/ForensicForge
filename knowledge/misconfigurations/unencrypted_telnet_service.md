# Unencrypted remote access (telnet/FTP)

Running telnet or plain FTP for remote administration or file transfer
sends credentials and session data in cleartext over the network.

**Why it's a real vulnerability:** anyone able to observe network traffic
between the client and server (e.g. via ARP spoofing on a shared segment)
can recover login credentials and session content directly, with no
cryptographic attack required. This is a classic, easy-to-demonstrate
vulnerability for teaching packet capture and network sniffing techniques.
