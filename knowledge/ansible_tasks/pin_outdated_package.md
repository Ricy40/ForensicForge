# Ansible: leave a package outdated and unpatched

```yaml
- name: Pin a package at its current, outdated version
  ansible.builtin.dpkg_selections:
    name: openssl
    selection: hold

- name: Disable automatic security updates
  ansible.builtin.lineinfile:
    path: /etc/apt/apt.conf.d/20auto-upgrades
    regexp: '^APT::Periodic::Unattended-Upgrade'
    line: 'APT::Periodic::Unattended-Upgrade "0";'
    create: true
```

`dpkg_selections` with `selection: hold` marks a package so `apt upgrade`
skips it - a real, standard way to keep an outdated, vulnerable version
installed on purpose. `20auto-upgrades` is the actual Ubuntu config file
`unattended-upgrades` reads; setting the line `APT::Periodic::Unattended-Upgrade "0";`
there turns off automatic security patching entirely, the same file and
directive a real misconfigured or neglected server would have. Use both
together for a training VM that's deliberately behind on patches -
`dpkg_selections` for a specific outdated package, the `lineinfile` task
for the system-wide update policy.

When citing this in an "Applied misconfigurations" claim, quote the
exact `line:` value as a single, contiguous backtick span - e.g.
`` `APT::Periodic::Unattended-Upgrade "0";` `` - not the directive name
and value as separate fragments. The whole line, verbatim, is what gets
checked against the live file afterward.
