import contextlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import vagrant
import yaml

from .. import config

LOG_FILENAME = "vagrant.log"
_ERROR_TAIL_CHARS = 4000

# Ansible's default console callback prints a "TASK [<name>]" header
# followed by a per-host result line (ok/changed/skipping/failed/fatal).
# Role-sourced tasks get a "<role> : <task name>" header (playbook.yml
# references the role plainly - `roles: [training_vm]`, no namespace).
# This is what closes the attribution gap: whether a task actually
# changed the target file, versus finding it already correct, is only
# observable here - not from the role's YAML, not from the file's final
# state. See docs/METHODOLOGY.md (week 5).
_TASK_HEADER = re.compile(r"^TASK \[(?P<name>.*)\] \*+$")
_STATUS_LINE = re.compile(r"^(ok|changed|skipping|failed|fatal): ")


@dataclass
class CheckResult:
    command: str
    expected: str
    output: str
    matched: bool
    task_name: str | None = None
    # "changed" = this run's role application caused the config; "ok" =
    # the task ran but the file already matched (NOT attributable to this
    # run - the week 3 PermitRootLogin scenario exactly); "skipping" /
    # "failed" / "fatal" = task didn't apply cleanly; None = task not
    # found in the captured output at all (e.g. Ansible itself never ran).
    attribution: str | None = None
    # "config" (default) for the scenario role's own checks, "artefact"
    # for forensic evidence checks (forensics/planter.py sets this) -
    # lets report.py's aggregate_reports() compute an artefact-planting
    # rate separately from the ordinary config-verification rate, without
    # this module needing to know anything about storylines at all.
    category: str = "config"


@dataclass
class TestDeployResult:
    booted: bool
    destroyed: bool
    config_verified: bool | None  # None = never reached the check step (boot failed), or no config checks given
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    artefacts_verified: bool | None = None  # None = no artefact-category checks given (no storyline)

    def to_dict(self) -> dict:
        return {
            "booted": self.booted,
            "destroyed": self.destroyed,
            "config_verified": self.config_verified,
            "artefacts_verified": self.artefacts_verified,
            "checks": [vars(c) for c in self.checks],
            "error": self.error,
        }


@dataclass
class DerivedCheck:
    command: str
    expected: str
    task_name: str
    category: str = "config"


def derive_checks_from_role(role_dir: Path) -> list[DerivedCheck]:
    """Derive smoke checks from lineinfile tasks, one per task.

    Mirrors the manual verification from week 3 - grep the directive a
    task claims to have applied out of the file it claims to have applied
    it to - but generated automatically from whatever the role actually
    contains, rather than hardcoded to the SSH example. Only lineinfile
    tasks are covered: it's the module every corpus example and every
    generated role so far uses to make its claimed change, and the one
    week 3's own verification exercised.

    Each check carries the task's own `name:` field, needed to look its
    result up in parse_task_attribution()'s output afterward.
    """
    tasks_file = role_dir / "tasks" / "main.yml"
    tasks = yaml.safe_load(tasks_file.read_text(encoding="utf-8")) or []

    checks = []
    for task in tasks:
        module_args = task.get("ansible.builtin.lineinfile")
        if not isinstance(module_args, dict):
            continue
        path = module_args.get("path")
        line = module_args.get("line")
        if not path or not line:
            continue
        escaped = str(line).replace("'", "'\\''")
        command = f"sudo grep -F -- '{escaped}' {path}"
        checks.append(DerivedCheck(command=command, expected=str(line), task_name=str(task.get("name", ""))))
    return checks


def parse_task_attribution(log_text: str) -> dict[str, str]:
    """Map each Ansible TASK name (as printed) to its result status.

    Reads the ansible_local provisioner's console output as captured in
    vagrant.log during `vagrant up` - already being captured for error
    reporting (see test_deploy() below); this just parses it. No JSON
    callback plugin or extra verbosity flag was needed, since the default
    callback already prints exactly the ok/changed distinction attribution
    needs.
    """
    lines = log_text.splitlines()
    attribution: dict[str, str] = {}
    current_task: str | None = None
    for line in lines:
        stripped = line.strip()
        header = _TASK_HEADER.match(stripped)
        if header:
            current_task = header.group("name")
            continue
        if current_task is not None:
            status = _STATUS_LINE.match(stripped)
            if status:
                attribution[current_task] = status.group(1)
                current_task = None
    return attribution


