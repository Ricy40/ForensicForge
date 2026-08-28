import json
import subprocess
import sys

import pytest

from forensicforge.validate.hcl_check import validate_packer_template
from forensicforge.validate.report import aggregate_reports, load_report, write_report
from forensicforge.validate.scanners import run_ansible_lint, run_checkov
from forensicforge.validate.test_deploy import derive_checks_from_role, parse_task_attribution
from forensicforge.validate.wsl_bridge import WslUnavailableError

VALID_PACKER = """\
source "virtualbox-iso" "example" {
  vm_name = "example"
}

build {
  sources = ["source.virtualbox-iso.example"]
}
"""

MALFORMED_PACKER = """\
source "example" "bad" {
  this is not valid hcl {{{
"""

INSECURE_TASK = """\
- name: Download something insecurely
  ansible.builtin.get_url:
    url: https://example.com/file.tar.gz
    dest: /tmp/file.tar.gz
    validate_certs: false
"""

BENIGN_TASK = """\
- name: Install OpenSSH server
  ansible.builtin.package:
    name: openssh-server
    state: present
"""

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


def _write_role_tasks(tmp_path, content: str):
    role_dir = tmp_path / "role"
    (role_dir / "tasks").mkdir(parents=True)
    (role_dir / "tasks" / "main.yml").write_text(content, encoding="utf-8")
    return role_dir


# --- hcl_check.py ---

def test_validate_packer_template_accepts_valid_hcl(tmp_path):
    path = tmp_path / "good.pkr.hcl"
    path.write_text(VALID_PACKER, encoding="utf-8")

    result = validate_packer_template(path)

    assert result.passed is True
    assert result.findings == []


def test_validate_packer_template_rejects_malformed_hcl(tmp_path):
    path = tmp_path / "bad.pkr.hcl"
    path.write_text(MALFORMED_PACKER, encoding="utf-8")

    result = validate_packer_template(path)

    assert result.passed is False
    assert result.findings[0].rule_id == "hcl-parse-error"


def test_validate_packer_template_flags_missing_blocks(tmp_path):
    path = tmp_path / "incomplete.pkr.hcl"
    path.write_text('variable "x" {\n  default = "y"\n}\n', encoding="utf-8")

    result = validate_packer_template(path)

    assert result.passed is False
    assert {f.rule_id for f in result.findings} == {"missing-block"}


# --- scanners.py: run_checkov (native, no WSL needed) ---

def test_run_checkov_flags_known_ansible_issue(tmp_path):
    role_dir = _write_role_tasks(tmp_path, INSECURE_TASK)

    result = run_checkov(role_dir)

    assert result.passed is False
    assert any(f.rule_id == "CKV_ANSIBLE_2" for f in result.findings)


def test_run_checkov_passes_when_no_matching_resources(tmp_path):
    role_dir = _write_role_tasks(tmp_path, BENIGN_TASK)

    result = run_checkov(role_dir)

    assert result.passed is True
    assert result.findings == []


# --- scanners.py: run_ansible_lint (mocked WSL bridge) ---

def test_run_ansible_lint_reports_unavailable_when_wsl_unreachable(tmp_path, monkeypatch):
    def fake_run_posix_tool(*args, **kwargs):
        raise WslUnavailableError("WSL did not respond")

    monkeypatch.setattr("forensicforge.validate.scanners.run_posix_tool", fake_run_posix_tool)

    result = run_ansible_lint(tmp_path)

    assert result.passed is None
    assert "WSL did not respond" in result.error


def test_run_ansible_lint_parses_codeclimate_json(tmp_path, monkeypatch):
    issues = [
        {
            "check_name": "risky-file-permissions",
            "description": "File permissions unset or incorrect",
            "severity": "minor",
            "location": {"path": "tasks/main.yml", "lines": {"begin": 3}},
        }
    ]

    def fake_run_posix_tool(*args, **kwargs):
        return subprocess.CompletedProcess(args=[], returncode=2, stdout=json.dumps(issues), stderr="")

    monkeypatch.setattr("forensicforge.validate.scanners.run_posix_tool", fake_run_posix_tool)

    result = run_ansible_lint(tmp_path)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "risky-file-permissions"
    assert result.findings[0].line == 3


