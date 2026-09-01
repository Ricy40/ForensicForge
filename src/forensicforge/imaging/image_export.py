"""Export a booted VM's disk as a portable image, importable directly into
VirtualBox or VMware - build-scenario's final step (week 6).

Two host-side tools do the real work, neither native to what this project
already used:

- Hyper-V's own `Export-VM` PowerShell cmdlet copies a VM's disk safely,
  including one that's still running - Hyper-V's export mechanism is
  built for exactly this, unlike a plain file copy of the live VHDX,
  which risks reading a locked or inconsistent file. `Convert-VHD` (also
  available on this machine) only converts between Microsoft's own
  VHD/VHDX formats - it does not produce anything VirtualBox or VMware
  can read, so it doesn't help here.
- `qemu-img` converts the exported VHDX to VMDK, which both VirtualBox
  and VMware can import directly. Neither a native Windows build nor an
  existing WSL install had it on this machine when checked, so it runs
  through the same WSL bridge validate/wsl_bridge.py already uses for
  ansible-lint/Molecule (see scripts/check_wsl_tools.py for the install
  step this needs the first time).

UNVERIFIED AGAINST A REAL VM as of its first version: every other
Hyper-V-touching piece of this project needed live iteration against the
user's own elevated terminal before it worked (see docs/METHODOLOGY.md,
weeks 3-6) - this one hasn't been through that yet. Treat the exact
Export-VM/qemu-img mechanics here as a first draft, not a proven one.
"""

import shutil
import subprocess
from pathlib import Path

from ..validate.wsl_bridge import WslUnavailableError, run_in_wsl, to_wsl_path

_EXPORT_TIMEOUT = 900  # a full disk export can be slow - VM disks run several GB
_CONVERT_TIMEOUT = 900


class ImageExportError(Exception):
    """The disk export or format conversion failed.

    Distinct from a boot/provisioning failure - by the time this can be
    raised, the VM already booted and (if checks were given) was already
    verified; TestDeployResult/CheckResult are what report those.
    """


def export_vhdx(vm_name: str, run_dir: Path) -> Path:
    """Export the Hyper-V VM named `vm_name`'s disk to run_dir/image.vhdx.

    `vm_name` must match vagrantfile_writer.py's `h.vmname` setting for
    this run (its VAGRANTFILE_TEMPLATE sets it to the same hostname
    provision_spec() already generates) - Export-VM needs a name, and
    Vagrant's own auto-generated Hyper-V VM names aren't predictable
    without it. `Export-VM` writes a full export folder (VM config,
    checkpoints, disks); only the disk file is kept from it.
    """
    export_dir = run_dir / "_hyperv_export"
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"Export-VM -Name '{vm_name}' -Path '{export_dir}'; "
        f"$disk = Get-ChildItem -Path '{export_dir}' -Recurse -Filter *.vhdx | Select-Object -First 1; "
        "if (-not $disk) { throw 'Export-VM completed but no .vhdx was found in the export' }; "
        "Write-Output $disk.FullName"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=_EXPORT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise ImageExportError(f"Export-VM for {vm_name!r} did not finish within {_EXPORT_TIMEOUT}s") from exc

    if proc.returncode != 0:
        raise ImageExportError(
            f"Export-VM failed for {vm_name!r}: {proc.stderr.strip() or proc.stdout.strip()}"
        )

    exported_vhdx = Path(proc.stdout.strip().splitlines()[-1])
    dest = run_dir / "image.vhdx"
    shutil.copyfile(exported_vhdx, dest)
    shutil.rmtree(export_dir, ignore_errors=True)
    return dest


def convert_to_vmdk(vhdx_path: Path) -> Path:
    """Convert a VHDX to VMDK via qemu-img (run through WSL - see module docstring)."""
    vmdk_path = vhdx_path.with_suffix(".vmdk")
    command = f'qemu-img convert -O vmdk "{to_wsl_path(vhdx_path)}" "{to_wsl_path(vmdk_path)}"'
    try:
        proc = run_in_wsl(command, timeout=_CONVERT_TIMEOUT)
    except WslUnavailableError as exc:
        raise ImageExportError(f"qemu-img conversion needs WSL, which isn't reachable: {exc}") from exc

    if proc.returncode != 0:
        raise ImageExportError(
            "qemu-img convert failed - is qemu-utils installed in WSL? "
            f"(see scripts/check_wsl_tools.py): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return vmdk_path


def export_scenario_image(run_dir: Path, vm_name: str) -> Path:
    """Export `vm_name`'s disk and convert it to VMDK. Returns the VMDK
    path.

    The intermediate VHDX (run_dir/image.vhdx) is deleted once conversion
    succeeds, not kept alongside the VMDK - each of the two is a full,
    uncompressed copy of the same multi-GB disk (~11GB VHDX + ~6GB VMDK,
    confirmed against a real run), and the VMDK is the actual deliverable
    (importable into VirtualBox/VMware; the VHDX isn't, without another
    conversion step). Keeping both was a real, avoidable disk-space
    problem for anyone running more than a couple of scenarios back to
    back - confirmed in practice, not hypothetically, running a multi-spec
    evaluation batch. If conversion fails, the VHDX is left in place -
    it's the only copy of the disk at that point, not a redundant one.
    """
    vhdx_path = export_vhdx(vm_name, run_dir)
    vmdk_path = convert_to_vmdk(vhdx_path)
    vhdx_path.unlink()
    return vmdk_path
