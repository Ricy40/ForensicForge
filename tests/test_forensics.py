import re
from datetime import datetime, timezone

import pytest
import yaml

from conftest import model_available
from forensicforge import config
from forensicforge.forensics import generators as gen
from forensicforge.forensics.planter import derive_checks_from_storyline, write_artefact_role
from forensicforge.forensics.scenarios import ALL_SCENARIOS
from forensicforge.forensics.storyline import Artefact, Storyline

# --- generators.py: shape checks only (content is Faker-randomized) ---

def test_shell_command_exfiltration_looks_like_scp():
    assert re.match(r"^scp \S+ \S+@\S+:\S+$", gen.shell_command_exfiltration())


def test_auth_log_entry_has_expected_shape():
    when = datetime(2026, 1, 5, 2, 30, 0)
    line = gen.auth_log_entry("Accepted publickey", when, user="jdoe", source_ip="10.0.0.5")
    assert line.startswith("Jan 05 02:30:00 ")
    assert "Accepted publickey for user jdoe from 10.0.0.5" in line


def test_email_draft_has_headers_and_body():
    text = gen.email_draft("Test subject", "Test body", sender="a@example.com", recipient="b@example.com")
    assert "From: a@example.com" in text
    assert "To: b@example.com" in text
    assert "Subject: Test subject" in text
    assert text.rstrip().endswith("Test body")


def test_fake_client_records_csv_has_header_and_row_count():
    csv_text = gen.fake_client_records_csv(rows=3)
    lines = csv_text.strip().splitlines()
    assert lines[0] == "id,name,email,phone,account_ref"
    assert len(lines) == 4  # header + 3 rows


# --- planter.py: task/check generation per artefact kind ---

def _tasks_and_checks(artefact: Artefact, tmp_path):
    storyline = Storyline(id="t", title="t", narrative="t", base_spec="t", artefacts=[artefact])
    role_dir = write_artefact_role(storyline, tmp_path)
    tasks = yaml.safe_load((role_dir / "tasks" / "main.yml").read_text(encoding="utf-8"))
    checks = derive_checks_from_storyline(storyline)
    return tasks, checks


def test_log_entry_artefact_produces_blockinfile_task_and_grep_check(tmp_path):
    artefact = Artefact(kind="log_entry", description="Suspicious login", target_path="/var/log/auth.log", content="fake log line")
    tasks, checks = _tasks_and_checks(artefact, tmp_path)

    # tasks[0] ensures /var/log exists first (see _ensure_dir_task) -
    # applied to every file-writing artefact kind, not just ones that
    # currently need it, after a deleted_file artefact whose parent
    # directory genuinely didn't exist failed in a real test-deploy run.
    # blockinfile (not lineinfile) even for a single artefact: log_entry/
    # shell_history artefacts targeting the same file are always batched
    # into one atomic write - see _build_line_artefacts_block's docstring
    # for why (multiple sequential lineinfile writes to the same file
    # were found not to reliably all survive in a real test-deploy run).
    assert len(tasks) == 2
    assert tasks[1]["name"] == "Plant 1 log_entry entries in /var/log/auth.log"
    assert tasks[1]["ansible.builtin.blockinfile"]["block"] == "fake log line"
    assert tasks[1]["ansible.builtin.blockinfile"]["mode"] == "0644"

    assert len(checks) == 1
    assert checks[0].task_name == "Plant 1 log_entry entries in /var/log/auth.log"
    assert checks[0].expected == "fake log line"
    assert "grep -F" in checks[0].command


def test_shell_history_artefact_uses_private_mode(tmp_path):
    artefact = Artefact(kind="shell_history", description="Bad command", target_path="/home/vagrant/.bash_history", content="rm -rf /data")
    tasks, _ = _tasks_and_checks(artefact, tmp_path)

    assert tasks[1]["ansible.builtin.blockinfile"]["mode"] == "0600"


def test_multiple_line_artefacts_to_same_file_batch_into_one_task(tmp_path):
    """The fix for the "only the last write survived" bug: N artefacts
    targeting the same file produce one blockinfile task (not N lineinfile
    tasks), but still N individual verification checks."""
    artefacts = [
        Artefact(kind="shell_history", description="cmd 1", target_path="/home/vagrant/.bash_history", content="tar -czf a.tar.gz /data"),
        Artefact(kind="shell_history", description="cmd 2", target_path="/home/vagrant/.bash_history", content="scp a.tar.gz user@host:/"),
        Artefact(kind="shell_history", description="cmd 3", target_path="/home/vagrant/.bash_history", content="history -c"),
    ]
    storyline = Storyline(id="t", title="t", narrative="t", base_spec="t", artefacts=artefacts)
    role_dir = write_artefact_role(storyline, tmp_path)
    tasks = yaml.safe_load((role_dir / "tasks" / "main.yml").read_text(encoding="utf-8"))
    checks = derive_checks_from_storyline(storyline)

    blockinfile_tasks = [t for t in tasks if "ansible.builtin.blockinfile" in t]
    assert len(blockinfile_tasks) == 1
    block = blockinfile_tasks[0]["ansible.builtin.blockinfile"]["block"]
    assert block == "tar -czf a.tar.gz /data\nscp a.tar.gz user@host:/\nhistory -c"

    assert len(checks) == 3
    assert {c.expected for c in checks} == {"tar -czf a.tar.gz /data", "scp a.tar.gz user@host:/", "history -c"}
    assert all(c.task_name == blockinfile_tasks[0]["name"] for c in checks)


