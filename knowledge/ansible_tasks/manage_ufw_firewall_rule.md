# Ansible: manage firewall rules with ufw

```yaml
- name: Allow SSH through the firewall
  community.general.ufw:
    rule: allow
    port: '22'
    proto: tcp

- name: Set default incoming policy to deny
  community.general.ufw:
    default: deny
    direction: incoming

- name: Enable ufw
  community.general.ufw:
    state: enabled
```

To deliberately expose a training VM instead of hardening it, set the
default incoming policy to `allow` or omit ufw entirely so the host relies
on no firewall filtering at all.
