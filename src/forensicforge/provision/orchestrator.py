import datetime
from dataclasses import dataclass
from pathlib import Path

from .. import config
from ..service import generate_vm_spec
from .ansible_writer import write_ansible_role
from .molecule_writer import write_molecule_scenario
from .vagrantfile_writer import write_vagrantfile


def make_run_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass
class ProvisionResult:
    run_id: str
    run_dir: Path
    role_dir: Path
    vagrantfile: Path
    molecule_scenario: Path
    raw_output: str


def provision_spec(spec: str, role_name: str = "training_vm") -> ProvisionResult:
    """RAG-generate a spec, parse it into an Ansible role, and write a
    Vagrantfile plus a Molecule scenario for it.

    Raises ansible_writer.AnsibleParseError (with the raw LLM output
    attached) if the generated output isn't a valid task list - nothing is
    written to disk in that case. Does not run `vagrant up` or
    `molecule test`; use the `test-deploy` and `validate` CLI commands
    (or run them yourself) once the role is written.
    """
    result = generate_vm_spec(spec, use_rag=True)

    run_id = make_run_id()
    run_dir = config.GENERATED_DIR / run_id

    role_dir = write_ansible_role(result.output, run_dir, role_name=role_name)
    vagrantfile = write_vagrantfile(run_dir, hostname=f"forensicforge-{run_id}")
    molecule_scenario = write_molecule_scenario(role_dir, role_name=role_name)

    return ProvisionResult(
        run_id=run_id,
        run_dir=run_dir,
        role_dir=role_dir,
        vagrantfile=vagrantfile,
        molecule_scenario=molecule_scenario,
        raw_output=result.output,
    )
