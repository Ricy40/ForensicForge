"""Bridge for running POSIX-only tools (ansible-lint, Molecule) from Windows.

Both depend on ansible-core, which imports POSIX-only stdlib modules (grp,
fcntl) that don't exist on Windows - see docs/METHODOLOGY.md (week 4).
This module shells out to WSL rather than reimplementing anything: the
tools themselves still need to be installed *inside* the WSL distro
separately from this project's venv (see scripts/check_wsl_tools.py).

On non-Windows hosts (e.g. GitHub Actions' Linux runners) none of this
applies - ansible-core imports fine natively there, so run_posix_tool()
skips WSL entirely. Callers (scanners.py, molecule_runner.py) should use
run_posix_tool(), not run_in_wsl() directly, unless they specifically
need the Windows-only behavior.
"""

import subprocess
from pathlib import Path

from .. import config


class WslUnavailableError(Exception):
    """WSL itself couldn't be reached - distinct from the wrapped command failing.

    A command that runs and returns nonzero is a normal scan result. This
    is for when WSL can't even be asked the question: not installed, not
    on PATH, or hung (which happens - see the week 4 methodology notes).
    """


def to_wsl_path(windows_path: Path) -> str:
    """Convert an absolute Windows path to its default WSL2 /mnt/<drive> form."""
    resolved = windows_path.resolve()
    drive_letter = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix()[len(resolved.drive):].lstrip("/")
    return f"/mnt/{drive_letter}/{rest}"


def _wsl_base_cmd() -> list[str]:
    wsl_cmd = ["wsl"]
    if config.WSL_DISTRO:
        wsl_cmd += ["-d", config.WSL_DISTRO]
    wsl_cmd.append("--")
    return wsl_cmd


def check_wsl_responsive(timeout: int = 10) -> bool:
    """Fast liveness probe, separate from the (possibly slow) real command.

    Without this, a hung WSL (which happens - see docs/METHODOLOGY.md
    week 4) means every caller waits out its full command timeout just to
    learn WSL was never going to answer. A trivial command gets its own
    short timeout so that failure is fast, while a real ansible-lint/
    Molecule run downstream still gets however long it legitimately needs.
    """
    try:
        proc = subprocess.run(
            [*_wsl_base_cmd(), "true"], capture_output=True, timeout=timeout, check=False
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_in_wsl(
    command: str,
    cwd: Path | None = None,
    timeout: int = 300,
    liveness_timeout: int = 10,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command string inside WSL, optionally from `cwd`.

    Returns the completed process regardless of exit code (a nonzero exit
    from the wrapped tool is a normal, meaningful result). Raises
    WslUnavailableError fast if WSL itself doesn't respond to a liveness
    probe within `liveness_timeout`; only a WSL that passes that probe but
    then hangs on the real command waits out the full `timeout`.
    """
    if not check_wsl_responsive(timeout=liveness_timeout):
        raise WslUnavailableError(
            f"WSL did not respond to a liveness check within {liveness_timeout}s. "
            "It may not be installed, or may be stuck - try `wsl --shutdown` "
            "and retry, or a reboot."
        )

    # ansible-lint/molecule live in a dedicated venv (see config.WSL_TOOLS_VENV
    # and scripts/check_wsl_tools.py) rather than WSL's system Python, which
    # Ubuntu 23.10+ blocks installing into directly (PEP 668). molecule
    # specifically needs the venv *activated*, not just its bin/ prefixed
    # onto PATH: it shells out to sibling binaries like ansible-config by
    # bare name, so activation is what makes those resolve.
    command = f"source {config.WSL_TOOLS_VENV}/bin/activate && {command}"
    command = f"cd {to_wsl_path(cwd)} && {command}" if cwd is not None else command
    wsl_cmd = [*_wsl_base_cmd(), "bash", "-lc", command]

    try:
        # encoding="utf-8" is required, not cosmetic: text=True alone decodes
        # with locale.getpreferredencoding() (cp1252 on this machine), but
        # WSL's output is UTF-8 - box-drawing characters in Molecule's Rich-
        # formatted output came through as mojibake in report.json before
        # this was added (confirmed by finding "â”‚" - UTF-8
        # "│" misdecoded as cp1252 - in an actual captured report.json).
        return subprocess.run(
            wsl_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise WslUnavailableError(
            "The `wsl` command is not available on this machine."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise WslUnavailableError(
            f"WSL accepted the liveness check but the actual command did not "
            f"finish within {timeout}s."
        ) from exc


def run_posix_tool(
    command: str,
    cwd: Path | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run a command that needs ansible-core: natively, or via WSL on Windows.

    This is what scanners.py and molecule_runner.py actually call. On
    Windows it delegates to run_in_wsl() (and can raise
    WslUnavailableError). On any other platform - a Linux CI runner,
    chiefly - ansible-core has no POSIX-module problem to route around,
    so the command just runs directly.
    """
    if config.RUNS_ON_WINDOWS:
        return run_in_wsl(command, cwd=cwd, timeout=timeout)

    return subprocess.run(
        ["bash", "-lc", command],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
    )
