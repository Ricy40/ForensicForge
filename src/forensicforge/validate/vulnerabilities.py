import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .. import config
from .test_deploy import DerivedCheck, test_deploy as run_test_deploy

# The RAG prompt (prompts.py RAG_SYSTEM_PROMPT) asks the LLM for a numbered
# or bulleted "Applied misconfigurations" section, one claim per line,
# ideally with the exact directive/line quoted in backticks. Neither the
# header's exact punctuation nor the list marker (digit vs "-") is fully
# consistent across real generations - confirmed by running the same spec
# twice and getting "**Applied misconfigurations:**" once and
# "**Applied misconfigurations**:" the next - so both are tolerated here.
_SECTION_HEADER = re.compile(r"applied misconfigurations[:*]*\s*\n", re.IGNORECASE)
_CLAIM_LINE = re.compile(r"^\s*(?:\d+\.|-)\s*(.+)$")
_BACKTICK = re.compile(r"`([^`]+)`")


@dataclass
class ClaimedVulnerability:
    """One line from the LLM's own 'Applied misconfigurations' section."""
    text: str
    directives: list[str] = field(default_factory=list)  # backtick-quoted values, if any


@dataclass
class VulnerabilityFinding:
    """One claim's outcome: claimed vs. actually true on a live VM.

    `actual`/`attribution`/`output` stay None when `verifiable` is False -
    there is deliberately no live check to run for those, rather than a
    silently-skipped or fabricated result. See docs/METHODOLOGY.md (week 6).
    """
    claim: str
    directive: str | None
    verifiable: bool
    task_name: str | None = None
    actual: bool | None = None
    attribution: str | None = None
    output: str | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return dict(vars(self))


@dataclass
class VulnerabilityReport:
    booted: bool
    destroyed: bool
    findings: list[VulnerabilityFinding] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "booted": self.booted,
            "destroyed": self.destroyed,
            "findings": [f.to_dict() for f in self.findings],
            "error": self.error,
        }


def parse_applied_misconfigurations(raw_output: str) -> list[ClaimedVulnerability]:
    """Extract the RAG prompt's 'Applied misconfigurations' claims from raw
    LLM output into a structured (but still LLM-authored, still
    free-text-per-claim) list.

    Directives come from backtick-quoted spans within each claim line -
    the prompt asks for this (see prompts.py), but the LLM doesn't always
    comply, so a claim can legitimately end up with zero directives. That
    is not a parse failure: it just means the claim has nothing this
    module can match to a checkable task later (see match logic below).
    """
    header = _SECTION_HEADER.search(raw_output)
    if not header:
        return []

    claims: list[ClaimedVulnerability] = []
    for line in raw_output[header.end():].splitlines():
        stripped = line.strip().strip("*").strip()
        if not stripped:
            continue
        matched = _CLAIM_LINE.match(stripped)
        text = (matched.group(1) if matched else stripped).strip()
        if not text:
            continue
        directives = [d.strip() for d in _BACKTICK.findall(text) if d.strip()]
        claims.append(ClaimedVulnerability(text=text, directives=directives))
    return claims


def _lineinfile_tasks(role_dir: Path) -> list[dict]:
    tasks_file = role_dir / "tasks" / "main.yml"
    tasks = yaml.safe_load(tasks_file.read_text(encoding="utf-8")) or []
    return [t for t in tasks if isinstance(t.get("ansible.builtin.lineinfile"), dict)]


# ansible.builtin.file (path:) and ansible.builtin.copy (dest:) both take a
# mode: permission string - a second, distinct kind of individually-
# checkable claim alongside lineinfile's, added after two of seven
# real evaluation-round specs (privilege escalation, SUID/sudoers
# world-writable permissions) came back entirely unverifiable: every
# claim they produced was a mode: value, none a lineinfile line, so the
# lineinfile-only mechanism found nothing checkable in either run at all.
# Unlike the mysql_user case (also lineinfile-only-unverifiable, see
# docs/METHODOLOGY.md's database-class section) a permission mode is
# safe and simple to check live - a single `stat`, no live service
# connection or credential-chain complexity - so this was worth adding
# rather than recording as another limitation.
_MODE_MODULES = ("ansible.builtin.file", "ansible.builtin.copy")


