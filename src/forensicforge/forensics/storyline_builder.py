"""Build a forensic storyline whose narrative and entry-vector artefact are
derived from a run's OWN verified vulnerability claims (validate/vulnerabilities.py),
instead of scenarios.py's hand-authored, spec-decoupled demo storylines.

Audit finding (week 6): scenarios.py's three demo storylines only reuse a
run's base_spec to *generate* a VM the same way any other run would - they
were never built from what that VM's role actually, verifiably did. Their
artefact lists (which log entries, which files, which timestamps) were
fixed at authoring time, entirely independent of whatever claims that
particular generation run happened to produce. For idea 3's own framing
("forensic scenario for the generated VM," not a separate track) that's a
real gap, not a cosmetic one - it means a storyline could describe an
"attacker" entering through a misconfiguration the VM in the same run
folder never actually had. This module closes it for the one thing a
narrative most needs to get right: the entry vector. Everything that
happens *after* entry (archiving data, clearing history, exfiltrating) is
still generic - that part of the story doesn't depend on which specific
misconfiguration let the attacker in, so genericity there isn't a gap in
the same sense. See docs/METHODOLOGY.md (week 6).
"""

import re
from datetime import datetime, timedelta

from ..validate.vulnerabilities import VulnerabilityFinding, VulnerabilityReport
from . import generators as gen
from .storyline import Artefact, Storyline

# Keyword -> (service label used in the log line, human description used in
# the narrative). Matched against the claim text, its backtick directive,
# and the task name that applied it - whichever of those actually mentions
# the vulnerability's own subject. Order matters: more specific patterns
# (ssh directive names) are checked before generic ones so e.g. a firewall
# rule that happens to mention "ssh" in passing doesn't get misclassified.
_ENTRY_VECTORS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"permitrootlogin|passwordauthentication|sshd|\bssh\b", re.IGNORECASE), "sshd",
     "a weakened SSH configuration"),
    (re.compile(r"telnet", re.IGNORECASE), "telnetd",
     "the still-enabled Telnet service - an unencrypted, legacy remote-access protocol"),
    (re.compile(r"postgres|pg_hba|listen_addresses|\bmysql\b|\bdatabase\b", re.IGNORECASE), "database",
     "the database service, left reachable over the network with no authentication required"),
    (re.compile(r"\bufw\b|firewall|iptables", re.IGNORECASE), "firewall",
     "an overly permissive firewall rule"),
    (re.compile(r"vsftpd|anonymous_enable|\bftp\b", re.IGNORECASE), "vsftpd",
     "the FTP service, left open to anonymous access"),
    (re.compile(r"apache|nginx|httpd|directory.?listing|admin.?panel|\bhttp\b", re.IGNORECASE), "apache2",
     "the web server, left with an exploitable misconfiguration"),
    (re.compile(r"sudoers|\bsuid\b|setuid|privilege.?escalation", re.IGNORECASE), "sudo",
     "a privilege-escalation path left open in the system's own permission configuration"),
    (re.compile(r"openssl|unattended.?upgrades?|apt.?daily|outdated|unpatched|dpkg_selections", re.IGNORECASE), "apt",
     "an outdated, unpatched package left unaddressed by automatic updates"),
    (re.compile(r"auditd|rsyslog|\bsyslog\b|audit.?log|logging", re.IGNORECASE), "auditd",
     "the system's own audit logging, left disabled or misdirected"),
]

# The fallback for a claim that matches none of the categories above.
# Deliberately does NOT embed the claim's own text (finding.claim can be a
# full explanatory sentence, not a short phrase) - confirmed as a real bug
# against a live vsftpd run, whose claim had no category match: the
# narrative repeated the entire claim sentence twice, once from this
# description and again from `specific` in the narrative below, reading
# as a garbled, doubled mess. `specific` alone already carries the exact
# verified text; this description only needs to name the *category* as
# unclassified, not restate the claim.
_GENERIC_ENTRY_DESCRIPTION = "a misconfiguration this run's own generation claimed to apply"

# service label -> what the fictional business plausibly uses this machine
# for, tying generators.fictional_business_context()'s backstory to the
# actual entry vector rather than a generic "runs a server" sentence -
# see _business_backstory() below.
_BUSINESS_FUNCTIONS: dict[str, str] = {
    "sshd": "let staff remotely access the office server",
    "vsftpd": "share files with clients and suppliers over FTP",
    "apache2": "host their public-facing website",
    "database": "store customer and order records in a database",
    "telnetd": "manage an older piece of shop equipment over the network",
    "firewall": "run their day-to-day office server",
    "sudo": "run their day-to-day office server",
    "apt": "run their day-to-day office server",
    "auditd": "run their day-to-day office server",
    "session": "run their day-to-day office server",
}


