import pytest
import yaml

from forensicforge.provision.ansible_writer import AnsibleParseError, write_ansible_role
from forensicforge.provision.orchestrator import _sanitize_run_name
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


def test_write_vagrantfile_sets_a_deterministic_vmname_and_installs_modern_ansible_via_pip3(tmp_path):
    """Regression test for two real fixes: a deterministic Hyper-V VM name
    (build-scenario's image-export step needs to find the VM by name), and
    installing a modern Ansible via pip3 rather than leaving it to
    ansible_local's own install logic (a PPA-resolution error, then a
    get-pip.py Python-version incompatibility, then a "pip: command not
    found") or apt's own `ansible` package (2.9.6, which predates
    Ansible's collections system - `community.general.ufw` failed to
    resolve at all, confirmed live). `pip3 install ansible` - the full
    package, not the minimal `ansible-core` - bundles community.general
    and other collections this project's generated roles need.
    `ansible.install = false` tells ansible_local not to try installing
    anything itself."""
    path = write_vagrantfile(tmp_path, hostname="forensicforge-20260101-000000")

    content = path.read_text(encoding="utf-8")
    assert 'h.vmname = "forensicforge-20260101-000000"' in content
    assert "apt-get install -y -qq python3-pip python3-pymysql python3-psycopg2" in content
    assert "pip3 install --quiet ansible" in content
    assert "ansible.install = false" in content
    assert 'ansible.install_mode = "pip"' not in content
    assert "ansible.pip_install_cmd" not in content
    assert "apt-get install -y -qq ansible\"" not in content


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


def test_write_ansible_role_rejects_template_module_fast(tmp_path):
    """Regression test for a real failure: a web-app-misconfig spec
    generated a task using ansible.builtin.template, referencing a .j2
    file this pipeline never creates (only tasks/main.yml is written) -
    the live boot got ~10 minutes in before failing on it. Caught here
    instantly instead, at generation time, before any VM boot."""
    raw_output = """\
```yaml
- name: Enable directory listing in Apache
  ansible.builtin.template:
    src: templates/apache_directory_listing.conf.j2
    dest: /etc/apache2/conf-available/directory-listing.conf
```

**Applied misconfigurations:**
1. Directory listing enabled.
"""
    with pytest.raises(AnsibleParseError, match="ansible.builtin.template"):
        write_ansible_role(raw_output, tmp_path / "run")

    assert not (tmp_path / "run").exists()


def test_write_ansible_role_rejects_copy_with_src(tmp_path):
    raw_output = """\
```yaml
- name: Copy a config file
  ansible.builtin.copy:
    src: files/some_config.conf
    dest: /etc/some_config.conf
```

**Applied misconfigurations:**
1. Something.
"""
    with pytest.raises(AnsibleParseError, match="src:"):
        write_ansible_role(raw_output, tmp_path / "run")


def test_write_ansible_role_rejects_mysql_secure_installation_fast(tmp_path):
    """Regression test for a real failure: a database-misconfiguration
    spec's `ansible.builtin.shell: mysql_secure_installation` task hung
    for 10+ minutes with zero progress before being interrupted by hand -
    mysql_secure_installation is interactive and Ansible provides no
    stdin, so it hangs forever rather than failing. Caught here instantly
    instead, at generation time, before any VM boot - unlike the other
    fast-fail checks, this failure mode doesn't even fail loudly on its
    own; it just hangs silently, which is why catching it here matters
    even more."""
    raw_output = """\
```yaml
- name: Secure MySQL installation
  ansible.builtin.shell: mysql_secure_installation
  args:
    creates: /root/.mysql_secret
```

**Applied misconfigurations:**
1. Something.
"""
    with pytest.raises(AnsibleParseError, match="mysql_secure_installation"):
        write_ansible_role(raw_output, tmp_path / "run")


def test_write_ansible_role_rejects_interactive_command_module_dict_form(tmp_path):
    raw_output = """\
```yaml
- name: Secure MySQL installation
  ansible.builtin.command:
    cmd: mysql_secure_installation
```

**Applied misconfigurations:**
1. Something.
"""
    with pytest.raises(AnsibleParseError, match="mysql_secure_installation"):
        write_ansible_role(raw_output, tmp_path / "run")


def test_write_ansible_role_allows_other_shell_commands(tmp_path):
    raw_output = """\
```yaml
- name: Restart apache safely
  ansible.builtin.shell: systemctl restart apache2
```

**Applied misconfigurations:**
1. Something.
"""
    role_dir, _ = write_ansible_role(raw_output, tmp_path / "run")
    assert role_dir.exists()


def test_write_ansible_role_rejects_nonexistent_firewall_module(tmp_path):
    """Regression test for a real failure: a database-misconfiguration
    spec used `ansible.builtin.firewall`, which does not exist in Ansible
    at all (not a resolution issue - a plainly invented module name) -
    confirmed live, failing ~10 minutes into a boot with "couldn't
    resolve module/action". Caught here instantly instead."""
    raw_output = """\
```yaml
- name: Remove firewall rules that allow external access
  ansible.builtin.firewall:
    name: default
    state: absent
```

**Applied misconfigurations:**
1. Something.
"""
    with pytest.raises(AnsibleParseError, match="ansible.builtin.firewall"):
        write_ansible_role(raw_output, tmp_path / "run")


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


# --- --name / _sanitize_run_name and vm_hostname staying spaceless ---

def test_sanitize_run_name_keeps_spaces_strips_invalid_path_chars():
    assert _sanitize_run_name("ssh bastion") == "ssh bastion"
    assert _sanitize_run_name('weird<>:"/\\|?*name') == "weirdname"


def test_provision_spec_appends_sanitized_name_to_run_dir(tmp_path, monkeypatch):
    from forensicforge import config
    from forensicforge.provision import orchestrator
    from forensicforge.service import GenerationResult

    monkeypatch.setattr(config, "GENERATED_DIR", tmp_path)
    monkeypatch.setattr(orchestrator, "generate_vm_spec", lambda spec, use_rag=True: GenerationResult(output=VALID_RAG_OUTPUT))
    monkeypatch.setattr(orchestrator, "make_run_id", lambda: "20260101-000000")

    result = orchestrator.provision_spec("a spec", name="ssh bastion")

    assert result.run_id == "20260101-000000-ssh bastion"
    assert result.run_dir == tmp_path / "20260101-000000-ssh bastion"
    # The folder name can carry the human-readable suffix, but the guest
    # hostname / Hyper-V VM name can't contain spaces - vm_hostname must
    # stay derived from the timestamp alone regardless of --name.
    assert result.vm_hostname == "forensicforge-20260101-000000"
    assert " " not in result.vm_hostname


def test_provision_spec_without_name_is_unchanged(tmp_path, monkeypatch):
    from forensicforge import config
    from forensicforge.provision import orchestrator
    from forensicforge.service import GenerationResult

    monkeypatch.setattr(config, "GENERATED_DIR", tmp_path)
    monkeypatch.setattr(orchestrator, "generate_vm_spec", lambda spec, use_rag=True: GenerationResult(output=VALID_RAG_OUTPUT))
    monkeypatch.setattr(orchestrator, "make_run_id", lambda: "20260101-000000")

    result = orchestrator.provision_spec("a spec")

    assert result.run_id == "20260101-000000"
    assert result.vm_hostname == "forensicforge-20260101-000000"
