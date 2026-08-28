"""CI entry point: run ansible-lint + checkov against the fixture role.

Used by .github/workflows/validate.yml, run on GitHub's Linux runners -
where ansible-lint runs natively (no WSL bridge needed; see
docs/METHODOLOGY.md week 4). Uses this project's own scanning code
directly rather than re-implementing CLI parsing in the workflow YAML.

Exits nonzero if either scan fails, so the CI job fails - the normal use
of scanners.py (validate CLI command) reports findings without treating a
failed scan as fatal, but CI's whole point is to fail loudly.
"""

import json
import sys
from pathlib import Path

from forensicforge.validate import run_ansible_lint, run_checkov

FIXTURE_ROLE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "example_role"


def main() -> int:
    results = {
        "ansible_lint": run_ansible_lint(FIXTURE_ROLE).to_dict(),
        "checkov": run_checkov(FIXTURE_ROLE).to_dict(),
    }
    print(json.dumps(results, indent=2))

    failed = [name for name, result in results.items() if result["passed"] is False]
    unavailable = [name for name, result in results.items() if result["passed"] is None]
    if unavailable:
        print(f"UNAVAILABLE (treated as failure in CI): {unavailable}", file=sys.stderr)
    if failed or unavailable:
        print(f"FAILED: {failed + unavailable}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
