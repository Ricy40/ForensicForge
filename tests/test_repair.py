import yaml

from forensicforge.provision.ansible_writer import write_ansible_role
from forensicforge.provision.repair import (
    repair_lineinfile_backreferences,
    repair_user_module_path_misuse,
    repair_yaml_text,
)

# The exact shape of raw LLM output captured from real, live generations
# this week - see docs/METHODOLOGY.md ("Proving dynamic generation, and
# what it actually found" and the live-results section). Trimmed to the
# minimum needed to reproduce each bug, not copied verbatim in full.

POSTGRES_QUOTE_BUG_OUTPUT = """\
```yaml
- name: Install PostgreSQL package
  ansible.builtin.package:
    name: postgresql
    state: present

- name: Configure PostgreSQL to listen on all interfaces without authentication
  ansible.builtin.lineinfile:
    path: /etc/postgresql/12/main/postgresql.conf
    regexp: '^#listen_addresses'
    line: 'listen_addresses = '*''
```

**Applied misconfigurations:**
1. `listen_addresses = '*'` - exposes PostgreSQL on all network interfaces.
"""

SSH_BACKREF_TASKS_YAML = """\
- name: Set SSH port to 2222 for training purposes (not security control)
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#*Port [0-9]*'
    line: 'Port 2222'
    state: present

- name: Enable weak root login and password authentication for training purposes (not secure)
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#*(PermitRootLogin|PasswordAuthentication) [a-zA-Z]*'
    line: '\\1 yes'
    state: present
"""

USER_PATH_MISUSE_TASKS_YAML = """\
- name: Create a world-writable directory
  ansible.builtin.file:
    path: /var/tmp/shared_dir
    state: directory
    mode: '0777'

- name: Ensure shared directory is owned by root
  ansible.builtin.user:
    name: root
    group: root
    path: /var/tmp/shared_dir
    state: present
"""


# --- repair_yaml_text: the Postgres nested-quote failure ---

def test_repair_yaml_text_fixes_nested_single_quote_in_line_value():
    yaml_text = (
        "- name: x\n"
        "  ansible.builtin.lineinfile:\n"
        "    path: /etc/postgresql/12/main/postgresql.conf\n"
        "    regexp: '^#listen_addresses'\n"
        "    line: 'listen_addresses = '*''\n"
    )
    try:
        yaml.safe_load(yaml_text)
        assert False, "fixture should reproduce the real parse failure"
    except yaml.YAMLError as exc:
        repaired_text, note = repair_yaml_text(yaml_text, exc)

    assert repaired_text is not None
    assert note is not None
    tasks = yaml.safe_load(repaired_text)
    assert tasks[0]["ansible.builtin.lineinfile"]["line"] == "listen_addresses = '*'"


def test_repair_yaml_text_strips_spurious_backslash_escapes():
    """Regression test for a real, independent second failure of the same
    bug family: `line: 'listen_addresses = \\'localhost\\''` - the LLM
    applying Python/JS-style backslash escaping, which single-quoted YAML
    doesn't support at all. The naive fix (re-quote whatever's captured
    verbatim) produces valid YAML that still carries the literal, bogus
    backslashes into the config value - wrong for the file it's writing
    to, even though the YAML itself now parses."""
    yaml_text = (
        "- name: x\n"
        "  ansible.builtin.lineinfile:\n"
        "    path: /etc/postgresql/12/main/postgresql.conf\n"
        "    regexp: '^#listen_addresses'\n"
        "    line: 'listen_addresses = \\'localhost\\''\n"
    )
    try:
        yaml.safe_load(yaml_text)
        assert False, "fixture should reproduce the real parse failure"
    except yaml.YAMLError as exc:
        repaired_text, note = repair_yaml_text(yaml_text, exc)

    assert repaired_text is not None
    tasks = yaml.safe_load(repaired_text)
    assert tasks[0]["ansible.builtin.lineinfile"]["line"] == "listen_addresses = 'localhost'"


def test_repair_yaml_text_returns_none_for_unrelated_errors():
    yaml_text = "- name: x\n  this is not: valid: yaml: at all\n"
    try:
        yaml.safe_load(yaml_text)
        assert False, "fixture should be invalid YAML"
    except yaml.YAMLError as exc:
        repaired_text, note = repair_yaml_text(yaml_text, exc)

    assert repaired_text is None
    assert note is None


def test_write_ansible_role_recovers_from_real_postgres_quote_bug(tmp_path):
    """Integration test against the exact bug shape captured from a real,
    live generation this week (reproduced identically twice) - see
    docs/METHODOLOGY.md."""
    role_dir, repairs = write_ansible_role(POSTGRES_QUOTE_BUG_OUTPUT, tmp_path / "run")

    assert len(repairs) == 1
    assert "repaired an unescaped-quote" in repairs[0]
    tasks = yaml.safe_load((role_dir / "tasks" / "main.yml").read_text(encoding="utf-8"))
    lineinfile_task = next(t for t in tasks if "ansible.builtin.lineinfile" in t)
    assert lineinfile_task["ansible.builtin.lineinfile"]["line"] == "listen_addresses = '*'"


# --- repair_lineinfile_backreferences: the SSH \1 bug ---

def test_repair_lineinfile_backreferences_splits_into_one_task_per_alternative():
    tasks = yaml.safe_load(SSH_BACKREF_TASKS_YAML)

    repaired, notes = repair_lineinfile_backreferences(tasks)

    assert len(notes) == 1
    # The untouched Port task, plus one new task per alternative (2), not the
    # original single broken task.
    assert len(repaired) == 3
    broken_names = [t["name"] for t in repaired if "\\1" in str(t.get("ansible.builtin.lineinfile", {}).get("line", ""))]
    assert broken_names == []  # no task should still contain a literal backreference

    permit_task = next(t for t in repaired if "PermitRootLogin" in t["name"])
    assert permit_task["ansible.builtin.lineinfile"]["line"] == "PermitRootLogin yes"
    password_task = next(t for t in repaired if "PasswordAuthentication" in t["name"])
    assert password_task["ansible.builtin.lineinfile"]["line"] == "PasswordAuthentication yes"


def test_repair_lineinfile_backreferences_leaves_normal_tasks_untouched():
    tasks = yaml.safe_load("- name: x\n  ansible.builtin.lineinfile:\n    path: /etc/x\n    line: 'X yes'\n")

    repaired, notes = repair_lineinfile_backreferences(tasks)

    assert notes == []
    assert repaired == tasks


# --- repair_user_module_path_misuse: the ansible.builtin.user/path bug ---

def test_repair_user_module_path_misuse_rewrites_to_file_module():
    tasks = yaml.safe_load(USER_PATH_MISUSE_TASKS_YAML)

    repaired, notes = repair_user_module_path_misuse(tasks)

    assert len(notes) == 1
    assert "ansible.builtin.user" not in repaired[1]
    file_args = repaired[1]["ansible.builtin.file"]
    assert file_args == {"path": "/var/tmp/shared_dir", "state": "directory", "owner": "root", "group": "root"}


def test_repair_user_module_path_misuse_leaves_normal_user_tasks_untouched():
    tasks = yaml.safe_load("- name: x\n  ansible.builtin.user:\n    name: alice\n    password: '{{ \"x\" | password_hash(\"sha512\") }}'\n")

    repaired, notes = repair_user_module_path_misuse(tasks)

    assert notes == []
    assert repaired == tasks
