import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Artefact:
    """One piece of synthetic evidence to plant on the VM.

    `kind` selects which Ansible tasks planter.py generates for it, and
    which verification check derive_checks_from_storyline() builds:
      - "log_entry" / "shell_history": a line appended to an existing
        file (lineinfile) - the same module and verification pattern
        provision/ansible_writer.py's generated roles already use, so
        this reuses derive_checks_from_role()'s grep-based checking and
        test_deploy.py's attribution parsing with no new machinery.
      - "email_draft": a whole file written with specific content (copy).
      - "deleted_file": a file written then removed - the verification
        check confirms *absence*, not content.
      - "backdated_file": a file written then its mtime set to
        `timestamp` via `touch -d` - the verification check confirms the
        actual on-disk timestamp, not just that the file exists.
    """
    kind: str
    description: str  # human-readable, shown in the manifest/report
    target_path: str
    content: str = ""
    timestamp: str | None = None  # ISO 8601 (e.g. "2026-08-15T02:14:00"), for backdated_file


@dataclass
class Storyline:
    """A forensic scenario: a narrative brief plus the evidence to plant.

    `base_spec` is a plain-English VM spec fed into the existing
    generate_vm_spec() RAG pipeline unchanged - a storyline is what the
    machine should *look like it did*, layered on top of what the
    machine actually *is* (the usual curriculum VM spec).
    """
    id: str
    title: str
    narrative: str
    base_spec: str
    artefacts: list[Artefact] = field(default_factory=list)


def save_storyline(storyline: Storyline, path: Path) -> None:
    """Persist a Storyline to disk so a later CLI invocation (e.g.
    `test-deploy --storyline-file`) can verify its artefacts without
    needing the object that built it still in memory - needed for
    storylines built by storyline_builder.py, which are specific to one
    run rather than one of the fixed ids in scenarios.ALL_SCENARIOS.
    """
    path.write_text(json.dumps(asdict(storyline), indent=2), encoding="utf-8")


def load_storyline(path: Path) -> Storyline:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artefacts"] = [Artefact(**a) for a in data["artefacts"]]
    return Storyline(**data)
