import sys

import pytest
import yaml

from forensicforge.validate.vulnerabilities import (
    VulnerabilityFinding,
    VulnerabilityReport,
    _lineinfile_tasks,
    _match_claim,
    _match_mode_claim,
    _mode_tasks,
    _normalize_octal_mode,
    parse_applied_misconfigurations,
    verify_vulnerabilities,
)
from forensicforge.forensics.generators import fictional_business_context
from forensicforge.forensics.scenario_doc import render_scenario_markdown
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


def test_claim_reported_as_could_not_verify_on_ssh_connection_failure(tmp_path, monkeypatch):
    """Regression test for a real live bug: a role that changed sshd's
    Port and restarted the service broke this tool's own SSH access
    (assumes port 22, no way to discover the new one) - every check then
    failed with SSH's own exit 255. Must be reported distinctly from
    "NOT TRUE" (which asserts the claim is false) - the check never
    actually reached the guest, so nothing was confirmed either way."""
    import subprocess

    role_dir = _write_role_tasks(tmp_path, LINEINFILE_TASKS)
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_WITH_BACKTICK_CLAIM, encoding="utf-8")

    td = sys.modules["forensicforge.validate.test_deploy"]

    class FakeVagrant:
        def __init__(self, root, out_cm, err_cm, **kwargs):
            with out_cm() as fh:
                fh.write(CHANGED_TASK_LOG)

        def up(self, provider=None, provision=None):
            pass

        def ssh(self, command):
            raise subprocess.CalledProcessError(255, ["vagrant", "ssh"], output=b"Connection refused")

        def destroy(self):
            pass

    monkeypatch.setattr(td.vagrant, "Vagrant", FakeVagrant)

    result = verify_vulnerabilities(tmp_path, role_dir)

    finding = result.findings[0]
    assert finding.actual is None
    assert "COULD NOT VERIFY" in finding.note
    assert "NOT TRUE" not in finding.note


def test_matches_a_claim_whose_directive_is_bold_not_backticked(tmp_path):
    """Regression test for a real failure: a live run wrapped the actual
    directive in **bold** and used its only backtick span for an
    unrelated source citation (`` `source: misconfigurations/weak_ssh_root_login.md` ``),
    which made backtick-only matching pick up the citation as if it were
    the directive - never matching any task. Matching now searches the
    claim's whole text for a task's line value, independent of whatever
    the LLM chose to backtick or bold."""
    role_dir = _write_role_tasks(
        tmp_path,
        "- name: Enable root login with password authentication\n"
        "  ansible.builtin.lineinfile:\n"
        "    path: /etc/ssh/sshd_config\n"
        "    line: PermitRootLogin yes\n",
    )
    raw_output = (
        "```yaml\nfiller\n```\n\n"
        "**Applied misconfigurations:**\n\n"
        "1. **PermitRootLogin yes (`source: misconfigurations/weak_ssh_root_login.md`)** - "
        "a real vulnerability due to the risk of brute-force attacks on the root account.\n"
    )
    claims = parse_applied_misconfigurations(raw_output)
    lineinfile_tasks = _lineinfile_tasks(role_dir)
    task, directive = _match_claim(claims[0], lineinfile_tasks)

    assert task is not None
    assert task["name"] == "Enable root login with password authentication"
    assert directive == "PermitRootLogin yes"


def test_unmatchable_claim_is_reported_not_skipped(tmp_path):
    role_dir = _write_role_tasks(tmp_path, "- name: Install PostgreSQL\n  ansible.builtin.package:\n    name: postgresql\n    state: present\n")
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_UNMATCHABLE_CLAIM, encoding="utf-8")

    result = verify_vulnerabilities(tmp_path, role_dir)

    assert result.booted is False  # nothing checkable, no VM was ever booted
    assert len(result.findings) == 1
    assert result.findings[0].verifiable is False
    assert result.findings[0].actual is None
    assert "NOT VERIFIABLE" in result.findings[0].note


