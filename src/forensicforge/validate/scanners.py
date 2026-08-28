import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from .wsl_bridge import WslUnavailableError, run_posix_tool, to_wsl_path


@dataclass
class Finding:
    rule_id: str
    message: str
    severity: str | None = None
    file: str | None = None
    line: int | None = None


@dataclass
class ScanResult:
    tool: str
    passed: bool | None  # None = the tool itself could not be run
    findings: list[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "passed": self.passed,
            "findings": [vars(f) for f in self.findings],
            "summary": self.summary,
            "error": self.error,
        }


def run_checkov(target_dir: Path) -> ScanResult:
    """Run Checkov's Ansible framework against a generated role directory.

    Runs natively on Windows (pure Python, no ansible-core dependency) -
    unlike ansible-lint and Molecule, no WSL bridge needed here.
    """
    cmd = [
        sys.executable, "-m", "checkov.main",
        "-d", str(target_dir),
        "--framework", "ansible",
        "--output", "json",
        "--compact",
        "--quiet",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ScanResult(tool="checkov", passed=None, error=str(exc))

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return ScanResult(
            tool="checkov", passed=None,
            error=f"could not parse checkov output: {exc}\n{proc.stdout[:2000]}",
        )

    # Checkov returns a flat summary dict when zero resources match its
    # (narrow) Ansible check set, or a {check_type, results, summary}
    # structure when there's something to report. Handle both.
    summary = data.get("summary", data)
    failed_checks = data.get("results", {}).get("failed_checks", [])

    findings = [
        Finding(
            rule_id=check.get("check_id", "unknown"),
            message=check.get("check_name", ""),
            severity=check.get("severity"),
            file=check.get("file_path"),
            line=(check.get("file_line_range") or [None])[0],
        )
        for check in failed_checks
    ]

    return ScanResult(
        tool="checkov",
        passed=summary.get("failed", 0) == 0,
        findings=findings,
        summary=summary,
    )


def run_ansible_lint(role_dir: Path) -> ScanResult:
    """Run ansible-lint against a generated role directory.

    ansible-lint depends on ansible-core, which needs POSIX-only stdlib
    modules not present on Windows - see wsl_bridge.py and
    docs/METHODOLOGY.md (week 4). On Windows this runs via WSL (installed
    there separately from this project's venv - scripts/check_wsl_tools.py);
    on other platforms (e.g. Linux CI runners) it runs directly, since
    ansible-core has nothing to route around there.
    """
    target = to_wsl_path(role_dir) if config.RUNS_ON_WINDOWS else str(role_dir)
    try:
        proc = run_posix_tool(f"ansible-lint --format json {target}")
    except WslUnavailableError as exc:
        return ScanResult(tool="ansible-lint", passed=None, error=str(exc))

    if proc.returncode == 127:
        return ScanResult(
            tool="ansible-lint", passed=None,
            error=(
                "ansible-lint is not installed. On Windows, install it inside "
                "WSL (separate from this project's venv): "
                "wsl -- pip install --user ansible-lint. Elsewhere: "
                "pip install ansible-lint."
            ),
        )

    try:
        issues = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return ScanResult(
            tool="ansible-lint", passed=None,
            error=f"could not parse ansible-lint output: {exc}\n{proc.stdout[:2000]}\n{proc.stderr[:2000]}",
        )

    findings = [
        Finding(
            rule_id=issue.get("check_name", "unknown"),
            message=issue.get("description", ""),
            severity=issue.get("severity"),
            file=(issue.get("location") or {}).get("path"),
            line=_first_line(issue.get("location", {})),
        )
        for issue in issues
    ]

    # ansible-lint's own exit code (0 = clean) is the authoritative
    # pass/fail signal - it accounts for profiles/ignored rules in a way
    # the raw finding count alone doesn't.
    return ScanResult(
        tool="ansible-lint",
        passed=proc.returncode == 0,
        findings=findings,
        summary={"issue_count": len(findings), "exit_code": proc.returncode},
    )


def _first_line(location: dict) -> int | None:
    positions = location.get("positions", {}).get("begin", {})
    if "line" in positions:
        return positions["line"]
    return location.get("lines", {}).get("begin")
