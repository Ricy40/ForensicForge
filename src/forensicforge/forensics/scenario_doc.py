"""Write scenario.md: a human-readable summary of a storyline plus its
verified vulnerabilities, meant to be read (or lifted near-verbatim into a
dissertation) rather than parsed - the narrative deliverable build-scenario
produces alongside the machine-readable report.json/storyline.json.
"""

from pathlib import Path

from ..validate.vulnerabilities import VulnerabilityReport
from .storyline import Storyline

SCENARIO_FILENAME = "scenario.md"


def _mark(finding) -> str:
    if not finding.verifiable:
        return "Not verifiable"
    if finding.actual is None:
        return "Not checked (boot failed)"
    return "Confirmed true" if finding.actual else "Confirmed false"


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_scenario_markdown(storyline: Storyline, vulnerability_report: VulnerabilityReport) -> str:
    lines = [f"# {storyline.title}", "", storyline.narrative, "", "## Vulnerabilities", ""]

    if not vulnerability_report.findings:
        lines.append("No claimed vulnerabilities were recorded for this run.")
    else:
        lines.append("| Claim | Status | Attribution | Note |")
        lines.append("|---|---|---|---|")
        for finding in vulnerability_report.findings:
            attribution = finding.attribution or "-"
            lines.append(
                f"| {_escape_cell(finding.claim)} | {_mark(finding)} | {attribution} | "
                f"{_escape_cell(finding.note)} |"
            )

    lines.append("")
    return "\n".join(lines)


def write_scenario_markdown(storyline: Storyline, vulnerability_report: VulnerabilityReport, run_dir: Path) -> Path:
    path = run_dir / SCENARIO_FILENAME
    path.write_text(render_scenario_markdown(storyline, vulnerability_report), encoding="utf-8")
    return path
