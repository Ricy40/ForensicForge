# Ansible: create a misconfigured SUID binary for a privilege escalation exercise

```yaml
- name: Set an SUID binary to demonstrate privilege escalation
  ansible.builtin.copy:
    content: |
      #!/bin/sh
      exec /bin/sh
    dest: /usr/local/suid_binary
    mode: '04755'
```

Use a YAML block scalar (`content: |`) for any file content spanning more
than one line - never a single-quoted string with `\n` escapes inside it.
Single-quoted YAML scalars do not interpret backslash escapes at all (only
doubling a quote, `''`, means anything); writing `content: '#!/bin/sh\nexec
/bin/sh'` produces a *literal* backslash followed by the letter `n` in the
file, not a line break. This was added to the knowledge base after exactly
that happened in a real generation: a shebang-based script written as a
single-quoted string with `\n` separators produced a one-line file whose
"interpreter" was the entire garbled string, so the kernel couldn't exec it
at all - the SUID bit was set correctly and verified, but the file itself
could never run. `content: |` (a real block scalar) sidesteps the problem
entirely by keeping actual line breaks in the YAML source.

`mode: '04755'` sets the SUID bit (the leading `4`) plus `rwxr-xr-x` -
readable and executable by anyone, writable only by the owner (root, since
tasks in this project run with `become: true`). Any local user who executes
the binary then runs with the file owner's privileges, not their own.