def _mode_tasks(role_dir: Path) -> list[dict]:
    tasks_file = role_dir / "tasks" / "main.yml"
    tasks = yaml.safe_load(tasks_file.read_text(encoding="utf-8")) or []
    result = []
    for task in tasks:
        for module in _MODE_MODULES:
            args = task.get(module)
            if isinstance(args, dict) and "mode" in args and (args.get("path") or args.get("dest")):
                result.append(task)
                break
    return result


def _task_mode_and_path(task: dict) -> tuple[str, str] | None:
    for module in _MODE_MODULES:
        args = task.get(module)
        if isinstance(args, dict) and "mode" in args:
            path = args.get("path") or args.get("dest")
            if path:
                return str(args["mode"]), str(path)
    return None


def _normalize_octal_mode(mode: str) -> str | None:
    """'0777' / '04755' -> '777' / '4755' - the exact form `stat -c %a`
    prints (no leading zero; special bits collapse naturally when
    present). Comparing as an integer rather than a string sidesteps
    every padding variant a claim or a task might use."""
    try:
        return oct(int(str(mode), 8))[2:]
    except (TypeError, ValueError):
        return None


def _match_mode_claim(claim: ClaimedVulnerability, mode_tasks: list[dict]) -> tuple[dict | None, str | None]:
    """Find the file/copy task (if any) a claim's permission mode refers
    to - the same "does the claim's own text contain what the task
    actually did" principle as _match_claim(), just against a mode value
    instead of a lineinfile line. Tried against both the task's raw mode
    string (e.g. '04755') and its normalized form ('4755'), since a claim
    might quote either.
    """
    for task in mode_tasks:
        result = _task_mode_and_path(task)
        if result is None:
            continue
        mode, _path = result
        normalized = _normalize_octal_mode(mode)
        if mode in claim.text or (normalized and normalized in claim.text):
            return task, mode
    return None, None


def _match_claim(claim: ClaimedVulnerability, lineinfile_tasks: list[dict]) -> tuple[dict | None, str | None]:
    """Find the lineinfile task (if any) a claim refers to.

    Matches by checking whether a task's own `line:` value - the literal
    text the task actually writes - appears verbatim anywhere in the
    claim's full text, rather than only within backtick-quoted spans.
    The prompt asks the LLM to backtick-quote the exact directive per
    claim (see prompts.py), but real generations don't consistently put
    the *directive* there - one live run wrapped the directive in
    **bold** instead and used its only backtick span for an unrelated
    source citation (`` `source: misconfigurations/weak_ssh_root_login.md` ``),
    which made every claim in that run unmatchable under backtick-only
    matching even though the directive text was sitting right there in
    the claim. Searching the whole claim text is robust to wherever the
    LLM chooses to put emphasis formatting. Only lineinfile is covered:
    it's the only module in the knowledge corpus (and every generated
    role seen so far) that makes a single, individually-checkable claim
    per task - see derive_checks_from_role()'s own docstring in
    test_deploy.py for the same reasoning. A claim that matches no
    lineinfile task's line is reported as unverifiable, not silently
    dropped or guessed at.
    """
    for task in lineinfile_tasks:
        line = str(task["ansible.builtin.lineinfile"].get("line", ""))
        normalized_line = " ".join(line.split())
        if normalized_line and normalized_line in claim.text:
            return task, normalized_line
    return None, None


