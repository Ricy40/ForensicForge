import json
from pathlib import Path

import click

from . import config
from .forensics import (
    build_storyline_from_vulnerabilities,
    derive_checks_from_storyline,
    load_storyline,
    provision_storyline,
    save_storyline,
    write_artefact_role,
)
from .forensics.scenarios import ALL_SCENARIOS
from .provision import AnsibleParseError, provision_spec
from .service import generate_vm_spec
from .validate import (
    aggregate_reports,
    build_validation_report,
    derive_checks_from_role,
    load_report,
    validate_packer_template,
    verify_vulnerabilities,
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


@main.command(name="forensic-scenario")
@click.argument("scenario_id", required=False)
def forensic_scenario_cmd(scenario_id: str | None) -> None:
    """Provision a forensic storyline: a curriculum VM plus planted synthetic evidence.

    Run with no SCENARIO_ID to list the available storylines. Writes the
    same role/Vagrantfile/Molecule scenario `provision` does, plus a
    second "forensic_artefacts" role that plants the storyline's evidence
    - see docs/METHODOLOGY.md (week 5). Verify with:
    `test-deploy --storyline SCENARIO_ID`.
    """
    if not scenario_id:
        click.echo("Available forensic scenarios:")
        for sid, storyline in ALL_SCENARIOS.items():
            click.echo(f"  {sid}")
            click.echo(f"      {storyline.title}")
        return

    storyline = ALL_SCENARIOS.get(scenario_id)
    if storyline is None:
        click.echo(f"Unknown scenario: {scenario_id!r}. Run with no argument to list available scenarios.", err=True)
        raise SystemExit(1)

    click.echo(f"{storyline.title}\n  {storyline.narrative}\n")
    try:
        result = provision_storyline(storyline)
    except AnsibleParseError as exc:
        click.echo(f"Failed to parse LLM output into a valid Ansible role: {exc}", err=True)
        click.echo("\n--- Raw LLM output ---\n", err=True)
        click.echo(exc.raw_output, err=True)
        raise SystemExit(1)

    click.echo(f"Wrote run '{result.provision.run_id}' to: {result.provision.run_dir}")
    click.echo(f"  Scenario role:  {result.provision.role_dir}")
    click.echo(f"  Artefact role:  {result.artefact_role_dir}")
    click.echo(f"  ({len(storyline.artefacts)} artefact(s) planted)")
    click.echo()
    click.echo("Next:")
    click.echo(f"  forensicforge validate {result.provision.run_dir}")
    click.echo(f"  forensicforge test-deploy {result.provision.run_dir} --storyline {scenario_id}")


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
    # Preserves an existing report's test_deploy section rather than
    # overwriting the whole file: build_validation_report() always sets
    # test_deploy=None (it doesn't boot anything), and re-running
    # `validate` after `test-deploy` had silently wiped that section -
    # confirmed by finding it None in a report a real test-deploy run had
    # just populated. `test-deploy` itself already merges correctly
    # (loads, updates one key, re-saves); `validate` needs the same.
    try:
        existing = load_report(run_dir)
        report["test_deploy"] = existing.get("test_deploy")
    except FileNotFoundError:
        pass
    write_report(report, run_dir)

    _print_scan_summary(report)
    click.echo(f"\nWrote {run_dir / config.REPORT_FILENAME}")


@main.command(name="test-deploy")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--role-name", default="training_vm", help="Role name within run_dir/roles/.")
@click.option(
    "--storyline", "scenario_id", default=None,
    help="Forensic scenario id (see `forensic-scenario` with no argument) to also verify planted evidence for.",
)
@click.option(
    "--storyline-file", "storyline_file", default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a storyline.json written by `forensic-scenario-from-run` (a run-specific "
    "storyline, not one of the fixed ids --storyline looks up) to verify planted evidence for.",
)
def test_deploy_cmd(run_dir: Path, role_name: str, scenario_id: str | None, storyline_file: Path | None) -> None:
    """Boot the generated VM, verify its config, then destroy it - automatically.

    Replaces the manual `vagrant up` workflow from week 3. Requires an
    elevated terminal on this machine (Hyper-V provider requirement) - see
    docs/METHODOLOGY.md. Updates/creates report.json in RUN_DIR. Pass
    --storyline to also verify one of the fixed demo scenarios' planted
    evidence, or --storyline-file for a run-specific one built by
    `forensic-scenario-from-run` (must match whatever was actually planted
    into this RUN_DIR).
    """
    role_dir = run_dir / "roles" / role_name
    checks = derive_checks_from_role(role_dir)

    if scenario_id and storyline_file:
        click.echo("Pass only one of --storyline / --storyline-file.", err=True)
        raise SystemExit(1)

    if scenario_id:
        storyline = ALL_SCENARIOS.get(scenario_id)
        if storyline is None:
            click.echo(f"Unknown scenario: {scenario_id!r}.", err=True)
            raise SystemExit(1)
        checks = checks + derive_checks_from_storyline(storyline)
    elif storyline_file:
        storyline = load_storyline(storyline_file)
        checks = checks + derive_checks_from_storyline(storyline)

    if not checks:
        click.echo("No lineinfile-based checks could be derived from this role; nothing to verify.", err=True)

    click.echo(f"Booting {run_dir} (provider: {config.VAGRANT_PROVIDER}) ...")
    result = run_test_deploy(run_dir, checks)

    click.echo(f"  booted:            {result.booted}")
    click.echo(f"  config_verified:   {result.config_verified}")
    if scenario_id or storyline_file:
        click.echo(f"  artefacts_verified: {result.artefacts_verified}")
    click.echo(f"  destroyed:         {result.destroyed}")
    for check in result.checks:
        mark = "PASS" if check.matched else "FAIL"
        attribution = {
            "changed": "applied by this run",
            "ok": "already true before this run - NOT attributable",
            None: "attribution unknown (task not found in provisioner output)",
        }.get(check.attribution, f"task {check.attribution}")
        tag = "artefact" if check.category == "artefact" else "config"
        click.echo(f"  [{mark}] ({tag}) {check.command}  ({attribution})")
    if result.error:
        click.echo(f"  error: {result.error}", err=True)

    try:
        report = load_report(run_dir)
    except FileNotFoundError:
        report = {"run_id": run_dir.name, "scans": None, "molecule": None}
    report["test_deploy"] = result.to_dict()
    write_report(report, run_dir)
    click.echo(f"\nWrote {run_dir / config.REPORT_FILENAME}")


@main.command(name="verify-vulnerabilities")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--role-name", default="training_vm", help="Role name within run_dir/roles/.")
def verify_vulnerabilities_cmd(run_dir: Path, role_name: str) -> None:
    """Check RUN_DIR's own claimed misconfigurations against a real, booted VM.

    Reads the 'Applied misconfigurations' claims the LLM made at
    generation time (generation.md, persisted since week 6 - runs
    provisioned before this won't have one), matches each to the
    lineinfile task that's supposed to apply it, then boots the VM and
    reports per claim: claimed, actually true on the live VM or not, and
    (via the existing attribution machinery) whether the role itself
    caused it or it was already true beforehand. A claim that can't be
    matched to a checkable task is reported as NOT VERIFIABLE, not
    silently skipped. Boots and destroys its own VM - see
    docs/METHODOLOGY.md (week 6).
    """
    role_dir = run_dir / "roles" / role_name
    click.echo(f"Verifying claimed vulnerabilities for {run_dir} (boots + destroys a VM) ...")

    try:
        result = verify_vulnerabilities(run_dir, role_dir)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1)

    click.echo(f"  booted:    {result.booted}")
    click.echo(f"  destroyed: {result.destroyed}")
    for finding in result.findings:
        mark = "SKIP" if not finding.verifiable else ("TRUE" if finding.actual else "FALSE")
        click.echo(f"  [{mark}] {finding.claim}")
        click.echo(f"         {finding.note}")
    if result.error:
        click.echo(f"  error: {result.error}", err=True)

    try:
        report = load_report(run_dir)
    except FileNotFoundError:
        report = {"run_id": run_dir.name, "scans": None, "molecule": None, "test_deploy": None}
    report["vulnerabilities"] = result.to_dict()
    write_report(report, run_dir)
    click.echo(f"\nWrote {run_dir / config.REPORT_FILENAME}")


@main.command(name="forensic-scenario-from-run")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--role-name", default="training_vm", help="Role name within run_dir/roles/.")
def forensic_scenario_from_run_cmd(run_dir: Path, role_name: str) -> None:
    """Build and plant a forensic storyline derived from RUN_DIR's OWN
    verified vulnerabilities, instead of a hand-authored, decoupled one.

    Runs `verify-vulnerabilities` first (boots + destroys a VM), picks the
    first claim that's both verified true AND attributed to this run's own
    role as this scenario's entry vector, then builds a narrative and
    artefact set around it and plants them. Fails clearly if no claim
    clears that bar - see docs/METHODOLOGY.md (week 6). Verify the planted
    evidence afterward with `test-deploy --storyline-file`.
    """
    role_dir = run_dir / "roles" / role_name
    spec_path = run_dir / config.SPEC_FILENAME
    if not spec_path.exists():
        click.echo(f"No {config.SPEC_FILENAME} recorded for {run_dir} - re-run `provision` first.", err=True)
        raise SystemExit(1)
    spec = spec_path.read_text(encoding="utf-8")

    click.echo(f"Verifying claimed vulnerabilities for {run_dir} (boots + destroys a VM) ...")
    try:
        vuln_report = verify_vulnerabilities(run_dir, role_dir)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1)

    for finding in vuln_report.findings:
        mark = "SKIP" if not finding.verifiable else ("TRUE" if finding.actual else "FALSE")
        click.echo(f"  [{mark}] {finding.claim}")

    try:
        storyline = build_storyline_from_vulnerabilities(vuln_report, spec=spec, run_id=run_dir.name)
    except ValueError as exc:
        click.echo(f"\nCannot build a storyline: {exc}", err=True)
        raise SystemExit(1)

    artefact_role_dir = write_artefact_role(storyline, run_dir, scenario_role_name=role_name)
    storyline_path = run_dir / "storyline.json"
    save_storyline(storyline, storyline_path)

    try:
        report = load_report(run_dir)
    except FileNotFoundError:
        report = {"run_id": run_dir.name, "scans": None, "molecule": None, "test_deploy": None}
    report["vulnerabilities"] = vuln_report.to_dict()
    write_report(report, run_dir)

    click.echo(f"\n{storyline.title}\n  {storyline.narrative}\n")
    click.echo(f"Wrote artefact role:     {artefact_role_dir}")
    click.echo(f"Wrote storyline manifest: {storyline_path}")
    click.echo("\nNext:")
    click.echo(f"  forensicforge test-deploy {run_dir} --storyline-file {storyline_path}")


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
