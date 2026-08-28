# Ansible: create a user with a set password

```yaml
- name: Create a local user account
  ansible.builtin.user:
    name: demo
    password: "{{ 'password123' | password_hash('sha512') }}"
    shell: /bin/bash
    state: present
```

`password_hash` stores a hashed password in `/etc/shadow` rather than the
plaintext value, even though the plaintext used to generate it (as in this
example) may itself be weak by design for a training scenario.

**Vulnerability note:** using a common, easily guessable password (as
opposed to a hashing weakness) is what makes an account like this a
realistic target for credential-stuffing or dictionary attacks.
