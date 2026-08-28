"""Check that WSL is responsive and has ansible-lint + Molecule installed.

ansible-lint and Molecule depend on ansible-core, which needs POSIX-only
stdlib modules (grp, fcntl) not present on Windows - see
docs/METHODOLOGY.md (week 4). Both run inside WSL instead of this
project's Windows venv, in a dedicated venv there (see TOOLS_VENV below -
must match forensicforge.config.WSL_TOOLS_VENV) rather than WSL's system
Python, which recent Ubuntu blocks installing into directly (PEP 668).

Never installs anything without asking first. Getting from a fresh WSL
Ubuntu distro to a working venv needs `python3-venv`, which needs `apt`,
which needs a sudo password this script has no way to supply - if that's
missing, it tells you the one command to run yourself rather than trying
to work around it.
"""

import subprocess
import sys

TOOLS_VENV = "~/.forensicforge-tools"  # keep in sync with config.WSL_TOOLS_VENV
TOOLS = ["ansible-lint", "molecule"]
INSTALL_CMD = "pip install -q ansible-lint molecule 'molecule-plugins[vagrant]'"

# molecule-plugins' vagrant driver manages instances via its own bundled
# Ansible `vagrant` module (molecule_plugins/vagrant/modules/vagrant.py),
# not one from ansible-core or a galaxy collection - the `community.vagrant`
# collection on Galaxy looks like the answer but is an empty v0.0.0
# placeholder (confirmed by inspecting what it actually installs: no
# plugins/modules/ at all). Nothing puts the bundled module on Ansible's
# search path automatically either; molecule_runner.py's
# _find_ansible_library() handles that in code (setting ANSIBLE_LIBRARY
# per invocation) rather than needing any one-time WSL setup step here -
# see docs/METHODOLOGY.md (week 4) for the full story.

# Vagrant itself is only installed on the Windows side, not inside WSL -
# but WSL2's interop makes vagrant.exe directly callable, so a symlink
# named plain `vagrant` on the venv's PATH is enough for Molecule's
# Vagrant driver (which shells out to a bare `vagrant`) to find it.
VAGRANT_EXE = "/mnt/c/Program Files/Vagrant/bin/vagrant.exe"
VAGRANT_LINK_CMD = f"ln -sf '{VAGRANT_EXE}' {TOOLS_VENV}/bin/vagrant"


def wsl(command: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["wsl", "--", "bash", "-lc", command], capture_output=True, text=True, timeout=timeout
    )


def check_wsl_responsive(timeout: int = 15) -> bool:
    try:
        return wsl("true", timeout=timeout).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_venv_has_python(timeout: int = 15) -> bool:
    try:
        return wsl(f"test -x {TOOLS_VENV}/bin/python3", timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def check_venv_module_available(timeout: int = 15) -> bool:
    """Whether WSL's system Python can even create a venv (needs python3-venv)."""
    try:
        return wsl("python3 -c 'import venv'", timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def check_tools_installed(timeout: int = 15) -> list[str]:
    missing = []
    for tool in TOOLS:
        try:
            result = wsl(f"test -x {TOOLS_VENV}/bin/{tool}", timeout=timeout)
        except subprocess.TimeoutExpired:
            missing.append(tool)
            continue
        if result.returncode != 0:
            missing.append(tool)
    return missing


def main() -> int:
    print("Checking WSL...")
    if not check_wsl_responsive():
        print(
            "WSL isn't responding (not installed, or stuck - try `wsl --shutdown` "
            "and retry, or a reboot). ansible-lint and Molecule can't run without it."
        )
        return 1
    print("WSL is responsive.")

    if not check_venv_has_python():
        if not check_venv_module_available():
            print(
                f"\n{TOOLS_VENV} doesn't exist yet, and WSL's system Python can't "
                "create a venv (missing python3-venv). This needs a sudo password "
                "this script can't supply - please run this yourself in a WSL "
                "terminal, then re-run this script:\n\n"
                "    sudo apt update && sudo apt install -y python3-pip python3-venv\n"
            )
            return 1

        answer = input(f"Create a venv at {TOOLS_VENV} inside WSL now? [y/N] ").strip().lower()
        if answer != "y":
            print(f"Skipped. Create it yourself with: wsl -- python3 -m venv {TOOLS_VENV}")
            return 1
        subprocess.run(["wsl", "--", "bash", "-lc", f"python3 -m venv {TOOLS_VENV}"], check=True)
        print(f"Created {TOOLS_VENV}.")

    missing = check_tools_installed()
    if not missing:
        print("ansible-lint and Molecule are already installed.")
    else:
        print(f"Not installed yet: {', '.join(missing)}")
        answer = input(f"Install them into {TOOLS_VENV} now? [y/N] ").strip().lower()
        if answer == "y":
            subprocess.run(
                ["wsl", "--", "bash", "-lc", f"{TOOLS_VENV}/bin/{INSTALL_CMD}"], check=True
            )
            print("Installed.")
        else:
            print(f"Skipped. Install manually later with: wsl -- {TOOLS_VENV}/bin/{INSTALL_CMD}")
            return 1

    vagrant_link = wsl(f"test -L {TOOLS_VENV}/bin/vagrant")
    if vagrant_link.returncode == 0:
        print("vagrant symlink (to the Windows vagrant.exe) already set up.")
    else:
        answer = input(
            "Molecule's Vagrant driver needs a `vagrant` on PATH inside WSL - "
            f"link it to the Windows vagrant.exe now? [y/N] "
        ).strip().lower()
        if answer == "y":
            subprocess.run(["wsl", "--", "bash", "-lc", VAGRANT_LINK_CMD], check=True)
            print("Linked.")
        else:
            print(f"Skipped. Link it yourself with: wsl -- {VAGRANT_LINK_CMD}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
