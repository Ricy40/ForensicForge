import datetime
import json
from pathlib import Path

from .. import config
from . import scanners
from .molecule_runner import run_molecule
from .test_deploy import TestDeployResult


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def build_validation_report(run_id: str, role_dir: Path, spec: str | None = None) -> dict:
    """Run checkov, ansible-lint, and Molecule against a generated role.

    This is the CI-safe half of validation - no VM is booted. See
    test_deploy.py and docs/METHODOLOGY.md (week 4) for the boot/verify/
    destroy half, which stays local-only.
    """
    checkov_result = scanners.run_checkov(role_dir)
    ansible_lint_result = scanners.run_ansible_lint(role_dir)
    molecule_result = run_molecule(role_dir)

    return {
        "run_id": run_id,
        "spec": spec,
        "generated_at": _now_iso(),
        "scans": {
            "checkov": checkov_result.to_dict(),
            "ansible_lint": ansible_lint_result.to_dict(),
        },
        "molecule": molecule_result.to_dict(),
        "test_deploy": None,
    }


def add_test_deploy_result(report: dict, result: TestDeployResult) -> dict:
    """Merge a TestDeployResult into an existing report dict, in place."""
    report["test_deploy"] = result.to_dict()
    return report


def write_report(report: dict, run_dir: Path) -> Path:
    path = run_dir / config.REPORT_FILENAME
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def load_report(run_dir: Path) -> dict:
    path = run_dir / config.REPORT_FILENAME
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate_reports(generated_dir: Path = config.GENERATED_DIR) -> dict:
    """Summarize report.json files across every run under generated_dir.

    Feeds the dissertation's evaluation chapter: a deployability/
    compliance rate the way the DPIaC-Eval benchmark structures results,
    computed once there are enough runs to make a rate meaningful rather
    than reading one report.json at a time.
    """
    reports = []
    for path in sorted(generated_dir.glob("*/" + config.REPORT_FILENAME)):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    total = len(reports)

    def _rate(predicate) -> dict:
        applicable = [r for r in reports if predicate(r) is not None]
        passed = [r for r in applicable if predicate(r) is True]
        return {
            "passed": len(passed),
            "applicable": len(applicable),
            "rate": (len(passed) / len(applicable)) if applicable else None,
        }

    return {
        "total_runs": total,
        # `or {}`, not `.get(X, {})`: a report written by a command that
        # hasn't run `validate` yet (verify-vulnerabilities,
        # forensic-scenario-from-run - both fall back to a fresh
        # {"scans": None, "molecule": None, ...} dict if no report.json
        # exists) has these keys *present* with value None, not missing -
        # `.get(X, {})`'s default never triggers for a present-but-None
        # key, so it returned None instead of {} and crashed the next
        # .get() in the chain. Confirmed by hitting exactly this running
        # report-summary against real week 6 runs. See docs/METHODOLOGY.md.
        "checkov": _rate(lambda r: (r.get("scans") or {}).get("checkov", {}).get("passed")),
        "ansible_lint": _rate(lambda r: (r.get("scans") or {}).get("ansible_lint", {}).get("passed")),
        "molecule": _rate(lambda r: (r.get("molecule") or {}).get("passed")),
        "test_deploy_booted": _rate(lambda r: (r.get("test_deploy") or {}).get("booted")),
        "test_deploy_config_verified": _rate(
            lambda r: (r.get("test_deploy") or {}).get("config_verified")
        ),
        # Per-run: did every artefact in a forensic run's storyline verify.
        # None on runs with no storyline (not just "no" - see
        # TestDeployResult.artefacts_verified), so plain curriculum-VM
        # runs don't drag this rate down.
        "test_deploy_artefacts_verified": _rate(
            lambda r: (r.get("test_deploy") or {}).get("artefacts_verified")
        ),
        # Per-check, not per-run: how reliably individual pieces of
        # planted evidence verify and are attributable to the run that
        # planted them, across every forensic scenario run so far. Finer
        # grained than the per-run rate above once there's more than a
        # couple of forensic runs - "every artefact in this run verified"
        # and "how reliably does artefact planting work overall" are
        # different questions. See docs/METHODOLOGY.md (week 5).
        "artefact_checks": _artefact_check_stats(reports),
        # Per-claim, across every run with a "vulnerabilities" section
        # (verify-vulnerabilities): of everything the generation step
        # claimed to have applied, how much was actually checkable live,
        # how much of what was checkable turned out true, and of what was
        # true, how much is actually attributable to this run's own role
        # rather than a pre-existing default. See docs/METHODOLOGY.md
        # (week 6).
        "vulnerability_claims": _vulnerability_claim_stats(reports),
    }


def _artefact_check_stats(reports: list[dict]) -> dict:
    all_checks = [
        check
        for report in reports
        for check in ((report.get("test_deploy") or {}).get("checks") or [])
        if check.get("category") == "artefact"
    ]
    total = len(all_checks)
    matched = sum(1 for c in all_checks if c.get("matched"))
    attributed = sum(1 for c in all_checks if c.get("attribution") == "changed")
    return {
        "total_checks": total,
        "matched": matched,
        "match_rate": (matched / total) if total else None,
        "attributed_to_this_run": attributed,
        "attribution_rate": (attributed / total) if total else None,
    }


def _vulnerability_claim_stats(reports: list[dict]) -> dict:
    all_findings = [
        finding
        for report in reports
        for finding in (report.get("vulnerabilities") or {}).get("findings", [])
    ]
    total = len(all_findings)
    verifiable = [f for f in all_findings if f.get("verifiable")]
    true_on_vm = [f for f in verifiable if f.get("actual")]
    attributed = [f for f in true_on_vm if f.get("attribution") == "changed"]
    return {
        "total_claims": total,
        "verifiable": len(verifiable),
        "verifiable_rate": (len(verifiable) / total) if total else None,
        "true_on_vm": len(true_on_vm),
        "true_rate_of_verifiable": (len(true_on_vm) / len(verifiable)) if verifiable else None,
        "attributed_to_this_run": len(attributed),
        "attribution_rate_of_true": (len(attributed) / len(true_on_vm)) if true_on_vm else None,
    }
