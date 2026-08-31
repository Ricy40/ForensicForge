import sys

import pytest

from forensicforge.validate.vulnerabilities import (
    VulnerabilityFinding,
    VulnerabilityReport,
    parse_applied_misconfigurations,
    verify_vulnerabilities,
)
from forensicforge.forensics.storyline_builder import build_storyline_from_vulnerabilities

LINEINFILE_TASKS = """\
- name: Allow root login (for pentesting exercise)
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^PermitRootLogin'
    line: 'PermitRootLogin yes'

- name: Install OpenSSH server
  ansible.builtin.package:
    name: openssh-server
    state: present
"""

CHANGED_TASK_LOG = """\
TASK [training_vm : Allow root login (for pentesting exercise)] **************
changed: [default]
"""

OK_TASK_LOG = """\
TASK [training_vm : Allow root login (for pentesting exercise)] **************
ok: [default]
"""

RAW_OUTPUT_WITH_BACKTICK_CLAIM = """\
```yaml
- name: Allow root login (for pentesting exercise)
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^PermitRootLogin'
    line: 'PermitRootLogin yes'
```

**Applied misconfigurations:**
1. `PermitRootLogin yes` - allows direct root login, sourced from misconfigurations/weak_ssh_root_login.md.
"""

RAW_OUTPUT_UNMATCHABLE_CLAIM = """\
```yaml
- name: Install PostgreSQL
  ansible.builtin.package:
    name: postgresql
    state: present
```

**Applied misconfigurations:**
1. PostgreSQL is exposed without authentication (source: misconfigurations/exposed_database_no_auth.md).
"""


def _write_role_tasks(tmp_path, content: str):
    role_dir = tmp_path / "role"
    (role_dir / "tasks").mkdir(parents=True)
    (role_dir / "tasks" / "main.yml").write_text(content, encoding="utf-8")
    return role_dir


# --- parse_applied_misconfigurations: tolerate real format variation ---

def test_parses_numbered_backtick_claim():
    claims = parse_applied_misconfigurations(RAW_OUTPUT_WITH_BACKTICK_CLAIM)

    assert len(claims) == 1
    assert claims[0].directives == ["PermitRootLogin yes"]


def test_parses_claim_with_no_backtick_directive():
    claims = parse_applied_misconfigurations(RAW_OUTPUT_UNMATCHABLE_CLAIM)

    assert len(claims) == 1
    assert claims[0].directives == []


def test_tolerates_bold_header_and_bullet_markers():
    raw = (
        "```yaml\n- name: x\n  ansible.builtin.package: {name: x, state: present}\n```\n\n"
        "2. **Applied misconfigurations**:\n"
        "   - The task disables auth, referencing `PasswordAuthentication no`.\n"
    )
    claims = parse_applied_misconfigurations(raw)

    assert len(claims) == 1
    assert claims[0].directives == ["PasswordAuthentication no"]


def test_no_section_header_yields_no_claims():
    assert parse_applied_misconfigurations("```yaml\n- name: x\n```\n") == []


# --- verify_vulnerabilities: claim matching + live check + attribution, vagrant mocked ---

def _mock_vagrant(monkeypatch, log_text: str, ssh_output: str):
    td = sys.modules["forensicforge.validate.test_deploy"]

    class FakeVagrant:
        def __init__(self, root, out_cm, err_cm, **kwargs):
            with out_cm() as fh:
                fh.write(log_text)

        def up(self, provider=None, provision=None):
            pass

        def ssh(self, command):
            return ssh_output

        def destroy(self):
            pass

    monkeypatch.setattr(td.vagrant, "Vagrant", FakeVagrant)


def test_verify_vulnerabilities_requires_generation_file(tmp_path):
    role_dir = _write_role_tasks(tmp_path, LINEINFILE_TASKS)

    with pytest.raises(FileNotFoundError, match="No generation.md"):
        verify_vulnerabilities(tmp_path, role_dir)


def test_matched_claim_true_and_attributed(tmp_path, monkeypatch):
    role_dir = _write_role_tasks(tmp_path, LINEINFILE_TASKS)
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_WITH_BACKTICK_CLAIM, encoding="utf-8")
    _mock_vagrant(monkeypatch, CHANGED_TASK_LOG, "PermitRootLogin yes\n")

    result = verify_vulnerabilities(tmp_path, role_dir)

    assert result.booted is True
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.verifiable is True
    assert finding.actual is True
    assert finding.attribution == "changed"
    assert "caused it" in finding.note