# --- mode-based claims (ansible.builtin.file/copy's mode:) ---
# Added after two of seven real evaluation-round specs (privilege
# escalation: world-writable sudoers entry + misconfigured SUID binary)
# came back entirely unverifiable - every claim they produced was a
# mode: value on file/copy tasks, none a lineinfile line, so the
# lineinfile-only mechanism found nothing checkable in either run.

PRIVESC_TASKS_YAML = """\
- name: Create a world-writable file in /etc/sudoers.d
  ansible.builtin.file:
    path: /etc/sudoers.d/world_writable
    state: touch
    mode: '0777'
    owner: root
    group: root
- name: Add a misconfigured SUID binary to the system
  ansible.builtin.copy:
    content: 'placeholder'
    dest: /usr/local/bin/misconfig_suid
    mode: '04755'
    owner: root
    group: root
"""

RAW_OUTPUT_PRIVESC = f"""\
```yaml
{PRIVESC_TASKS_YAML}```

**Applied misconfigurations**:
1. `path: /etc/sudoers.d/world_writable` sets world-writable permissions (`0777`) on a file in `/etc/sudoers.d`.
2. `mode: '04755'` on the SUID binary makes it executable by all users and allows setuid.
"""


def test_normalize_octal_mode_strips_leading_zero_and_matches_stat_output():
    assert _normalize_octal_mode("0777") == "777"
    assert _normalize_octal_mode("04755") == "4755"
    assert _normalize_octal_mode("not-a-mode") is None


def test_match_mode_claim_finds_file_and_copy_tasks(tmp_path):
    role_dir = _write_role_tasks(tmp_path, PRIVESC_TASKS_YAML)
    tasks = _mode_tasks(role_dir)
    claims = parse_applied_misconfigurations(RAW_OUTPUT_PRIVESC)

    assert len(tasks) == 2

    task0, mode0 = _match_mode_claim(claims[0], tasks)
    assert task0["name"] == "Create a world-writable file in /etc/sudoers.d"
    assert mode0 == "0777"

    task1, mode1 = _match_mode_claim(claims[1], tasks)
    assert task1["name"] == "Add a misconfigured SUID binary to the system"
    assert mode1 == "04755"


def test_verify_vulnerabilities_builds_stat_check_for_mode_claim(tmp_path, monkeypatch):
    role_dir = _write_role_tasks(tmp_path, PRIVESC_TASKS_YAML)
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_PRIVESC, encoding="utf-8")
    _mock_vagrant(monkeypatch, CHANGED_TASK_LOG.replace(
        "training_vm : Allow root login (for pentesting exercise)",
        "training_vm : Create a world-writable file in /etc/sudoers.d",
    ), "777\n")

    result = verify_vulnerabilities(tmp_path, role_dir)

    assert result.booted is True
    world_writable_finding = next(f for f in result.findings if "world_writable" in f.claim)
    assert world_writable_finding.verifiable is True
    assert world_writable_finding.actual is True
    assert "TRUE" in world_writable_finding.note


def test_verify_vulnerabilities_mode_claim_false_on_live_vm(tmp_path, monkeypatch):
    role_dir = _write_role_tasks(tmp_path, PRIVESC_TASKS_YAML)
    (tmp_path / "generation.md").write_text(RAW_OUTPUT_PRIVESC, encoding="utf-8")
    _mock_vagrant(monkeypatch, CHANGED_TASK_LOG.replace(
        "training_vm : Allow root login (for pentesting exercise)",
        "training_vm : Create a world-writable file in /etc/sudoers.d",
    ), "644\n")

    result = verify_vulnerabilities(tmp_path, role_dir)

    world_writable_finding = next(f for f in result.findings if "world_writable" in f.claim)
    assert world_writable_finding.actual is False
    assert "NOT TRUE" in world_writable_finding.note


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


def test_build_storyline_classifies_ftp_entry_vector():
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim="`anonymous_enable=YES` allows anonymous FTP uploads", directive="anonymous_enable=YES",
                  task_name="Configure vsftpd to allow anonymous uploads"),
    ])

    storyline = build_storyline_from_vulnerabilities(report, spec="Ubuntu FTP server", run_id="20260101-000000")

    assert "FTP" in storyline.title
    assert "vsftpd" in storyline.artefacts[0].content


