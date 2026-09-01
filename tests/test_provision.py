import pytest

from forensicforge.provision.ansible_writer import AnsibleParseError, write_ansible_role

VALID_RAG_OUTPUT = """\
Here is the configuration:

```yaml
- name: Install OpenSSH server
  ansible.builtin.package:
    name: openssh-server
    state: present

- name: Permit root login (deliberately weak)
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^PermitRootLogin'
    line: 'PermitRootLogin yes'
```

**Applied misconfigurations:**
1. `PermitRootLogin yes` - allows direct root login.
"""


def test_write_ansible_role_writes_task_and_meta_files(tmp_path):
    run_dir = tmp_path / "20260101-000000"

    role_dir, repairs = write_ansible_role(VALID_RAG_OUTPUT, run_dir, role_name="training_vm")

    assert role_dir == run_dir / "roles" / "training_vm"
    assert repairs == []
    tasks_file = role_dir / "tasks" / "main.yml"
    meta_file = role_dir / "meta" / "main.yml"
    playbook_file = run_dir / "playbook.yml"

    assert tasks_file.exists()
    assert meta_file.exists()
    assert playbook_file.exists()

    tasks_text = tasks_file.read_text(encoding="utf-8")
    assert "Install OpenSSH server" in tasks_text
    assert "PermitRootLogin yes" in tasks_text
    assert "training_vm" in playbook_file.read_text(encoding="utf-8")


def test_write_ansible_role_rejects_output_with_no_yaml_block(tmp_path):
    raw_output = "Sorry, here is a description with no code block at all."

    with pytest.raises(AnsibleParseError) as exc_info:
        write_ansible_role(raw_output, tmp_path / "run")

    assert exc_info.value.raw_output == raw_output
    assert not (tmp_path / "run").exists()


def test_write_ansible_role_rejects_invalid_yaml(tmp_path):
    raw_output = """\
```yaml
- name: broken task
  this is not: valid: yaml: at all
```
"""
    with pytest.raises(AnsibleParseError):
        write_ansible_role(raw_output, tmp_path / "run")

    assert not (tmp_path / "run").exists()


def test_write_ansible_role_rejects_non_task_yaml(tmp_path):
    raw_output = """\
```yaml
just_a_string: not a task list
```
"""
    with pytest.raises(AnsibleParseError):
        write_ansible_role(raw_output, tmp_path / "run")

    assert not (tmp_path / "run").exists()
