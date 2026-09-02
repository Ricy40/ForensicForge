# Anonymous FTP access with upload enabled

Running an FTP server (e.g. `vsftpd`) with anonymous login enabled lets any
unauthenticated client connect and browse the server's files. If upload is
also enabled, anyone can write arbitrary files to the server with no
credentials at all.

**Why it's a real vulnerability:** anonymous read access alone exposes
whatever the FTP root contains to anyone on the network; anonymous *write*
access goes further, letting an attacker plant files (malware, web shells if
the FTP root overlaps a web server's document root, or files designed to
fill the disk) without ever authenticating. It's a classic, easy-to-verify
entry vector for teaching unauthenticated-access scenarios.
