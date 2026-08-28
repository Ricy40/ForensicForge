from dataclasses import dataclass
from pathlib import Path

from ..provision import ProvisionResult, provision_spec
from .planter import write_artefact_role
from .storyline import Storyline


@dataclass
class ForensicProvisionResult:
    provision: ProvisionResult
    artefact_role_dir: Path
    storyline: Storyline


def provision_storyline(storyline: Storyline, role_name: str = "training_vm") -> ForensicProvisionResult:
    """RAG-generate `storyline.base_spec` into a scenario role (exactly
    like provision_spec()), then plant the storyline's artefacts as a
    second role run alongside it.

    A second role, not folded into the scenario role: keeps "what the
    box is" (the curriculum VM spec, generated the same way every other
    run is) separate from "what evidence is on it" (this storyline's
    artefacts) - the same distinction the narrative brief itself draws
    between a machine and the story layered on top of it. See
    planter.py and docs/METHODOLOGY.md (week 5).
    """
    result = provision_spec(storyline.base_spec, role_name=role_name)
    artefact_role_dir = write_artefact_role(storyline, result.run_dir, scenario_role_name=role_name)
    return ForensicProvisionResult(
        provision=result, artefact_role_dir=artefact_role_dir, storyline=storyline
    )
