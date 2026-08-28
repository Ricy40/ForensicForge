# Ansible: disable the host firewall entirely

```yaml
- name: Stop and disable ufw
  ansible.builtin.service:
    name: ufw
    state: stopped
    enabled: false
```

This is the deliberate-misconfiguration counterpart to enabling ufw: useful
when a training scenario calls for a VM with no host-level packet filtering
at all, so that any exposed service is reachable without a firewall rule
being the limiting factor.
