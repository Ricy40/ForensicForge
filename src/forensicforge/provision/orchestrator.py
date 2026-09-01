import datetime
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .. import config
from ..rag.chain import Snippet
from ..service import generate_vm_spec
from .ansible_writer import write_ansible_role
from .molecule_writer import write_molecule_scenario
from .vagrantfile_writer import write_vagrantfile

# Characters Windows forbids in a path component, plus control characters.
# Spaces are deliberately kept - a --name of "ssh bastion" should stay
# "ssh bastion" in the folder name, not get mangled into "ssh_bastion".
_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def make_run_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _sanitize_run_name(name: str) -> str:
    return _INVALID_PATH_CHARS.sub("", name).strip()


@dataclass
class ProvisionResult:
    run_id: str
    run_dir: Path
    role_dir: Path
    vagrantfile: Path
    molecule_scenario: Path
    raw_output: str
    repairs: list[str]
    snippets: list[Snippet]
    # The exact string used for both the guest's hostname and the Hyper-V
    # VM's own name (config.vm.hostname / h.vmname in the generated
    # Vagrantfile) - always derived from the timestamp alone, never from
    # `--name`. A Linux hostname can't contain spaces or most punctuation,
    # so a human-readable run_id like "20260901-123432-ssh bastion" can't
    # double as the hostname the way a bare timestamp could - callers that
    # need to find this run's actual VM (build-scenario's image export)
    # must use this field, not reconstruct a name from run_id. See
    # docs/METHODOLOGY.md.
    vm_hostname: str


def provision_spec(spec: str, role_name: str = "training_vm", name: str | None = None) -> ProvisionResult:
    """RAG-generate a spec, parse it into an Ansible role, and write a
    Vagrantfile plus a Molecule scenario for it.

    Raises ansible_writer.AnsibleParseError (with the raw LLM output
    attached) if the generated output isn't a valid task list - nothing is
    written to disk in that case. Does not run `vagrant up` or
    `molecule test`; use the `test-deploy` and `validate` CLI commands
    (or run them yourself) once the role is written.

    `name`, if given, is appended to the run directory's name (e.g.
    "20260901-123432-ssh bastion") so a batch of runs stays identifiable
    by eye instead of only by timestamp - purely a folder-naming
    convenience, invisible to everything else (attribution, checks,
    reports all still key off the timestamp-only `vm_hostname` above).
    """
    result = generate_vm_spec(spec, use_rag=True)

    timestamp = make_run_id()
    suffix = _sanitize_run_name(name) if name else ""
    run_id = f"{timestamp}-{suffix}" if suffix else timestamp
    run_dir = config.GENERATED_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    vm_hostname = f"forensicforge-{timestamp}"

    # Persisted so verify-vulnerabilities (week 6) can check this run's own
    # claimed misconfigurations later, without needing the original
    # generate_vm_spec() call still in memory - see docs/METHODOLOGY.md.
    (run_dir / config.SPEC_FILENAME).write_text(spec, encoding="utf-8")
    (run_dir / config.GENERATION_FILENAME).write_text(result.output, encoding="utf-8")
    # Persisted so a spec's *retrieval* quality (did the corpus have
    # anything relevant, not just whether generation parsed) can be
    # audited after the fact - the evaluation round this was added for
    # needed to tell a genuinely corpus-limited spec apart from a
    # generation problem on a spec the corpus covers fine. See
    # docs/METHODOLOGY.md.
    (run_dir / config.RETRIEVAL_FILENAME).write_text(
        json.dumps([asdict(s) for s in result.snippets], indent=2), encoding="utf-8"
    )

    role_dir, repairs = write_ansible_role(result.output, run_dir, role_name=role_name)
    vagrantfile = write_vagrantfile(run_dir, hostname=vm_hostname)
    molecule_scenario = write_molecule_scenario(role_dir, role_name=role_name)

    return ProvisionResult(
        run_id=run_id,
        run_dir=run_dir,
        role_dir=role_dir,
        vagrantfile=vagrantfile,
        molecule_scenario=molecule_scenario,
        raw_output=result.output,
        repairs=repairs,
        snippets=result.snippets,
        vm_hostname=vm_hostname,
    )