def test_matched_claim_true_but_not_attributed_ok_case(tmp_path, monkeypatch):
    """The exact week-3 PermitRootLogin gap: true on the VM, but the task
    reported 'ok' (already true), not 'changed' - not this run's doing."""
    role_dir = _write_role_tasks(tmp_path, LINEINFILE_TASKS)
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_WITH_BACKTICK_CLAIM, encoding="utf-8")
    _mock_vagrant(monkeypatch, OK_TASK_LOG, "PermitRootLogin yes\n")

    result = verify_vulnerabilities(tmp_path, role_dir)

    finding = result.findings[0]
    assert finding.actual is True
    assert finding.attribution == "ok"
    assert "NOT attributable" in finding.note


def test_claim_false_on_live_vm(tmp_path, monkeypatch):
    role_dir = _write_role_tasks(tmp_path, LINEINFILE_TASKS)
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_WITH_BACKTICK_CLAIM, encoding="utf-8")
    _mock_vagrant(monkeypatch, CHANGED_TASK_LOG, "PermitRootLogin no\n")

    result = verify_vulnerabilities(tmp_path, role_dir)

    finding = result.findings[0]
    assert finding.actual is False
    assert "NOT TRUE" in finding.note


def test_unmatchable_claim_is_reported_not_skipped(tmp_path):
    role_dir = _write_role_tasks(tmp_path, "- name: Install PostgreSQL\n  ansible.builtin.package:\n    name: postgresql\n    state: present\n")
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_UNMATCHABLE_CLAIM, encoding="utf-8")

    result = verify_vulnerabilities(tmp_path, role_dir)

    assert result.booted is False  # nothing checkable, no VM was ever booted
    assert len(result.findings) == 1
    assert result.findings[0].verifiable is False
    assert result.findings[0].actual is None
    assert "NOT VERIFIABLE" in result.findings[0].note


# --- storyline_builder: entry vector must be verified AND attributed ---

def _finding(**kwargs) -> VulnerabilityFinding:
    defaults = dict(claim="x", directive=None, verifiable=True, task_name="t", actual=True, attribution="changed")
    defaults.update(kwargs)
    return VulnerabilityFinding(**defaults)


def test_build_storyline_requires_a_verified_attributed_finding():
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(actual=True, attribution="ok"),  # true but not attributable - must not qualify
        _finding(actual=False, attribution="changed"),  # attributed but not actually true
        _finding(verifiable=False, actual=None, attribution=None),
    ])

    with pytest.raises(ValueError, match="no verified, attributable"):
        build_storyline_from_vulnerabilities(report, spec="Ubuntu server", run_id="20260101-000000")


def test_build_storyline_classifies_ssh_entry_vector():
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim="PermitRootLogin yes - allows direct root login", directive="PermitRootLogin yes",
                  task_name="Allow root login (for pentesting exercise)"),
    ])

    storyline = build_storyline_from_vulnerabilities(report, spec="Ubuntu SSH bastion host", run_id="20260101-000000")

    assert "SSH" in storyline.title
    assert storyline.artefacts[0].kind == "log_entry"
    assert storyline.artefacts[0].target_path == "/var/log/auth.log"
    assert "sshd" in storyline.artefacts[0].content
    assert len(storyline.artefacts) == 4  # entry vector + 3 generic post-entry artefacts


def test_build_storyline_narrative_names_the_actual_verified_claim_not_just_its_category():
    """Regression test for a real bug caught against a live run: the SSH
    bastion role's only verified+attributed claim was `Port 2222`
    (PermitRootLogin was true but attributed "ok" - not attributable - so
    correctly wasn't picked), but the narrative claimed "root login and/or
    password authentication left enabled" regardless, because the old
    per-category description text asserted specifics no particular finding
    had actually verified. The narrative must name the *specific* claim
    that qualified, not just its category."""
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim="`Port 2222`: leaving SSH on the default port is trivially discoverable",
                  directive="Port 2222", task_name="Set SSH to listen on a non-default port for training"),
    ])

    storyline = build_storyline_from_vulnerabilities(report, spec="Ubuntu SSH bastion host", run_id="20260829-105652")

    assert "Port 2222" in storyline.narrative
    assert "root login" not in storyline.narrative.lower()
    assert "password authentication" not in storyline.narrative.lower()


def test_build_storyline_classifies_non_ssh_entry_vector():
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim="Telnet service left enabled", directive=None, task_name="Install Telnet server (deliberate weakness)"),
    ])

    storyline = build_storyline_from_vulnerabilities(report, spec="Ubuntu server", run_id="20260101-000000")

    assert "Telnet" in storyline.title
    assert "telnetd" in storyline.artefacts[0].content
