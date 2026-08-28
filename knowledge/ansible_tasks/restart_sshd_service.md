# Ansible: restart sshd via a handler

Configuration changes to `/etc/ssh/sshd_config` only take effect after sshd
is restarted. Use a handler so the restart only fires once, after all
config tasks in the play have run:

```yaml
handlers:
  - name: restart sshd
    ansible.builtin.service:
      name: sshd
      state: restarted
```

Tasks that change sshd_config should `notify: restart sshd` rather than
restarting the service directly in the task itself.