def test_run_ansible_lint_passes_on_clean_exit(tmp_path, monkeypatch):
    def fake_run_posix_tool(*args, **kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr("forensicforge.validate.scanners.run_posix_tool", fake_run_posix_tool)

    result = run_ansible_lint(tmp_path)

    assert result.passed is True
    assert result.findings == []


# --- test_deploy.py: derive_checks_from_role (native) ---

def test_derive_checks_from_role_extracts_lineinfile_tasks(tmp_path):
    role_dir = _write_role_tasks(tmp_path, LINEINFILE_TASKS)

    checks = derive_checks_from_role(role_dir)

    assert len(checks) == 1
    assert checks[0].command == "sudo grep -F -- 'PermitRootLogin yes' /etc/ssh/sshd_config"
    assert checks[0].expected == "PermitRootLogin yes"
    assert checks[0].task_name == "Allow root login (for pentesting exercise)"


def test_derive_checks_from_role_returns_empty_for_no_lineinfile_tasks(tmp_path):
    role_dir = _write_role_tasks(tmp_path, BENIGN_TASK)

    assert derive_checks_from_role(role_dir) == []


# --- test_deploy.py: parse_task_attribution (native, no VM needed) ---

CHANGED_TASK_LOG = """\
TASK [training_vm : Allow root login (for pentesting exercise)] **************
changed: [default]

TASK [training_vm : Install OpenSSH server] ***********************************
ok: [default]
"""


def test_parse_task_attribution_reads_changed_and_ok():
    attribution = parse_task_attribution(CHANGED_TASK_LOG)

    assert attribution == {
        "training_vm : Allow root login (for pentesting exercise)": "changed",
        "training_vm : Install OpenSSH server": "ok",
    }


def test_parse_task_attribution_empty_for_no_task_headers():
    assert parse_task_attribution("just some unrelated log text\nwith no TASK headers\n") == {}


def test_test_deploy_attribution_lookup_matches_role_prefixed_task_name(tmp_path, monkeypatch):
    """Full test_deploy() flow with vagrant mocked, checking attribution wiring end-to-end.

    Imports the test_deploy *module* via sys.modules rather than
    `import forensicforge.validate.test_deploy as td`: the package's
    __init__.py does `from .test_deploy import test_deploy` (the
    function), which rebinds the `test_deploy` attribute on the
    `forensicforge.validate` package to the function, shadowing the
    submodule of the same name for ordinary dotted-attribute access.
    sys.modules is unaffected by that and always holds the real module.
    """
    td = sys.modules["forensicforge.validate.test_deploy"]

    role_dir = _write_role_tasks(tmp_path, LINEINFILE_TASKS)
    checks = td.derive_checks_from_role(role_dir)

    class FakeVagrant:
        def __init__(self, root, out_cm, err_cm, **kwargs):
            self._out_cm = out_cm
            with out_cm() as fh:
                fh.write(CHANGED_TASK_LOG)

        def up(self, provider=None, provision=None):
            pass

        def ssh(self, command):
            return "PermitRootLogin yes\n"

        def destroy(self):
            pass

    monkeypatch.setattr(td.vagrant, "Vagrant", FakeVagrant)

    result = td.test_deploy(tmp_path, checks)

    assert result.booted is True
    assert result.config_verified is True
    assert result.checks[0].attribution == "changed"


def test_test_deploy_destroys_even_when_up_fails(tmp_path, monkeypatch):
    """Regression test: a real run hit this - a provisioner step failed
    partway through `vagrant up` (after the VM was already created), and
    the pre-fix version of test_deploy() only ever called destroy() if
    `up()` succeeded, leaving a real VM running with a lock that then
    blocked every retry. destroy() must always be attempted.
    """
    td = sys.modules["forensicforge.validate.test_deploy"]
    destroy_called = []

    class FakeVagrant:
        def __init__(self, root, out_cm, err_cm, **kwargs):
            pass

        def up(self, provider=None, provision=None):
            raise subprocess.CalledProcessError(1, ["vagrant", "up"])

        def destroy(self):
            destroy_called.append(True)

    monkeypatch.setattr(td.vagrant, "Vagrant", FakeVagrant)

    result = td.test_deploy(tmp_path, [])

    assert result.booted is False
    assert result.destroyed is True
    assert destroy_called == [True]


# --- report.py ---

def test_write_and_load_report_round_trip(tmp_path):
    report = {"run_id": "abc", "scans": {}, "molecule": None, "test_deploy": None}

    write_report(report, tmp_path)
    loaded = load_report(tmp_path)

    assert loaded == report


def test_aggregate_reports_computes_pass_rates(tmp_path):
    def make_report(run_id: str, checkov_passed: bool, test_deploy_booted: bool | None):
        run_dir = tmp_path / run_id
        run_dir.mkdir()
        write_report(
            {
                "run_id": run_id,
                "scans": {
                    "checkov": {"passed": checkov_passed},
                    "ansible_lint": {"passed": None},
                },
                "molecule": {"passed": None},
                "test_deploy": (
                    {"booted": test_deploy_booted, "config_verified": test_deploy_booted}
                    if test_deploy_booted is not None else None
                ),
            },
            run_dir,
        )

    make_report("run1", checkov_passed=True, test_deploy_booted=True)
    make_report("run2", checkov_passed=False, test_deploy_booted=False)
    make_report("run3", checkov_passed=True, test_deploy_booted=None)

    summary = aggregate_reports(tmp_path)

    assert summary["total_runs"] == 3
    assert summary["checkov"] == {"passed": 2, "applicable": 3, "rate": pytest.approx(2 / 3)}
    assert summary["ansible_lint"] == {"passed": 0, "applicable": 0, "rate": None}
    assert summary["test_deploy_booted"] == {"passed": 1, "applicable": 2, "rate": pytest.approx(0.5)}
