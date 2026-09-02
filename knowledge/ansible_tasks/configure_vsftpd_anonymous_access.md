# Ansible: enable anonymous FTP access in vsftpd

```yaml
- name: Install vsftpd
  ansible.builtin.package:
    name: vsftpd
    state: present

- name: Enable anonymous FTP access
  ansible.builtin.lineinfile:
    path: /etc/vsftpd.conf
    regexp: '^anonymous_enable'
    line: 'anonymous_enable=YES'
    state: present

- name: Restart vsftpd to apply the config change
  ansible.builtin.service:
    name: vsftpd
    state: restarted
```

The restart task is required, not optional: installing the `vsftpd` package
already starts the service under its original (anonymous-disabled) config,
so editing `/etc/vsftpd.conf` afterward only changes the file on disk - the
already-running daemon keeps serving its original config until it's
explicitly restarted. This was added to the knowledge base after a live
generation and manual FTP login test showed exactly that gap: the
`lineinfile` task alone produced a config file that correctly said
`anonymous_enable=YES` and was verified `TRUE` against the file, but a real
`ftp` login still failed with `530 Login incorrect` until the service was
restarted. Any task here that edits a running service's config file needs
an explicit `ansible.builtin.service` restart task immediately after it -
never rely on `notify:`, since no handlers file exists in this project's
generated roles.

When citing this in an "Applied misconfigurations" claim, quote the exact
`line:` value as a single, contiguous backtick span - e.g.
`` `anonymous_enable=YES` `` - not the directive name and value as separate
fragments.
