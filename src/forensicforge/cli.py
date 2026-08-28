import json
from pathlib import Path

import click

from . import config
from .provision import AnsibleParseError, provision_spec
from .service import generate_vm_spec
from .validate import (
    aggregate_reports,
    build_validation_report,
    derive_checks_from_role,
    load_report,
    validate_packer_template,
    write_report,
)
from .validate.test_deploy import test_deploy as run_test_deploy


@click.group()
def main() -> None:
    """ForensicForge: generate, provision, and validate curriculum-aligned training VMs."""


@main.command()
@click.argument("spec")
@click.option(
    "--no-rag", is_flag=True,
    help="Skip retrieval and use the ungrounded week-1 prompt instead.",
)
def generate(spec: str, no_rag: bool) -> None:
    """Generate a VM configuration from a plain-English SPEC and print the raw output."""
    result = generate_vm_spec(spec, use_rag=not no_rag)

    if result.snippets:
        click.echo(f"Retrieved {len(result.snippets)} snippet(s):")
        for snippet in result.snippets:
            click.echo(f"  - {snippet.source}")
        click.echo()

    click.echo(result.output)


@main.command()
@click.argument("spec")
def provision(spec: str) -> None:
    """Generate a VM spec and write an Ansible role + Vagrantfile + Molecule scenario.

    Does NOT boot anything - run `validate` for static scans and Molecule
    verification, then `test-deploy` to boot/verify/destroy a real VM.
    """
    try:
        result = provision_spec(spec)
    except AnsibleParseError as exc:
        click.echo(f"Failed to parse LLM output into a valid Ansible role: {exc}", err=True)
        click.echo("\n--- Raw LLM output ---\n", err=True)
        click.echo(exc.raw_output, err=True)
        raise SystemExit(1)

    click.echo(f"Wrote run '{result.run_id}' to: {result.run_dir}")
    click.echo(f"  Ansible role:      {result.role_dir}")
    click.echo(f"  Vagrantfile:       {result.vagrantfile}")
    click.echo(f"  Molecule scenario: {result.molecule_scenario}")
    click.echo()
    click.echo("Next:")
    click.echo(f"  forensicforge validate {result.run_dir}")
    click.echo(f"  forensicforge test-deploy {result.run_dir}")


@main.command()
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--role-name", default="training_vm", help="Role name within run_dir/roles/.")
def validate(run_dir: Path, role_name: str) -> None:
    """Run checkov, ansible-lint, and Molecule against a provisioned run.

    CI-safe: does not boot a VM (that's `test-deploy`). Writes/updates
    report.json in RUN_DIR.
    """
    role_dir = run_dir / "roles" / role_name
    spec_hint = None

    click.echo(f"Validating {role_dir} ...")
    report = build_validation_report(run_id=run_dir.name, role_dir=role_dir, spec=spec_hint)
    write_report(report, run_dir)

    _print_scan_summary(report)
    click.echo(f"\nWrote {run_dir / config.REPORT_FILENAME}")


@main.command(name="test-deploy")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--role-name", default="training_vm", help="Role name within run_dir/roles/.")
def test_deploy_cmd(run_dir: Path, role_name: str) -> None:
    """Boot the generated VM, verify its config, then destroy it - automatically.

    Replaces the manual `vagrant up` workflow from week 3. Requires an
    elevated terminal on this machine (Hyper-V provider requirement) - see
    docs/METHODOLOGY.md. Updates/creates report.json in RUN_DIR.
    """
    role_dir = run_dir / "roles" / role_name
    checks = derive_checks_from_role(role_dir)

    if not checks:
        click.echo("No lineinfile-based checks could be derived from this role; nothing to verify.", err=True)

    click.echo(f"Booting {run_dir} (provider: {config.VAGRANT_PROVIDER}) ...")
    result = run_test_deploy(run_dir, checks)

    click.echo(f"  booted:          {result.booted}")
    click.echo(f"  config_verified: {result.config_verified}")
    click.echo(f"  destroyed:       {result.destroyed}")
    for check in result.checks:
        mark = "PASS" if check.matched else "FAIL"
        click.echo(f"  [{mark}] {check.command}")
    if result.error:
        click.echo(f"  error: {result.error}", err=True)

    try:
        report = load_report(run_dir)
    except FileNotFoundError:
        report = {"run_id": run_dir.name, "scans": None, "molecule": None}
    report["test_deploy"] = result.to_dict()
    write_report(report, run_dir)
    click.echo(f"\nWrote {run_dir / config.REPORT_FILENAME}")


@main.command(name="check-packer")
@click.argument(
    "template",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=config.PROJECT_ROOT / "packer" / "ubuntu-base.pkr.hcl",
)
def check_packer(template: Path) -> None:
    """Structurally validate a Packer .pkr.hcl template with python-hcl2."""
    result = validate_packer_template(template)
    click.echo(f"{template}: {'OK' if result.passed else 'FAILED'}")
    for finding in result.findings:
        click.echo(f"  [{finding.rule_id}] {finding.message}")
    if not result.passed:
        raise SystemExit(1)


@main.command(name="report-summary")
@click.option(
    "--generated-dir", type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=config.GENERATED_DIR,
)
def report_summary(generated_dir: Path) -> None:
    """Aggregate report.json across every run into pass rates."""
    summary = aggregate_reports(generated_dir)
    click.echo(json.dumps(summary, indent=2))


def _print_scan_summary(report: dict) -> None:
    for name, scan in report["scans"].items():
        status = "PASS" if scan["passed"] else ("N/A" if scan["passed"] is None else "FAIL")
        click.echo(f"  [{status}] {name} ({len(scan['findings'])} finding(s))")
        for finding in scan["findings"]:
            click.echo(f"      {finding['rule_id']}: {finding['message']}")
        if scan.get("error"):
            click.echo(f"      error: {scan['error']}")

    molecule = report["molecule"]
    status = "PASS" if molecule["passed"] else ("N/A" if molecule["passed"] is None else "FAIL")
    click.echo(f"  [{status}] molecule")
    if molecule.get("error"):
        click.echo(f"      error: {molecule['error']}")


if __name__ == "__main__":
    main()
