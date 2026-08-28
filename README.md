# ForensicForge

LLM-driven pipeline for generating curriculum-aligned virtual machines and
AI-driven forensic training scenarios.

**Week 1 scope:** environment + scaffold. Given a plain-English spec, prove
the round trip to a local LLM and back.

**Week 2 scope:** retrieval-augmented generation. Ground that output in a
small curated knowledge corpus and steer it from free-text prose toward a
draft Ansible task list.

**Week 3 scope:** Packer/Vagrant/Ansible provisioning. Parse a generated
task list into a real Ansible role, generate a Vagrantfile for it, and boot
a real VM.

**Week 4 scope:** scanning, gating, and automated test-deploy. Static
validation (`python-hcl2`, `ansible-lint`, Checkov) and Molecule role
verification, both wired into CI; `python-vagrant` replaces the manual
`vagrant up` from week 3 with a scripted boot → verify → destroy cycle; a
`report.json` per run captures the results. See
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) for the full design rationale,
including why `ansible-lint`/Molecule need WSL on Windows, the Docker-vs-
Vagrant Molecule driver decision, and an honest limitation on what Checkov
actually catches.

## Project structure

```
knowledge/
    sshd_config/            Real sshd_config directives (one per file)
    ansible_tasks/          Example Ansible tasks for common services
    misconfigurations/      Vulnerability patterns with a "why" note
packer/
    ubuntu-base.pkr.hcl      Custom base box template (built, not yet wired in)
    http/                    cloud-init autoinstall files for the above
src/forensicforge/
    llm/
        base.py             LLMBackend interface (ABC)
        ollama_backend.py   Ollama implementation of LLMBackend
    rag/
        embeddings.py       Local embedding model (Ollama)
        vectorstore.py      Persistent Chroma store built from knowledge/
        retriever.py        Top-k retrieval over the vector store
        chain.py            retrieve -> compose prompt -> LLMBackend.generate
    provision/
        ansible_writer.py    Parse RAG output into a validated Ansible role
        vagrantfile_writer.py  Generate a per-run Vagrantfile
        molecule_writer.py   Generate a per-run Molecule scenario (Vagrant driver)
        orchestrator.py      RAG -> role -> Vagrantfile -> Molecule scenario
    validate/
        hcl_check.py         Structural validation of the Packer template
        scanners.py          ansible-lint + Checkov, normalized to one result shape
        molecule_runner.py   Runs `molecule test` for a generated role
        test_deploy.py       python-vagrant boot -> verify -> destroy cycle
        wsl_bridge.py         Runs POSIX-only tools via WSL on Windows
        report.py             Builds/aggregates report.json across runs
    config.py               Ollama/RAG/provisioning/validation settings
    prompts.py              Prompt templates (RAG and week-1 ungrounded)
    service.py              Shared generate_vm_spec() used by API and CLI
    api.py                  FastAPI app (POST /generate)
    cli.py                  click CLI: generate/provision/validate/test-deploy/...
scripts/
    check_ollama.py         Verifies Ollama has both a code and embedding model
    check_wsl_tools.py       Verifies WSL has ansible-lint + Molecule installed
    ci_scan.py                Entry point CI uses to scan the fixture role
tests/
    test_smoke.py           End-to-end smoke test (RAG path)
    test_rag.py             Retrieval + RAG-vs-ungrounded comparison
    test_provision.py       Ansible role parsing/writing (no Ollama needed)
    test_validate.py        Scanners/report/test-deploy helpers (no Ollama needed)
    fixtures/example_role/  A real generated role, checked in for CI to scan
.github/workflows/
    validate.yml             CI: static scans + Molecule (Docker driver), no boot
generated/                  Output of `provision` runs (gitignored), one dir per run-id
```

Design rationale (the `src/` layout, the `LLMBackend` ABC, the vector
store/embedding model choice, the parsing approach, the Packer/stock-box
decision, and this week's scanning/Molecule/CI design) is written up in
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) rather than duplicated here.

## 1. Install dependencies

A virtual environment already exists at `.venv/`. Activate it and install
the project in editable mode:

```bash
.venv/Scripts/activate
pip install -e ".[dev]"
```

You'll also need, separately (none are Python dependencies `pip install`
covers):