def _lookup_attribution(attribution: dict[str, str], task_name: str) -> str | None:
    if not task_name:
        return None
    for full_name, status in attribution.items():
        if full_name == task_name or full_name.endswith(f": {task_name}"):
            return status
    return None


def test_deploy(
    run_dir: Path,
    checks: list[DerivedCheck],
    provider: str = config.VAGRANT_PROVIDER,
) -> TestDeployResult:
    """Boot the generated VM, run smoke checks over SSH, then always destroy it.

    Replaces week 3's manual `vagrant up` / `vagrant ssh` / (never
    destroyed) cycle with a scripted one. Destroy always runs (via
    `finally`) regardless of whether boot or checks succeeded, so a
    failed run doesn't leave a VM behind.

    `vagrant up`/`destroy` go through python-vagrant's non-capturing path
    (subprocess.check_call under the hood, not check_output) - their
    CalledProcessError never carries stdout/stderr, unlike `.ssh()`'s.
    Both are redirected to run_dir/vagrant.log instead, which is what
    gets read back into `error` on failure - without this, a boot
    failure surfaces as a bare "exit status 1" with no way to tell why.
    The log is truncated fresh at the start of each call (not appended
    across runs) so parse_task_attribution() only sees this run's output.
    """
    log_path = run_dir / LOG_FILENAME
    log_path.write_text("", encoding="utf-8")

    @contextlib.contextmanager
    def _log_cm():
        with log_path.open("a", encoding="utf-8") as fh:
            yield fh

    v = vagrant.Vagrant(root=str(run_dir), out_cm=_log_cm, err_cm=_log_cm)
    result = TestDeployResult(booted=False, destroyed=False, config_verified=None)

    try:
        try:
            # provision=True forces Ansible to actually run every time,
            # rather than Vagrant's own "machine already provisioned,
            # skipping" default - confirmed by finding exactly that
            # message in an earlier run's vagrant.log. Without this, a
            # machine left over from an earlier attempt could report
            # checks passing without this run's role having done
            # anything at all - the general form of the same attribution
            # problem this feature closes.
            v.up(provider=provider, provision=True)
            result.booted = True
        except subprocess.CalledProcessError:
            result.error = f"vagrant up failed - see {log_path}:\n{_tail(log_path)}"
            # This `return` skips straight to `finally` below, which
            # still runs `destroy()` regardless - `up` can fail after a
            # VM was already created (a provisioner step failing partway
            # through, as opposed to the VM never coming up at all), and
            # the previous version of this function only reached destroy
            # if `up` succeeded, so a mid-`up` failure left a real VM
            # behind with a lock that then blocked every retry. Confirmed
            # by hitting exactly this: a provisioner permissions error
            # failed `up` after the VM had already booted. See
            # docs/METHODOLOGY.md (week 5).
            return result

        attribution = parse_task_attribution(_read_log(log_path))

        for check in checks:
            try:
                output = v.ssh(command=check.command)
                matched = check.expected in output
            except subprocess.CalledProcessError as exc:
                output = _proc_error_text(exc)
                matched = False
            result.checks.append(
                CheckResult(
                    command=check.command,
                    expected=check.expected,
                    output=output.strip(),
                    matched=matched,
                    task_name=check.task_name,
                    attribution=_lookup_attribution(attribution, check.task_name),
                    category=check.category,
                )
            )

        # Tracked separately per category rather than one combined flag:
        # a run mixing scenario-config checks and forensic-artefact
        # checks (test-deploy --storyline) needs to report "did the
        # baseline config land" and "did the evidence get planted" as
        # independent answers, not blended into one - see
        # docs/METHODOLOGY.md (week 5) and report.py's aggregate_reports().
        config_checks = [c for c in result.checks if c.category == "config"]
        artefact_checks = [c for c in result.checks if c.category == "artefact"]
        result.config_verified = all(c.matched for c in config_checks) if config_checks else None
        result.artefacts_verified = all(c.matched for c in artefact_checks) if artefact_checks else None
    finally:
        try:
            v.destroy()
            result.destroyed = True
        except subprocess.CalledProcessError:
            note = f"vagrant destroy failed - see {log_path}:\n{_tail(log_path)}"
            result.error = f"{result.error}; {note}" if result.error else note

    return result


def _proc_error_text(exc: subprocess.CalledProcessError) -> str:
    output = exc.output
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    return (output or "").strip() or str(exc)


def _read_log(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8", errors="replace")


def _tail(log_path: Path, max_chars: int = _ERROR_TAIL_CHARS) -> str:
    text = _read_log(log_path)
    return text[-max_chars:] if text else "(no log written)"
