# Unpatched or outdated software

Pinning a package to an old version (or simply never applying security
updates) leaves the host exposed to any publicly known vulnerability fixed
in a later release.

**Why it's a real vulnerability:** once a CVE is published, proof-of-concept
exploit code is often available within days, and vulnerability scanners
will flag the exact version string. This is a deliberately easy target for
training scenarios because the vulnerability, its CVE identifier, and a
working exploit can all be looked up directly rather than discovered.