- [Vagrant](https://developer.hashicorp.com/vagrant/downloads) and a
  provider (this project uses Hyper-V on Windows - see
  `docs/METHODOLOGY.md` for why, not VirtualBox) for `vagrant up` /
  `test-deploy`.
- WSL2, with `ansible-lint` and Molecule installed *inside* it (separate
  from this venv) for the `validate` command's `ansible-lint`/Molecule
  checks to run on Windows. Run `python scripts/check_wsl_tools.py` to
  check and be prompted before anything is installed.

## 2. Start Ollama and check for models

Make sure the Ollama app is running (or run `ollama serve`), then:

```bash
python scripts/check_ollama.py
```

This checks that Ollama is installed and running, lists installed models,
and - if either a code-capable model or an embedding model is missing -
suggests a few options and asks before pulling anything. It never
downloads a model silently.

Defaults: `qwen2.5-coder:7b` for generation, `nomic-embed-text` for
embeddings. Override with `FORENSICFORGE_MODEL` /
`FORENSICFORGE_EMBEDDING_MODEL`, and `FORENSICFORGE_OLLAMA_HOST` if Ollama
isn't on the default `localhost:11434`.

The first RAG request builds a persistent Chroma vector store from
`knowledge/` at `.chroma/` (gitignored). If you edit the corpus, delete
`.chroma/` to force a rebuild.

## 3. Run the API

```bash
uvicorn forensicforge.api:app --reload
```

Then, from another terminal:

**bash / Git Bash:**

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"spec": "Ubuntu server VM with a deliberately weak SSH config for a pentesting exercise"}'
```

**PowerShell:** `curl` is aliased to `Invoke-WebRequest` there, which doesn't
accept curl-style flags or `\` line continuations. Use `Invoke-RestMethod`
instead:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/generate -Method Post -ContentType "application/json" -Body '{"spec": "Ubuntu server VM with a deliberately weak SSH config for a pentesting exercise"}'
```

The response is `{"output": "...", "snippets": [{"source": "...", "content": "..."}]}` -
`snippets` lists the corpus documents retrieved for that request, so it's
traceable which piece of grounding influenced the output. Pass
`"use_rag": false` in the request body to get the week-1 ungrounded prompt
instead (no retrieval, `snippets` comes back empty) - useful for comparing
grounded vs ungrounded output. The API doesn't expose `provision`/
`validate`/`test-deploy` yet - those are CLI-only.

## 4. Run the CLI

```bash
# print raw generated output (like week 1/2)
forensicforge generate "Ubuntu server VM with a deliberately weak SSH config for a pentesting exercise"
forensicforge generate --no-rag "..."   # week-1 ungrounded prompt instead

# parse that output into a real Ansible role + Vagrantfile + Molecule scenario
forensicforge provision "Ubuntu server VM with a deliberately weak SSH config for a pentesting exercise"

# static scans (checkov, ansible-lint) + Molecule, against a provisioned run - CI-safe
forensicforge validate generated/<run-id>

# boot -> verify config -> destroy, automatically - needs an elevated terminal (Hyper-V)
forensicforge test-deploy generated/<run-id>

# structurally check the Packer template
forensicforge check-packer

# aggregate report.json across every run into pass rates
forensicforge report-summary
```

`provision` writes `generated/<run-id>/` (`Vagrantfile`, `playbook.yml`,
`roles/<role-name>/`, `roles/<role-name>/molecule/default/`) and prints
what to run next - it does not boot or scan anything itself. If the LLM
output can't be parsed into a valid task list, nothing is written; you get
the parse error and the raw LLM output instead, on stderr.

`validate` and `test-deploy` both write/update `generated/<run-id>/report.json`.
Neither requires the other to have run first.

(`python -m forensicforge.cli ...` also works if the `forensicforge` entry
point isn't on your PATH.)

## 5. Boot and verify the generated VM

Automatically (replaces the manual steps below):

```bash
forensicforge test-deploy generated/<run-id>
```

Boots the VM, greps the config each `lineinfile` task claims to have
applied out of the file it claims to have applied it to (mirroring the
manual week-3 check), then always destroys the VM afterward - even if a
check fails. Needs an elevated terminal on this machine (Hyper-V provider
requirement).

Manually, if you'd rather watch each step:

```bash
cd generated/<run-id>
vagrant up
vagrant ssh -c "sudo grep -i permitrootlogin /etc/ssh/sshd_config"
vagrant destroy
```

First boot downloads the `generic/ubuntu2004` box (if not already cached)
and takes a few minutes - `ansible_local` also has to install Ansible
inside the guest before it can provision itself. Deleting the
`generated/<run-id>/` directory afterward leaves no trace, since each run
is self-contained.

## 6. Run the tests

```bash
pytest
```

- `test_smoke.py` / `test_rag.py` need Ollama running with both models
  pulled; skipped automatically (with a clear reason) otherwise.
- `test_provision.py` / `test_validate.py` need nothing external - they
  run every time, including in CI.

None of them check output *quality*, or boot a VM - only that the plumbing
works. `.github/workflows/validate.yml` runs the Ollama-independent tests
plus static scans and Molecule (Docker driver, against a checked-in
fixture role) on every push - see `docs/METHODOLOGY.md` for why the full
`test-deploy` boot cycle stays local-only.
