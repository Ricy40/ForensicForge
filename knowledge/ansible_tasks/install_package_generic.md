# Ansible: install a package (distribution-agnostic)

```yaml
- name: Install a package
  ansible.builtin.package:
    name: "{{ package_name }}"
    state: present
```

`ansible.builtin.package` dispatches to the correct package manager module
(`apt`, `dnf`, `yum`, etc.) based on the target's facts, so it is the
preferred choice over calling a distribution-specific module directly
unless distribution-specific options are needed.

To intentionally install an outdated version instead of the latest, pin
a specific version string in `name` (e.g. `openssh-server=1:7.6p1-4`) and
set `state: present` rather than `state: latest`.