def _classify_entry_vector(finding: VulnerabilityFinding) -> tuple[str, str]:
    haystack = " ".join(filter(None, [finding.claim, finding.directive, finding.task_name]))
    for pattern, service, description in _ENTRY_VECTORS:
        if pattern.search(haystack):
            return service, description
    return "session", _GENERIC_ENTRY_DESCRIPTION


def _business_backstory(service: str) -> str:
    """A short scene-setting sentence naming a fictional small business and
    why it runs this particular machine - gives the narrative a concrete
    "who" instead of describing a bare VM. See
    generators.fictional_business_context()'s own docstring: fully
    fabricated, same synthetic-only standard as every other generator this
    module uses."""
    context = gen.fictional_business_context()
    function = _BUSINESS_FUNCTIONS.get(service, _BUSINESS_FUNCTIONS["session"])
    return (
        f"{context.name}, a small {context.business_type}, uses this machine to {function}. "
        f"{context.admin_name} looks after IT part-time, alongside their regular role."
    )


def _entry_artefact(service: str, description: str, when: datetime, user: str) -> Artefact:
    event = "Accepted password" if service == "sshd" else "session opened"
    content = gen.service_log_entry(service, event, when, user=user)
    return Artefact(
        kind="log_entry",
        description=f"Entry via {description}",
        target_path="/var/log/auth.log",
        content=content,
    )


def build_storyline_from_vulnerabilities(
    vulnerability_report: VulnerabilityReport,
    spec: str,
    run_id: str,
) -> Storyline:
    """Pick this run's entry vector from its OWN verified, attributable
    vulnerability claims, and build a narrative + artefact set around it.

    Only a finding that is verifiable, actually true on the live VM, AND
    attributed to this run's own role (attribution == "changed") qualifies
    as an entry vector - the same bar test_deploy.py's config_verified
    already applies. A claim that's merely "ok" (true, but already true
    before this run applied anything) is exactly the week 3 PermitRootLogin
    situation that started this whole thread; building a storyline around
    one would repeat that mistake one layer up, just with a narrative
    instead of a validation report making the unproven claim. Raises
    ValueError rather than silently falling back to a generic,
    spec-decoupled story when no such finding exists.
    """
    entry = next(
        (f for f in vulnerability_report.findings
         if f.verifiable and f.actual and f.attribution == "changed"),
        None,
    )
    if entry is None:
        raise ValueError(
            "no verified, attributable vulnerability claim found for this run - "
            "cannot build a storyline whose entry vector is actually true. Run "
            "`verify-vulnerabilities` first and check its findings."
        )

    service, description = _classify_entry_vector(entry)
    # The category description (e.g. "a weakened SSH configuration") is
    # deliberately generic - it must never assert a specific sub-detail
    # (e.g. "root login left enabled") that this particular finding didn't
    # actually verify. Confirmed as a real bug against a live run: an
    # earlier version of this description named root-login/password-auth
    # specifically, and got attached to a run whose *only* verified,
    # attributable SSH claim was actually `Port 2222` (PermitRootLogin was
    # true but attributed "ok" - already true before this run, exactly the
    # week 3 gap - so it correctly wasn't picked as the entry vector, but
    # the narrative text still claimed it was). `specific` below is what
    # keeps the narrative honest regardless of which claim within a
    # category actually qualified. See docs/METHODOLOGY.md (week 6).
    specific = entry.directive or entry.claim
    user = gen.fake.user_name()
    intrusion_time = datetime(2026, 8, 15, 2, 30, 0)

    narrative = (
        f"{_business_backstory(service)} "
        f"A training VM provisioned for '{spec}' was found accessed outside normal hours. "
        f"This run's own generated role deliberately applied {description} - specifically, "
        f"{specific!r} (task: {entry.task_name!r}) - verified live against the booted VM and "
        f"confirmed by Ansible's own output to have been caused by this run's provisioning, "
        f"not a pre-existing default. Investigators believe this is how the intrusion "
        f"occurred, and are looking for evidence of what happened afterward."
    )

    artefacts = [
        _entry_artefact(service, description, intrusion_time, user),
        Artefact(
            kind="shell_history",
            description="Archiving data shortly after the intrusion",
            target_path="/home/vagrant/.bash_history",
            content=gen.shell_command_archive(),
        ),
        Artefact(
            kind="shell_history",
            description="Copying the archive off the machine",
            target_path="/home/vagrant/.bash_history",
            content=gen.shell_command_exfiltration(),
        ),
        Artefact(
            kind="shell_history",
            description="Attempting to clear shell history afterward",
            target_path="/home/vagrant/.bash_history",
            content=gen.shell_command_history_clear(),
        ),
    ]

    return Storyline(
        id=f"derived-{run_id}",
        title=f"Intrusion via {description}",
        narrative=narrative,
        base_spec=spec,
        artefacts=artefacts,
    )
