import re
from pathlib import Path

from .. import config
from .scanners import Finding, ScanResult
from .wsl_bridge import WslUnavailableError, run_posix_tool, to_wsl_path

_VAGRANT_MODULES_HELPER = config.PROJECT_ROOT / "scripts" / "wsl_helpers" / "print_vagrant_modules_dir.py"

# Molecule (via `rich`) colors its output even when captured non-
# interactively through this bridge, which otherwise ends up as raw
# escape sequences polluting report.json.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _find_ansible_library() -> str:
    """Locate molecule-plugins' bundled Vagrant `vagrant` Ansible module dir.

    Nothing puts it on Ansible's module search path automatically -
    confirmed by reproducing "couldn't resolve module/action 'vagrant'"
    and fixing it by setting ANSIBLE_LIBRARY by hand. This is a *separate*
    run_posix_tool() call rather than a `$(...)` expression folded into
    the main molecule command: that was tried first and its captured
    output was unreliably empty crossing the Windows subprocess -> wsl.exe
    -> WSL bash boundary specifically when combined with `$(...)`, even
    with the corrupted-quoting problem below already worked around (see
    print_vagrant_modules_dir.py's docstring) - reproduced repeatedly,
    root cause not fully pinned down. Getting the value back into this
    Python process and passing it as a literal on the next call sidesteps
    the whole question. Returns "" if it can't be found (e.g. a
    Docker-only molecule-plugins install, as in CI) - harmless as an
    empty ANSIBLE_LIBRARY.
    """
    helper = to_wsl_path(_VAGRANT_MODULES_HELPER) if config.RUNS_ON_WINDOWS else str(_VAGRANT_MODULES_HELPER)
    python3 = f"{config.WSL_TOOLS_VENV}/bin/python3" if config.RUNS_ON_WINDOWS else "python3"
    try:
        proc = run_posix_tool(f"{python3} {helper}")
    except WslUnavailableError:
        return ""
    return proc.stdout.strip()


def run_molecule(role_dir: Path, scenario: str = "default") -> ScanResult:
    """Run `molecule test` for the generated role's scenario.

    Molecule depends on ansible-core, which needs POSIX-only stdlib
    modules not present on Windows - see wsl_bridge.py and
    docs/METHODOLOGY.md (week 4). On Windows this runs via WSL (installed
    there separately from this project's venv - scripts/check_wsl_tools.py);
    on other platforms it runs directly. Either way, whatever driver the
    target scenario's molecule.yml declares needs to actually be usable
    wherever this runs - locally that's the Vagrant driver
    (provision/molecule_writer.py explains why), in CI it's the fixture
    role's Docker-driven "ci" scenario instead (see .github/workflows).

    Molecule is invoked with the role directory itself as the working
    directory: that's what lets its "roles: [role_name]" converge
    playbook resolve the role via Ansible's standard role search relative
    to molecule/'s parent, without needing an explicit roles_path.
    """
    ansible_library = _find_ansible_library()
    library_prefix = f"export ANSIBLE_LIBRARY={ansible_library} && " if ansible_library else ""

    try:
        proc = run_posix_tool(
            f"{library_prefix}molecule test --scenario-name {scenario}",
            cwd=role_dir,
        )
    except WslUnavailableError as exc:
        return ScanResult(tool="molecule", passed=None, error=str(exc))

    if proc.returncode == 127:
        return ScanResult(
            tool="molecule", passed=None,
            error=(
                "molecule is not installed. On Windows, install it inside WSL "
                "(separate from this project's venv): wsl -- pip install "
                "--user molecule 'molecule-plugins[vagrant]'. Elsewhere: "
                "pip install molecule 'molecule-plugins[docker]'."
            ),
        )

    # Molecule has no machine-readable summary format the way
    # ansible-lint/checkov do - its own exit code plus tail of its
    # textual output is the practical signal available here.
    findings = []
    if proc.returncode != 0:
        tail = _ANSI_ESCAPE.sub("", proc.stdout or proc.stderr or "")[-4000:]
        findings.append(Finding(rule_id="molecule-test-failed", message=tail))

    return ScanResult(
        tool="molecule",
        passed=proc.returncode == 0,
        findings=findings,
        summary={"exit_code": proc.returncode},
    )
