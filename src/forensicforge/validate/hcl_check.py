from pathlib import Path

import hcl2

from .scanners import Finding, ScanResult

# Top-level blocks a Packer template needs at minimum to be structurally
# usable - not a full schema check, just "is this recognizably a Packer
# template" rather than arbitrary HCL.
REQUIRED_BLOCKS = ("source", "build")


def validate_packer_template(path: Path) -> ScanResult:
    """Parse a .pkr.hcl file with python-hcl2 and check basic structure.

    This is narrowly the HCL side of structural validation: is the file
    syntactically valid HCL2, and does it have the blocks a Packer
    template needs. It does not run `packer validate` (which would need
    Packer's plugins installed) and does not check the Ansible role's
    structure - that's ansible-lint's job (scanners.py).
    """
    try:
        with path.open(encoding="utf-8") as f:
            data = hcl2.load(f)
    except Exception as exc:  # lark raises several distinct exception types
        return ScanResult(
            tool="python-hcl2",
            passed=False,
            findings=[Finding(rule_id="hcl-parse-error", message=str(exc), file=str(path))],
        )

    findings = [
        Finding(
            rule_id="missing-block",
            message=f"Packer template has no top-level '{block}' block.",
            file=str(path),
        )
        for block in REQUIRED_BLOCKS
        if block not in data
    ]

    return ScanResult(
        tool="python-hcl2",
        passed=not findings,
        findings=findings,
        summary={"top_level_blocks": sorted(data.keys())},
    )