def test_build_storyline_classifies_unattended_upgrade_entry_vector():
    """Regression test for a real bug: the real Ansible/apt directive is
    `APT::Periodic::Unattended-Upgrade` (singular "Upgrade"), but the
    category regex required the plural "Upgrades" - so a genuinely
    verified, attributed claim about it fell through to the generic
    fallback description instead of the correct "apt" category, on a
    real live openssl-scenario run."""
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim='`APT::Periodic::Unattended-Upgrade "0";` in the `lineinfile` task',
                  directive='APT::Periodic::Unattended-Upgrade "0";',
                  task_name="Disable automatic security updates"),
    ])

    storyline = build_storyline_from_vulnerabilities(report, spec="Ubuntu server", run_id="20260101-000000")

    assert "unpatched" in storyline.title.lower() or "outdated" in storyline.title.lower()
    assert "a misconfiguration this run's own generation claimed to apply" not in storyline.title


def test_build_storyline_unclassified_claim_does_not_duplicate_the_claim_text():
    """Regression test for a real bug: a live vsftpd run's claim didn't
    match any category (before vsftpd was added to _ENTRY_VECTORS above),
    so the generic fallback kicked in - and its description used to embed
    finding.claim verbatim, which is a full sentence, not a short phrase.
    The narrative ended up repeating that entire sentence twice: once from
    the (long) description, once from `specific`. The fallback must never
    embed the claim text - only `specific` should."""
    long_claim = (
        "`some_directive=value` from the config - This is a real vulnerability because "
        "it does something bad in great detail across a full explanatory sentence."
    )
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim=long_claim, directive="some_directive=value", task_name="Do the thing"),
    ])

    storyline = build_storyline_from_vulnerabilities(report, spec="Ubuntu server", run_id="20260101-000000")

    assert storyline.narrative.count("real vulnerability because it does something bad") == 0
    assert storyline.narrative.count("some_directive=value") == 1


def test_build_storyline_narrative_has_a_business_backstory():
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim="`anonymous_enable=YES` allows anonymous FTP uploads", directive="anonymous_enable=YES",
                  task_name="Configure vsftpd to allow anonymous uploads"),
    ])

    storyline = build_storyline_from_vulnerabilities(report, spec="Ubuntu FTP server", run_id="20260101-000000")

    assert "uses this machine to" in storyline.narrative
    assert "FTP" in storyline.narrative or "files" in storyline.narrative


# --- generators.fictional_business_context() ---

def test_fictional_business_context_has_all_fields():
    context = fictional_business_context()

    assert context.name
    assert context.business_type
    assert context.admin_name


# --- scenario_doc.render_scenario_markdown() ---

def test_render_scenario_markdown_includes_title_narrative_and_vulnerability_table():
    from forensicforge.forensics.storyline import Storyline

    storyline = Storyline(id="t", title="Intrusion via X", narrative="Something happened.", base_spec="x", artefacts=[])
    report = VulnerabilityReport(booted=True, destroyed=True, findings=[
        _finding(claim="X was true", actual=True, attribution="changed", note="TRUE and attributed"),
        _finding(claim="Y unclear", verifiable=False, actual=None, attribution=None, note="NOT VERIFIABLE - no match"),
    ])

    markdown = render_scenario_markdown(storyline, report)

    assert markdown.startswith("# Intrusion via X")
    assert "Something happened." in markdown
    assert "## Vulnerabilities" in markdown
    assert "X was true" in markdown
    assert "Confirmed true" in markdown
    assert "Not verifiable" in markdown


def test_render_scenario_markdown_handles_no_findings():
    from forensicforge.forensics.storyline import Storyline

    storyline = Storyline(id="t", title="T", narrative="N", base_spec="x", artefacts=[])
    report = VulnerabilityReport(booted=False, destroyed=False, findings=[])

    markdown = render_scenario_markdown(storyline, report)

    assert "No claimed vulnerabilities were recorded" in markdown