def verify_vulnerabilities(run_dir: Path, role_dir: Path) -> VulnerabilityReport:
    """Check every claimed misconfiguration for `run_dir` against a real,
    booted VM: claimed vs. actually true, and (via test_deploy.py's
    existing attribution parsing) whether the role itself caused it or it
    was already true before this run applied anything.

    Generalizes the ad-hoc manual SSH checks from week 3/4 into something
    spec-driven: claims come from whatever this run's own generation
    output said it applied (generation.md), not a hardcoded field list -
    see docs/METHODOLOGY.md (week 6).

    Boots and destroys its own VM via test_deploy() (there's no VM left
    running from a prior `test-deploy` call to reuse - that command
    always destroys too), so this is a separate live run, not a re-read
    of another command's result.
    """
    generation_path = run_dir / config.GENERATION_FILENAME
    if not generation_path.exists():
        raise FileNotFoundError(
            f"No {config.GENERATION_FILENAME} recorded for {run_dir} - this run was "
            "provisioned before generation output started being persisted "
            "(see docs/METHODOLOGY.md, week 6). Re-run `provision` to get a run "
            "verify-vulnerabilities can check."
        )

    raw_output = generation_path.read_text(encoding="utf-8")
    claims = parse_applied_misconfigurations(raw_output)
    lineinfile_tasks = _lineinfile_tasks(role_dir)
    mode_tasks = _mode_tasks(role_dir)

    findings: list[VulnerabilityFinding] = []
    checks: list[DerivedCheck] = []
    check_by_task_name: dict[str, VulnerabilityFinding] = {}

    for claim in claims:
        task, directive = _match_claim(claim, lineinfile_tasks)
        if task is not None:
            task_name = str(task.get("name", ""))
            module_args = task["ansible.builtin.lineinfile"]
            path = module_args.get("path")
            line = str(module_args.get("line", ""))
            escaped = line.replace("'", "'\\''")
            check = DerivedCheck(
                command=f"sudo grep -F -- '{escaped}' {path}",
                expected=line,
                task_name=task_name,
                category="vulnerability",
            )
            checks.append(check)
            finding = VulnerabilityFinding(claim=claim.text, directive=directive, verifiable=True, task_name=task_name)
            check_by_task_name[task_name] = finding
            findings.append(finding)
            continue

        mode_task, mode = _match_mode_claim(claim, mode_tasks)
        if mode_task is not None:
            task_name = str(mode_task.get("name", ""))
            _, path = _task_mode_and_path(mode_task)
            normalized = _normalize_octal_mode(mode)
            check = DerivedCheck(
                command=f"sudo stat -c %a {path}",
                expected=normalized,
                task_name=task_name,
                category="vulnerability",
            )
            checks.append(check)
            finding = VulnerabilityFinding(claim=claim.text, directive=mode, verifiable=True, task_name=task_name)
            check_by_task_name[task_name] = finding
            findings.append(finding)
            continue

        reason = (
            "no ansible.builtin.lineinfile task writes a line, and no "
            "ansible.builtin.file/copy task sets a mode:, that appears anywhere in "
            "this claim's text"
        )
        findings.append(VulnerabilityFinding(
            claim=claim.text,
            directive=claim.directives[0] if claim.directives else None,
            verifiable=False,
            note=f"NOT VERIFIABLE - {reason}",
        ))

    if not checks:
        return VulnerabilityReport(
            booted=False, destroyed=False, findings=findings,
            error=None if not findings else "no claims matched a checkable task - nothing to boot for",
        )

    result = run_test_deploy(run_dir, checks)

    results_by_task = {c.task_name: c for c in result.checks}
    for task_name, finding in check_by_task_name.items():
        check_result = results_by_task.get(task_name)
        if check_result is None:
            finding.note = "the VM never reached this check (boot likely failed before checks ran)"
            continue
        finding.actual = check_result.matched
        finding.attribution = check_result.attribution
        finding.output = check_result.output
        if check_result.matched is None:
            finding.note = (
                "COULD NOT VERIFY - the check itself could not connect over SSH "
                "(connection failed), even though the VM booted and Ansible ran. A task "
                "that changes SSH's own listening port and then restarts sshd is a "
                "likely cause (this tool's SSH access assumes port 22 and has no way to "
                "discover a new one) - the claimed change may or may not be "
                "true, this run just couldn't reach the guest to check"
            )
        elif not check_result.matched:
            finding.note = "NOT TRUE on the live VM - the claimed misconfiguration was not applied"
        elif check_result.attribution == "changed":
            finding.note = "TRUE on the live VM, and Ansible's output confirms this run's role caused it"
        elif check_result.attribution == "ok":
            finding.note = (
                "TRUE on the live VM, but the task reported 'ok' not 'changed' - it was "
                "already true before this run applied anything, NOT attributable to this role "
            )
        elif check_result.attribution in ("skipping", "failed", "fatal"):
            finding.note = f"TRUE on the live VM, but the claiming task itself reported '{check_result.attribution}'"
        else:
            finding.note = "TRUE on the live VM; attribution unknown (task not found in provisioner output)"

    return VulnerabilityReport(booted=result.booted, destroyed=result.destroyed, findings=findings, error=result.error)
