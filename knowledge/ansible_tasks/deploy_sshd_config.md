# Ansible: set individual sshd_config directives

Use `ansible.builtin.lineinfile` to set or override a single directive
without templating the whole file:

```yaml
- name: Set PermitRootLogin in sshd_config
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PermitRootLogin'
    line: 'PermitRootLogin yes'
    validate: '/usr/sbin/sshd -t -f %s'
  notify: restart sshd
```

For scenarios that change many directives at once, prefer templating the
whole file instead:

```yaml
- name: Deploy sshd_config from template
  ansible.builtin.template:
    src: sshd_config.j2
    dest: /etc/ssh/sshd_config
    validate: '/usr/sbin/sshd -t -f %s'
  notify: restart sshd
```

The `validate` argument runs `sshd -t` against the new file before it
replaces the live config, preventing a syntax error from locking out SSH
access entirely.
