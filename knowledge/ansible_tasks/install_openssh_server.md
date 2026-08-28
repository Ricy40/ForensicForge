# Ansible: install and enable OpenSSH server

```yaml
- name: Install OpenSSH server
  ansible.builtin.package:
    name: openssh-server
    state: present

- name: Ensure sshd is enabled and running
  ansible.builtin.service:
    name: sshd
    state: started
    enabled: true
```

Use this as the baseline pair of tasks whenever a scenario requires SSH
access to a VM before applying any further sshd_config changes.
