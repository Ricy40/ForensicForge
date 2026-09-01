import pytest
import yaml

from forensicforge.provision.ansible_writer import AnsibleParseError, write_ansible_role
from forensicforge.provision.vagrantfile_writer import write_vagrantfile

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


def test_write_vagrantfile_sets_a_deterministic_vmname_and_pip_install_mode(tmp_path):
    """Regression test for two real fixes this week: a deterministic
    Hyper-V VM name (build-scenario's image-export step needs to find the
    VM by name), and installing Ansible via pip rather than the PPA-based
    default (which failed live, independently, on two different runs with
    the same PPA-resolution error)."""
    path = write_vagrantfile(tmp_path, hostname="forensicforge-20260101-000000")

    content = path.read_text(encoding="utf-8")
    assert 'h.vmname = "forensicforge-20260101-000000"' in content
    assert 'ansible.install_mode = "pip"' in content
    assert "bootstrap.pypa.io/pip/3.8/get-pip.py" in content


INDENTED_FENCE_OUTPUT = """\
1. ```yaml
   - name: Set non-standard port for SSH daemon
     ansible.builtin.lineinfile:
       path: /etc/ssh/sshd_config
       regexp: '^#Port 22$'
       line: 'Port 2222'
       state: present

   - name: Enable password authentication for training purposes
     ansible.builtin.lineinfile:
       path: /etc/ssh/sshd_config
       regexp: '^#PasswordAuthentication no$'
       line: 'PasswordAuthentication yes'
       state: present
   ```

2. **Applied misconfigurations**:
   - `Port 2222`: leaves SSH trivially discoverable by a port scan.
"""


def test_write_ansible_role_handles_yaml_fence_nested_in_a_numbered_list(tmp_path):
    """Regression test for a real failure: when the LLM wraps the whole
    ```yaml fence inside a numbered markdown list item ("1. ```yaml"),
    every line in the block carries the same leading indentation from
    that nesting - extract_yaml_block()'s old plain .strip() only trimmed
    the *first* line's leading whitespace (since str.strip() only touches
    the very start/end of the whole string), desyncing "- name:" from its
    own sibling keys one indent level deeper than they should be relative
    to it. Confirmed as the actual root cause via direct inspection of the
    extracted string, not visible from the raw LLM output alone."""
    role_dir, repairs = write_ansible_role(INDENTED_FENCE_OUTPUT, tmp_path / "run")

    assert repairs == []
    tasks = yaml.safe_load((role_dir / "tasks" / "main.yml").read_text(encoding="utf-8"))
    assert len(tasks) == 2
    assert tasks[0]["ansible.builtin.lineinfile"]["line"] == "Port 2222"


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
