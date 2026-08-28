import contextlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import vagrant
import yaml

from .. import config

LOG_FILENAME = "vagrant.log"
_ERROR_TAIL_CHARS = 4000


@dataclass
class CheckResult:
    command: str
    expected: str
    output: str
    matched: bool


@dataclass
class TestDeployResult:
    booted: bool
    destroyed: bool
    config_verified: bool | None  # None = never reached the check step (boot failed)
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "booted": self.booted,
            "destroyed": self.destroyed,
            "config_verified": self.config_verified,
            "checks": [vars(c) for c in self.checks],
            "error": self.error,
        }


def derive_checks_from_role(role_dir: Path) -> list[tuple[str, str]]:
    """Derive (command, expected_line) smoke checks from lineinfile tasks.

    Mirrors the manual verification from week 3 - grep the directive a
    task claims to have applied out of the file it claims to have applied
    it to - but generated automatically from whatever the role actually
    contains, rather than hardcoded to the SSH example. Only lineinfile
    tasks are covered: it's the module every corpus example and every
    generated role so far uses to make its claimed change, and the one
    week 3's own verification exercised.
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
        checks.append((command, str(line)))
    return checks


def test_deploy(
    run_dir: Path,
    checks: list[tuple[str, str]],
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
    """
    log_path = run_dir / LOG_FILENAME

    @contextlib.contextmanager
    def _log_cm():
        with log_path.open("a", encoding="utf-8") as fh:
            yield fh

    v = vagrant.Vagrant(root=str(run_dir), out_cm=_log_cm, err_cm=_log_cm)
    result = TestDeployResult(booted=False, destroyed=False, config_verified=None)

    try:
        v.up(provider=provider)
        result.booted = True
    except subprocess.CalledProcessError:
        result.error = f"vagrant up failed - see {log_path}:\n{_tail(log_path)}"
        return result

    try:
        all_matched = True
        for command, expected in checks:
            try:
                output = v.ssh(command=command)
                matched = expected in output
            except subprocess.CalledProcessError as exc:
                output = _proc_error_text(exc)
                matched = False
            result.checks.append(
                CheckResult(command=command, expected=expected, output=output.strip(), matched=matched)
            )
            all_matched = all_matched and matched
        result.config_verified = all_matched if checks else None
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


def _tail(log_path: Path, max_chars: int = _ERROR_TAIL_CHARS) -> str:
    if not log_path.exists():
        return "(no log written)"
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]
