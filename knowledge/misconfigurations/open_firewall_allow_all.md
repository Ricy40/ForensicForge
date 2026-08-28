# Open firewall / allow-all inbound policy

A host firewall configured with a default-allow inbound policy (or with no
firewall enabled at all) permits traffic to every listening service,
regardless of whether that service was intended to be reachable from the
network the VM sits on.

**Why it's a real vulnerability:** it removes network-layer filtering as a
compensating control, so any misconfigured or vulnerable service on the host
becomes directly reachable. In production this is flagged as a critical
finding; in a training VM it is often introduced deliberately so learners can
observe and enumerate every open port with a scanner.