def test_deleted_file_artefact_verifies_absence(tmp_path):
    artefact = Artefact(kind="deleted_file", description="Exported records", target_path="/tmp/records.csv", content="id,name\n1,x\n")
    tasks, checks = _tasks_and_checks(artefact, tmp_path)

    assert [t["name"] for t in tasks] == ["Ensure /tmp exists", "Exported records (write)", "Exported records (delete)"]
    assert tasks[2]["ansible.builtin.file"] == {"path": "/tmp/records.csv", "state": "absent"}

    assert len(checks) == 1
    assert checks[0].task_name == "Exported records (delete)"
    assert checks[0].expected == "CONFIRMED_ABSENT"


def test_backdated_file_artefact_computes_utc_epoch_and_sets_changed_when(tmp_path):
    artefact = Artefact(
        kind="backdated_file", description="Old note", target_path="/tmp/note.txt",
        content="hi", timestamp="2026-01-01T00:00:00",
    )
    tasks, checks = _tasks_and_checks(artefact, tmp_path)

    touch_task = tasks[2]
    assert touch_task["name"] == "Old note (backdate)"
    assert touch_task["changed_when"] is True
    assert "touch -d '2026-01-01T00:00:00Z'" in touch_task["ansible.builtin.command"]

    expected_epoch = str(int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()))
    assert checks[0].expected == expected_epoch
    assert checks[0].command == "sudo stat -c %Y /tmp/note.txt"


def test_backdated_file_artefact_requires_timestamp(tmp_path):
    artefact = Artefact(kind="backdated_file", description="No timestamp", target_path="/tmp/x", content="x")
    with pytest.raises(ValueError, match="needs a timestamp"):
        _tasks_and_checks(artefact, tmp_path)


def test_email_draft_check_targets_subject_line_not_full_body(tmp_path):
    artefact = Artefact(
        kind="email_draft", description="Draft", target_path="/home/vagrant/Drafts/x.eml",
        content="From: a@example.com\nTo: b@example.com\nSubject: Leaving soon\n\nBody text.\n",
    )
    _, checks = _tasks_and_checks(artefact, tmp_path)

    assert checks[0].expected == "Subject: Leaving soon"


def test_playbook_references_both_scenario_and_artefact_roles(tmp_path):
    artefact = Artefact(kind="log_entry", description="x", target_path="/var/log/auth.log", content="x")
    storyline = Storyline(id="t", title="t", narrative="t", base_spec="t", artefacts=[artefact])
    write_artefact_role(storyline, tmp_path, scenario_role_name="my_scenario")

    playbook = (tmp_path / "playbook.yml").read_text(encoding="utf-8")
    assert "- my_scenario" in playbook
    assert "- forensic_artefacts" in playbook


# --- scenarios.py: demo storylines are well-formed ---

def test_all_demo_scenarios_are_distinct_and_have_artefacts():
    assert len(ALL_SCENARIOS) == 3
    titles = {s.title for s in ALL_SCENARIOS.values()}
    assert len(titles) == 3  # genuinely distinct narratives, not near-duplicates
    for storyline in ALL_SCENARIOS.values():
        assert storyline.artefacts
        assert storyline.narrative
        assert storyline.base_spec


def test_all_demo_scenario_artefacts_build_without_error():
    for storyline in ALL_SCENARIOS.values():
        checks = derive_checks_from_storyline(storyline)
        assert len(checks) == len(storyline.artefacts)


# --- orchestrator.py: needs a live LLM, skipped otherwise ---

pytestmark_ollama = pytest.mark.skipif(
    not (model_available(config.MODEL_NAME) and model_available(config.EMBEDDING_MODEL)),
    reason="Ollama not running or required models not pulled",
)


@pytestmark_ollama
def test_provision_storyline_writes_both_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GENERATED_DIR", tmp_path)
    from forensicforge.forensics.orchestrator import provision_storyline

    storyline = ALL_SCENARIOS["departing-employee-exfiltration"]
    result = provision_storyline(storyline)

    assert result.provision.role_dir.exists()
    assert result.artefact_role_dir.exists()
    assert result.artefact_role_dir.name == "forensic_artefacts"
