# Methodology

This is a living design record for the ForensicForge dissertation project,
updated at the end of each implementation week. It explains what exists,
why it is shaped the way it is, and which trade-offs were made deliberately
rather than by accident. It is written for the methodology and
implementation chapters of the dissertation, so it favours honesty about
limitations over making the current state sound more finished than it is.

## What the project is

ForensicForge is an LLM-driven pipeline that turns a plain-English request
("Ubuntu server VM with a deliberately weak SSH config for a pentesting
exercise") into a curriculum-aligned virtual machine definition and,
eventually, an AI-driven forensic training scenario built around it. The
end state, six weeks out, is a pipeline that generates a VM specification,
grounds and structures that specification well enough to hand to
provisioning tooling (Packer/Vagrant/Ansible), validates it against security
and correctness gates, and boots it automatically. Each week adds one stage
of that pipeline rather than building the whole thing shallowly up front,
so that every stage is something that actually runs before the next one is
added on top of it.

## Week 1: environment and scaffold

The first week's goal was narrow on purpose: prove that a plain-English
spec can round-trip through a local LLM and come back as text, with a
project structure that would not need to be reorganised as later weeks
added retrieval, provisioning, and validation on top.

**Why a `src/` layout.** The installable package lives under `src/forensicforge/`
rather than at the repository root. This is a well-worn Python convention
specifically because it stops the package from being importable by
accident from the repository root (a common source of "works on my machine"
bugs where a script one directory up masks the installed package). The
package is installed editable (`pip install -e .`), so `src/`, `scripts/`,
`tests/`, and `docs/` all import the same code the same way, and there is
never a question of which copy of the code is running.

**Why an `LLMBackend` abstract base class.** The project is constrained to a
local Ollama instance for now, but that constraint is expected to lift —
the dissertation's evaluation chapter will likely want to compare local and
hosted models. Rather than sprinkling `ollama.Client()` calls through the
API, CLI, and (as of week 2) the RAG chain, every one of those call sites
depends on `LLMBackend.generate(prompt: str) -> str`, and `llm/get_backend()`
is the single function that decides which concrete backend to instantiate.
Adding a hosted backend later means writing one new class and changing one
factory function; it does not mean re-touching every place that currently
calls Ollama.

**Why FastAPI + a thin CLI over the same shared function.** Both `api.py`
and `cli.py` call `service.generate_vm_spec()` rather than each
re-implementing "build a prompt, call the backend." This was a deliberate
choice to keep the CLI a *convenience wrapper*, not a second code path —
if the underlying generation logic changes, there is exactly one place to
change it, and the two interfaces cannot silently drift apart.

**Why the `ollama` Python client instead of raw HTTP.** `localhost:11434/api/generate`
is a plain REST endpoint and could have been called with `requests` or the
standard library directly. The official `ollama` package wraps the same
endpoint and saves hand-rolling request/response JSON handling and error
cases (e.g. model-not-pulled errors), for the cost of one extra dependency
that is already a first-party, actively maintained package.

## Week 2: retrieval-augmented generation

Week 1's output, given the SSH pentesting spec, was fluent prose that
*sounded* plausible but was not grounded in any real `sshd_config` syntax
and was not structured enough for anything downstream to parse. Week 2's
goal was to fix both problems: ground the output in a small curated corpus
of real configuration knowledge, and change the output shape from prose to
something closer to a provisioning artifact.

### The knowledge corpus

The corpus lives under `knowledge/`, as 26 short markdown documents split
into three categories:

- **`knowledge/sshd_config/`** (11 documents) — one real `sshd_config`
  directive per file (`PermitRootLogin`, `PasswordAuthentication`,
  `PermitEmptyPasswords`, `MaxAuthTries`, `AllowTcpForwarding`,
  `X11Forwarding`, `ClientAliveInterval`/`ClientAliveCountMax`, weak
  `Ciphers`/`KexAlgorithms`, `Port`, `LoginGraceTime`, and
  `PubkeyAuthentication`), each stating what it does and, where relevant,
  why a particular setting is a real vulnerability.
- **`knowledge/ansible_tasks/`** (7 documents) — short, valid Ansible task
  snippets for the operations a generated scenario will actually need:
  installing/enabling OpenSSH, setting individual `sshd_config` directives
  with `lineinfile` versus templating the whole file, restarting `sshd` via
  a handler, managing `ufw` firewall rules (and deliberately disabling
  them), creating a user with a set password, and installing a package
  generically (including pinning an outdated version on purpose).
- **`knowledge/misconfigurations/`** (8 documents) — broader vulnerability
  patterns not specific to SSH, each with a one-line "why this is real"
  justification: open/allow-all firewalls, default or weak credentials,
  unencrypted telnet/FTP, world-writable files, unpatched packages,
  unauthenticated exposed databases, and disabled audit logging.

This split (directive knowledge / provisioning knowledge / vulnerability
rationale) was deliberate: a single generated scenario typically needs a
directive-level fact ("what does `PermitRootLogin` do"), a provisioning
fact ("what does the Ansible task that sets it look like"), and a framing
fact ("why is this combination a real weakness worth teaching") — keeping
those as separate retrievable units means the retriever can pull exactly
the ones relevant to a given spec instead of always pulling one large
mixed document. One document per fact also keeps each embedding vector
representing one coherent idea, rather than an under- or over-broad
mixture, which is the standard argument for small retrieval units in RAG
system design.

This is a first-pass set focused on the SSH pentesting example used
throughout weeks 1–2. It does not yet cover other service families
(web servers, databases beyond the one exposed-database note, Windows/AD
misconfigurations) — that is expected to grow as more scenario types are
exercised in later weeks, and is worth a deliberate coverage review rather
than silently expanding.

### Embeddings and vector store

**Why `nomic-embed-text`.** Ollama's embedding model library was checked
directly rather than assumed (model recommendations age quickly). At time
of writing, `nomic-embed-text` remains the most widely used local embedding
model on Ollama by a large margin, is a comparatively small download
(~274 MB against ~670 MB for `mxbai-embed-large` or ~1.2 GB for `bge-m3`),
and supports a large (8192-token) context window — more headroom than our
current short corpus documents need, but useful if later weeks' corpus
documents grow longer. It was pulled the same way `check_ollama.py`
already handled the generation model: checked for, listed as one of a few
reasonable options, and only pulled after an explicit yes.

**Why Chroma.** The brief for this week explicitly favoured "no server
dependency," which ruled out Qdrant, Weaviate, and Milvus in their typical
deployment form (a running service/container). That leaves an embedded
choice between Chroma and FAISS. Chroma was chosen because it has a
first-party LangChain integration (`langchain-chroma`) that manages
documents, metadata, and embeddings together as a single persistent
on-disk store; FAISS's LangChain wrapper is a thinner layer over a
similarity-search index and leaves more of the docstore/metadata
bookkeeping to the caller. For a corpus this size (26 documents), that
difference does not matter much yet, but it will as the corpus grows to
cover more scenario types — Chroma's approach is the one that scales
without extra plumbing. The persisted store lives at `.chroma/` (gitignored,
like any other build artifact) and is rebuilt automatically the first time
it doesn't exist; there is currently no staleness check against edits to
`knowledge/`, so editing the corpus requires deleting `.chroma/` by hand to
force a rebuild. That is a known gap, not an oversight — a hash-based
staleness check is a reasonable week 3+ addition once the corpus is large
enough that rebuilding on every run would be wasteful.

### LangChain's role, and where it deliberately stops

LangChain is used for the retrieval half of the pipeline only:
`langchain_core.documents.Document` for the corpus items,
`langchain_chroma.Chroma` for the vector store, and its `.as_retriever()`
interface for top-k similarity search. Generation still goes through the
project's own `LLMBackend.generate()` from week 1, not through LangChain's
`ChatModel`/LCEL abstractions. This was a deliberate line, not an
oversight: `LLMBackend` is already the seam intended for swapping models
and providers later, and wrapping generation in a second, competing
abstraction (a LangChain `Runnable` chain ending in a chat model) would
mean two different places claiming ownership of "how a prompt becomes
text." Using LangChain where it has no such competing concern (loading and
retrieving documents) and leaving generation alone keeps exactly one seam
per concern. `src/forensicforge/rag/chain.py` is consequently a plain
function — retrieve, format a prompt, call the existing backend — rather
than an LCEL pipeline; the orchestration the brief asked for happens in
that function's control flow, not in a `Runnable` object.

Only `langchain-core`, `langchain-ollama`, and `langchain-chroma` are
dependencies, not the umbrella `langchain` package. The umbrella package
additionally pulls in chain/agent implementations for providers and
tools this project does not use; the three integration packages provide
everything the retrieval path needs (`Document`, `OllamaEmbeddings`,
`Chroma`) without that extra surface area.

### Output format: Ansible tasks over a raw config block

The generated output was steered toward a YAML list of Ansible tasks (each
with a `name` and a module such as `ansible.builtin.lineinfile` or
`ansible.builtin.service`), plus a short "applied misconfigurations"
section, rather than a raw `sshd_config` file block. Week 3's stated scope
is Packer/Vagrant/Ansible provisioning, so Ansible tasks are the format
that stage will actually consume directly — a raw `sshd_config` block only
covers one file for one service, whereas a spec might also need firewall
rules, user accounts, or package installs, all of which are naturally
different Ansible modules but the same task-list shape. A single
consistent output format is also easier to validate mechanically in week 4
(`ansible-lint` operates on exactly this shape) than a mix of free-form
config-file syntax that would differ per service.

### RAG over a longer static prompt

An alternative to retrieval would have been to paste the entire corpus
into every prompt. That was rejected for two reasons. First, it does not
scale — the corpus is expected to grow well past 26 documents as later
weeks cover more scenario types, and a static prompt grows (and costs
tokens) with the whole corpus regardless of relevance to the current spec,
while retrieval's cost is bounded by *k* regardless of corpus size. Second,
retrieval is traceable in a way a static prompt is not: because retrieval
happens per-request, the API and CLI can report exactly which corpus
documents were retrieved for a given spec (surfaced as `snippets` in both),
which is useful for debugging bad output and will likely be useful again
in the evaluation chapter when explaining why a given generation looked
the way it did.

### Keeping the ungrounded path available

`generate_vm_spec(spec, use_rag=True)` is the new default, but
`use_rag=False` reproduces the exact week-1 behaviour (`prompts.build_prompt`,
no retrieval). This was kept, rather than deleted, specifically so the
dissertation's evaluation chapter can compare grounded and ungrounded
output for the same spec directly, rather than relying on memory of what
week 1's output looked like. The CLI exposes this as `--no-rag`; the API as
`"use_rag": false` in the request body.

## Week 3: Packer, Vagrant, and Ansible provisioning

Week 2 ended with output that was grounded and shaped like an Ansible task
list, but nothing downstream had ever actually tried to run it. Week 3's
job was to close that gap: turn a generated task list into a real Ansible
role, generate a Vagrantfile that boots a VM and provisions it with that
role, and confirm — on a real machine, not just by reading the generated
files — that the deliberately weak configuration actually lands.

### A naming loose end, tied off first

Before building on top of week 2, the package name was checked end to end
(committed git history, the working tree, and the installed package) after
a discrepancy was noticed between what an earlier week's README said and
what week 2's summary said. All three were already consistent as
`forensicforge` — the `vmforge` name that appeared briefly was a mid-session
rename in an earlier week's chat transcript that was never actually
committed under that name. Worth stating plainly here since a
half-renamed package is exactly the kind of thing that causes confusing
import errors weeks later if it goes unchecked.

### Parsing LLM output into a real Ansible role

`build_rag_prompt()` (week 2) asks the model for a fenced ` ```yaml ` block
followed by an "Applied misconfigurations" section, but asking for a shape
and getting it reliably are different things — nothing before week 3
verified the model actually produced valid YAML, or a valid task list
inside it. `src/forensicforge/provision/ansible_writer.py` adds that check
as an explicit step with three stages, each of which can fail independently
and be attributed to a specific cause: extract the fenced code block with a
regex (`extract_yaml_block`), parse it with `yaml.safe_load`
(`parse_tasks`), and check that the parsed value is a non-empty list of
mappings that each have at least a `name` key. Any failure raises
`AnsibleParseError`, which carries the raw LLM output as an attribute
specifically so the CLI can print exactly what the model produced instead
of a bare "parsing failed" — that matters for a project whose evaluation
chapter will want to know *how often* and *how* generation fails, not just
that it sometimes does. Nothing is written to disk unless all three stages
succeed, so a failed run never leaves a half-written role directory behind
to be mistaken for a working one.

This is deliberately a low bar — "is this a syntactically valid task list
with names" — not real policy validation. `ansible-lint` and Checkov are
explicitly week 4's job and check meaningfully different things (module
argument correctness, security policy compliance) that would be premature
to half-implement here. The point of doing even this much now was the
brief's own framing: garbage-in-garbage-out being silently written to disk
is not acceptable at any stage, even before proper gating exists.

**Why plain PyYAML rather than `ruamel.yaml`.** `ruamel.yaml`'s main
advantage over PyYAML is round-trip fidelity — loading a YAML document,
modifying it, and dumping it back out while preserving comments, key order,
and formatting. That matters when a human-authored YAML file is being
edited programmatically. It does not apply here: the extracted YAML block
is validated and then written to `tasks/main.yml` *verbatim*, as the exact
text the model produced, rather than being parsed into Python objects and
re-serialized. `yaml.safe_load` is used only to check the text is valid and
shaped correctly; its output is discarded once that check passes. Since
there is no load-modify-dump cycle, PyYAML's plain (and already-installed,
as a transitive dependency of other packages) `safe_load` does everything
required, and `ruamel.yaml` would be an added dependency for a capability
this code path doesn't use.

### The generated-directory-per-run structure

Each successful `provision` run writes to `generated/<run-id>/`, where
`run-id` is a timestamp (`YYYYMMDD-HHMMSS`), containing:

```
generated/<run-id>/
    Vagrantfile
    playbook.yml
    roles/
        <role-name>/
            tasks/main.yml
            meta/main.yml
```

Every run gets its own directory rather than overwriting a single
`generated/` output, and every file a `vagrant up` in that directory needs
(the Vagrantfile, the playbook, the role) is self-contained inside it —
nothing references a shared or previous run. That makes each run
independently disposable (`vagrant destroy` plus deleting the directory
leaves no trace) and directly comparable to other runs side by side, which
will matter once week 4 starts running many specs through the pipeline
and needs to keep their outputs apart. `generated/` is gitignored for the
same reason `.chroma/` is: it is a build artifact reproducible from the
spec and the current corpus/prompt, not a source file.

### `ansible_local`, not the host-side `ansible` provisioner

The generated Vagrantfile provisions with Vagrant's `ansible_local`
provisioner, which installs Ansible *inside the guest* on first boot and
runs the playbook there, rather than the `ansible` provisioner, which
expects Ansible to already be installed on the host machine running
`vagrant up`. Ansible does not support running natively on Windows as a
control node (it works under WSL, but requiring WSL as a hard dependency
was rejected to keep the host-side setup to "install Vagrant and a
provider," matching how the project has otherwise avoided host-level
dependencies beyond Ollama). `ansible_local` trades a slower first boot
(the guest has to install Ansible via `pip`/`apt` before it can provision
itself) for zero host-side Ansible dependency, which was judged the right
trade for a dev machine that does not otherwise need Ansible installed at
all.

### Packer vs. a stock box: the trade-off, made explicit

The brief asked directly for this trade-off to be named rather than
decided silently, so: `packer/ubuntu-base.pkr.hcl` builds a minimal Ubuntu
20.04 base box via VirtualBox and cloud-init autoinstall, but the
Vagrantfiles `provision` actually generates this week boot from the stock
`generic/ubuntu2004` box on Vagrant Cloud, not the Packer-built one.

The case for wiring in the Packer box immediately would be fidelity to the
eventual real pipeline — a custom-built base image is what a finished
system would use, since it can bake in exactly the base state (packages,
users, hardening baseline) the project wants every scenario to start from,
rather than inheriting whatever `generic/ubuntu2004`'s maintainers shipped.
The case against, this week specifically, is build time and unverified
risk stacked on top of an already-new part of the pipeline: a Packer build
is a 15–30+ minute unattended OS install that depends on an ISO URL and
checksum staying valid, cloud-init autoinstall behaving as expected, and
Packer's VirtualBox and Vagrant plugins being installed and working — none
of which had been exercised on this machine before this week. (The Packer
CLI binary itself turned out to already be present in the repository root
as a plain downloaded executable, `packer_1.16.0_windows_amd64/packer.exe`,
predating this week's work and unrelated to it — confirmed working
(`packer --version` → `1.16.0`) and added to `.gitignore`, but its plugins
have not been installed and the template has still not actually been run.)
Debugging a broken Packer build and debugging whether a generated Ansible
role behaves correctly are different problems, and this week's actual goal
was the second one: prove a generated role can provision *a* VM correctly.
Using a known-good stock box isolates that question from "does the custom
image build work," rather than debugging both at once the first time
either is tried.

One more consideration this week's actual `vagrant up` surfaced after this
section was first written: `ubuntu-base.pkr.hcl` uses Packer's
`virtualbox-iso` builder, but the dev machine turned out not to be able to
run VirtualBox VMs at all (see "what watching the first boot actually
caught" below) — the generated Vagrantfiles now default to the Hyper-V
provider on this machine instead. A VirtualBox-format box built by the
current template would not be usable there without either running Packer
on a machine that can still run VirtualBox, or retargeting the template at
Packer's `hyperv-iso` builder. This is exactly the kind of thing isolating
the stock-box decision from the custom-image decision was meant to avoid
having to debug simultaneously - noted here for whenever the Packer box
is actually wired in, rather than guessed at now.

The Packer template is consequently built but not run or verified — see
`packer/README.md` for its exact unfinished edges (an ISO checksum that
will need rechecking against whatever Ubuntu 20.04 point release is
current, and a placeholder autoinstall password). Wiring it in is a
short, well-scoped follow-up once it has actually been built and confirmed
to produce a working box: point `config.vm.box` at the registered box name
instead of `generic/ubuntu2004`, which is a one-line change in
`vagrantfile_writer.py`.

### What's automated versus what's still manual

`forensicforge provision "<spec>"` automates every step through writing the
Vagrantfile and role to disk, and prints the exact `cd`/`vagrant up`
command to run next — but it deliberately does not run `vagrant up` itself.
Booting a VM is slow (minutes, not seconds), this is the first week
virtualization is involved at all, and the brief was explicit that the
first boot should be watched rather than automated blind. Full
boot-smoke-test-destroy automation via `python-vagrant` is explicitly
week 4 scope, once there is a validation step worth automating the boot
*around*. Automating a boot loop before there is anything to check beyond
"did it boot" would be automation for its own sake.

### What watching the first boot actually caught

The first real `vagrant up` against a generated run failed immediately,
before any provisioning ran, with `The following settings shouldn't exist:
roles_path`. `vagrantfile_writer.py`'s original template set
`ansible.roles_path = "roles"` on the assumption that `ansible_local`
supported the same `roles_path` option the host-side `ansible` provisioner
does; it doesn't — checked against Vagrant's own documentation afterward,
`roles_path` isn't in `ansible_local`'s options, nor in the set of options
shared between the two provisioners. The fix was to drop the setting
entirely rather than find an equivalent: Ansible already searches for a
`roles/` directory next to the playbook by default, which is exactly the
layout `ansible_writer.py` produces (`playbook.yml` and `roles/` as
siblings under `generated/<run-id>/`), so the option was never needed.

This is precisely the class of mistake unit tests around
`ansible_writer.py` could not have caught — they check that a role
directory is written and shaped correctly, not that Vagrant accepts the
option syntax used to reference it. It is also the concrete justification,
independent of the brief's own reasoning, for not automating `vagrant up`
before a human had watched it succeed at least once: an automated
boot-and-destroy loop would have failed the same way, but silently
folded into "provisioning failed" logs rather than being caught and fixed
in the time it took to read one error message on a real terminal.

With that fixed, the next `vagrant up` failed before Vagrant itself did
anything: `VBoxManage` couldn't lock the newly-created VM
(`E_ACCESSDENIED`). This traced to Windows 11's Memory Integrity
(Core Isolation/HVCI) being active on the dev machine — a documented,
fairly common VirtualBox-on-Windows-11 incompatibility, confirmed by
checking `Win32_DeviceGuard` directly rather than guessed at. The
standard fix is disabling Memory Integrity, but that was explicitly
rejected here: it also gates several kernel-level anti-cheat systems, and
this machine is used for that too. So the provider changed instead of the
security setting - `generic/ubuntu2004` already publishes a Hyper-V
variant, Windows' own hypervisor platform was already active anyway (WSL2
requires it), and the generated Vagrantfile never hardcoded a provider in
the first place, so switching only meant enabling the Hyper-V Windows
feature and passing `--provider=hyperv`. This is worth recording as a
methodological point, not just a fix: a security constraint the user
already holds for an unrelated reason (anti-cheat compatibility)
determined a provisioning-tooling decision. That is a real category of
constraint a deployed version of this pipeline would need to detect or
ask about, not assume away.

Switching providers surfaced a second, independent gap: `ansible_local`
depends on a synced folder to find `playbook.yml` and `roles/` on the
guest (default path `/vagrant`), and Vagrant only wires that synced folder
up automatically for providers with a native shared-folder mechanism -
VirtualBox has one (Guest Additions); Hyper-V doesn't, and needs an
explicit SMB share instead, which meant an interactive prompt for the
host Windows account's actual password (not the Hello PIN normally used
to sign in, which doesn't work for network authentication at all - itself
worth noting as a real point of user friction). Rather than accept that
credential prompt, the Vagrantfile template was changed to stop depending
on synced folders entirely: a `file` provisioner now copies `run_dir`'s
contents to the guest over the SSH connection Vagrant already has and
trusts, and `ansible_local`'s `provisioning_path` points at that copied
location instead of the default `/vagrant`. This works identically
regardless of provider and needs no credentials at all, which in hindsight
is arguably the better default independent of the Hyper-V/VirtualBox
question - depending on a provider-specific synced-folder mechanism was
the fragile choice, not the SSH-based copy every provider already supports
the same way.

That first version of the SSH-copy fix (`source: "."`, copying `run_dir`
wholesale) itself failed on the next real attempt, with a generic
`SCP did not finish successfully` error and no further detail. Two things
were wrong with it, found by checking Vagrant's own file-provisioner
documentation and issue tracker rather than guessing from the error alone:
first, `run_dir` by that point also contained `.vagrant/` (Vagrant's own
per-run state directory, created the moment `vagrant up` first ran) - a
generic recursive copy pulled that in too, including files the running
`vagrant` process itself holds open, which is a plausible way to break an
SCP transfer outright. Second, and independently, Vagrant's file
provisioner is documented as not reliably creating missing *nested* parent
directories on the guest - a single new directory under an already-existing
parent works, but the destination used here needed two new levels
(`/home/vagrant/forensicforge/roles`) created at once. The fix addressed
both: an explicit `shell` provisioner now runs `mkdir -p` on the exact
destination path before anything is copied, and the `file` provisioners
that follow name `playbook.yml` and `roles/` individually rather than
copying `run_dir` as a whole - narrower, but avoids both problems at once
rather than working around either in isolation.

Three real failures in a row, each caught on the first real `vagrant`
invocation and each fixed within one exchange, is itself a data point
worth recording plainly: none of them were reachable from the unit tests
around `ansible_writer.py`, none were guessable in advance without
checking Vagrant's actual documented behaviour instead of assuming
parity between providers or provisioners, and each one only existed
because this was the first time this exact combination (Windows 11 host,
Hyper-V provider, `ansible_local`, a from-scratch generated Vagrantfile)
had actually been run rather than reasoned about.

### Confirmed working

With all three fixed, `vagrant provision` completed cleanly (7 tasks,
3 changed, 0 failed), and `vagrant ssh` into the running VM confirmed
`PermitRootLogin yes`, `PasswordAuthentication yes`, and `MaxAuthTries
1000` all active in the live `/etc/ssh/sshd_config` - the week 3
definition of done, met against a real generated spec on a real booted
machine.

One detail from that verification is worth recording rather than glossing
over: the `PermitRootLogin` task reported `ok` (no change), not `changed`.
`generic/ubuntu2004` turns out to already ship with `PermitRootLogin yes`
active by default - a "convenience box" trait, not unusual for a
general-purpose Vagrant Cloud image, but a genuine mismatch with what a
curriculum-aligned pentesting scenario should be able to assume about its
starting state. `PasswordAuthentication`, by contrast, did report
`changed`, meaning the box's stock config was more locked down there. This
is a small, concrete instance of a larger and more important point: a
generated task can be entirely correct and still land on a base image that
was already partway to (or past) the intended state, for reasons the
generation step has no visibility into. Nothing here validates that a
generated role's *effect* matches its *intent* against a specific base
image - only that it ran without error. That gap is squarely what week 4's
validation stage needs to cover, and this is a real rather than
hypothetical example of why it's needed.

## Week 4: scanning, gating, and automated test-deploy

Week 3 ended on a finding that motivated this entire week: the manual
verification step (`vagrant ssh` + `grep`) confirmed `PermitRootLogin yes`
was live on the booted VM, but closer inspection showed the Ansible task
that claimed to set it had reported `ok`, not `changed` - the
`generic/ubuntu2004` box already shipped with that setting, unrelated to
anything the generated role did. Week 3's pipeline had no way to notice
that distinction; it only checked that generation produced parseable
YAML. Week 4's job was to add the layer that would have caught it, or to
say plainly if nothing available actually catches it.

### The scanning module and a shared result shape

`src/forensicforge/validate/scanners.py` defines two small dataclasses -
`Finding` (one issue: rule id, message, severity, file, line) and
`ScanResult` (a tool's overall verdict: `passed`, a list of `Finding`s, a
tool-specific `summary` dict, and an `error` string) - that every scanner
in the module returns, regardless of how different the underlying tool's
own output format is. `run_checkov()` and `run_ansible_lint()`
(scanners.py), `run_molecule()` (molecule_runner.py), and
`validate_packer_template()` (hcl_check.py) all normalize into this same
shape. The point of doing this rather than passing each tool's raw JSON
through is `report.json`: a single per-run report can iterate over
`report["scans"]` uniformly, and `aggregate_reports()` can compute a pass
rate across tools and runs without needing to know each tool's native
schema.

`ScanResult.passed` is a three-state value on purpose: `True`, `False`,
or `None`. `None` means the tool itself could not be run - not installed,
not reachable, timed out - and is kept structurally distinct from `False`
(the tool ran and found a problem). Collapsing those two into a boolean
would have made "the scanner was unavailable" indistinguishable from "the
scanner passed" in the aggregate statistics, which is exactly the kind of
silent false-positive this week's brief was about avoiding.

### The Windows/POSIX wall, again

Wiring in `ansible-lint` and Molecule ran straight into a bigger version
of a problem this project already knew about from week 3 (Ansible not
running natively on Windows, which is why generated Vagrantfiles use the
`ansible_local` provisioner). `ansible-lint` and Molecule both depend on
`ansible-core`, and `ansible-core` imports POSIX-only standard library
modules - `grp` (used by `ansible-lint`) and `fcntl` (used by Molecule) -
that simply do not exist on Windows. Neither tool can be imported, let
alone run, in this project's Windows virtual environment, regardless of
driver or configuration choices. This was discovered empirically
(`ModuleNotFoundError: No module named 'grp'`, then `'fcntl'`), not
anticipated - it is a materially bigger constraint than "Ansible doesn't
run on Windows," because it means the *tooling that checks* Ansible
doesn't run on Windows either.

Checkov and `python-hcl2` do not have this problem - both are pure Python
with no `ansible-core` dependency - and were confirmed to run natively
before assuming so (`checkov -m checkov.main --version` and a real scan,
`hcl2.load()` against the actual Packer template).

`src/forensicforge/validate/wsl_bridge.py` is the answer for the two
tools that do need it: on Windows, `run_posix_tool()` shells out to WSL
(already installed on this machine since week 3, for the same underlying
reason); on any other platform - specifically, GitHub Actions' Linux
runners - it runs the command directly, since there is nothing to route
around there. `scanners.run_ansible_lint()` and
`molecule_runner.run_molecule()` both call this same dispatcher rather
than hardcoding a WSL call, so the identical scanning code runs correctly
whether it's invoked from this Windows dev machine or from CI. `ansible-lint`
and Molecule are consequently *not* Python dependencies of this project
(`pyproject.toml`) at all - the Windows venv never imports them, only
shells out to wherever they're actually installed (WSL locally, the CI
runner's own environment there). `scripts/check_wsl_tools.py` checks
whether WSL is responsive and whether the two tools are installed inside
it, and - matching every other setup script in this project -asks before
installing anything.

One correctness bug surfaced while building this: the first version of
`run_in_wsl()` had a single timeout covering the entire WSL invocation, so
when WSL itself was unresponsive (see below), every call waited out the
*full* timeout (300s) before reporting failure - two scanners in sequence
meant a ten-minute wait to learn nothing could run. The fix was a
separate, short "liveness" probe (`wsl -- true`, 10s timeout) run before
the real command: a WSL that fails *that* fails fast, while a WSL that
passes it but then hangs on the real command still gets however long that
command legitimately needs.

### Docker checked, not assumed - and found not to be it

The brief was explicit about not assuming Molecule's default Docker
driver would work, given this project already hit one virtualization
surprise (VirtualBox blocked by Windows' Memory Integrity, resolved by
switching Vagrant to the Hyper-V provider in week 3). That caution turned
out to be warranted a second time, for a different reason: `docker info`
showed the Docker Desktop CLI installed but its engine unreachable
(`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file
specified`). Relaunching Docker Desktop and waiting did not resolve it.
Investigating further, a completely unrelated problem turned up: the
machine's C: drive had 0 bytes free, which is independently sufficient to
break Docker Desktop's engine startup (and very likely explains why it
was already in a bad state before this session touched anything). Once
disk space was freed, Docker Desktop was relaunched again - and its
engine still did not come up, and a basic `wsl --list --verbose` call
also hung for 90+ seconds without responding, pointing at the shared
Hyper-V-backed virtualization subsystem needing a clean restart (most
likely a reboot) rather than anything specific to Docker. Given that,
the project moved forward with the **Vagrant driver**
(`molecule-plugins[vagrant]`) for locally-generated roles' Molecule
scenarios, per the brief's own fallback instruction, rather than waiting
on a reboot that was the user's call to schedule, not this session's.

This decision is scoped to *this machine, right now* - it is a real
example of the "verify, don't assume" principle producing a different
answer than "verify, don't assume" produced for the Vagrant provider
question in week 3, because the actual failure was different (a stuck
virtualization subsystem, not a security-feature conflict). It is not a
claim that Docker is unusable on this machine in general, only that it
was not usable at the moment this needed to be decided, and the fallback
existed specifically so that not being knowable in advance wouldn't block
the week.

### Why CI's Molecule scenario uses Docker anyway

GitHub Actions' hosted runners are a different environment with a
different answer to the same question: they support Docker natively but
have no nested virtualization, so a Vagrant-driven scenario (booting a
real VM inside the runner) cannot work there at all, for a structural
reason rather than a this-machine-right-now reason. Rather than force one
driver choice to serve both purposes, the two are kept separate:
`provision/molecule_writer.py` renders a Vagrant-driven `molecule/default/`
scenario into every generated run (matching what this dev machine can
actually execute), while `tests/fixtures/example_role/molecule/ci/`
is a second, Docker-driven scenario against a *fixture* role - a real
role from an actual week-3 run (`generated/20260824-174922/roles/training_vm/`),
copied in as a static example - specifically for CI to exercise against.
CI cannot run the live pipeline in any case, since it has no access to
Ollama; a checked-in fixture was needed regardless of the driver
question, so splitting the driver by environment cost nothing extra.

### Checkov's real coverage, and the PermitRootLogin problem specifically

The brief asked directly: if Checkov or `ansible-lint` don't catch the
class of problem that motivated this week (a claimed change that isn't
actually attributable to the generated role), say so honestly rather than
force a fix that doesn't really solve it. Checked directly rather than
assumed: Checkov's Ansible framework ships exactly six built-in checks
(`checkov/ansible/checks/task/`) - unauthenticated apt installs, `apt
force`, and TLS certificate validation for `get_url`/`uri`/`yum` - plus
two AWS-specific EC2 checks. None of them inspect `ansible.builtin.package`,
`ansible.builtin.service`, `ansible.builtin.lineinfile`, or
`ansible.builtin.user`, which are the only modules any role this pipeline
has generated so far actually uses. Running Checkov against
`generated/20260824-174922/roles/training_vm/` returns `resource_count: 0`
- confirmed to be genuine ("nothing here matches a check I have") rather
than a broken invocation, by constructing a minimal task using
`get_url`/`validate_certs: false` and confirming Checkov correctly flags
*that* (`CKV_ANSIBLE_2`, `passed: False`). **Checkov, as currently
scoped, will essentially always report a trivial pass against this
project's generated roles.** That is recorded here as a limitation, not
smoothed over as "Checkov ran clean" - a `passed: true` in `report.json`
for a role Checkov did not actually have a check for should not be read
as "Checkov verified this role is fine."

`ansible-lint` is closer to relevant (it checks Ansible style/correctness
broadly, not a fixed list of security-flavoured module checks), but
neither it nor Checkov can catch the specific PermitRootLogin case even
in principle, for a structural reason: **that failure mode is not a
property of the role's YAML at all.** The role's task is syntactically
and semantically correct - "ensure this line is present in this file" is
exactly what `lineinfile` does, correctly, regardless of what the file
already contained. The gap is entirely in *attribution*: whether the
resulting live state was caused by the task or already true beforehand.
No static analysis of the role file can answer that, because the answer
depends on the base image, which the role file says nothing about. The
only place that distinction is actually observable is at
apply-time - specifically, an Ansible `changed`/`ok` result, exactly the
signal that gave the game away manually in week 3. `test_deploy.py`
captures this automatically now (each `CheckResult` records whether the
expected line was found, and `derive_checks_from_role()`'s checks are the
mechanical version of the same manual grep), but it verifies *end state*,
not *attribution* - a check passing still doesn't distinguish "the role
caused this" from "this was already true." Actually closing that gap
would mean capturing and comparing Ansible's own per-task `changed`
status, which is possible in principle (Molecule's `verify.yml` or a
`-vv` capture of the converge run could do it) but was not built this
week: recorded here as an accurate limitation rather than implemented as
a fix that would only address one symptom of a broader true problem
(fidelity between the box a role runs on and the box the role's author -
here, an LLM prompted against SSH-specific knowledge snippets - implicitly
assumed).

### python-vagrant and a real bug in error visibility

`src/forensicforge/validate/test_deploy.py` scripts the boot → verify →
destroy cycle `python-vagrant` wraps around the `vagrant` CLI. Building it
surfaced a bug worth recording because it would have made every future
failure hard to diagnose: `python-vagrant`'s `up()` and `destroy()` are
implemented over `subprocess.check_call` internally
(`Vagrant._call_vagrant_command`), not `check_output` - unlike `.ssh()`,
which does use `check_output` and so raises a `CalledProcessError` with
real `.output` content on failure. `check_call`'s `CalledProcessError`
never carries stdout/stderr *at all*, regardless of how the instance's
`quiet_stdout`/`quiet_stderr` flags are set, because `check_call` was
never given anywhere to capture it. First attempt at surfacing a real
failure (deliberately reproduced: `vagrant up --provider=hyperv` without
an elevated terminal) returned only `Command '[...]' returned non-zero
exit status 1` - true, but useless for telling a permissions problem
apart from a missing box, a bad Vagrantfile, or anything else. The fix
was to give `Vagrant()` a custom `out_cm`/`err_cm` that appends to
`run_dir/vagrant.log` instead of the default (discarded to `/dev/null`
under `quiet_stdout=True`), and read the tail of that file back into
`TestDeployResult.error` on failure. Re-run against the same reproduced
failure, this correctly surfaces the actual Vagrant message ("The
Hyper-V provider requires that Vagrant be run with administrative
privileges...") - confirming both that the fix works and, incidentally,
that `test-deploy` genuinely does need an elevated terminal on this
machine, the same Hyper-V constraint week 3 already established for
`vagrant up`.

`derive_checks_from_role()` turns each `lineinfile` task's `path`/`line`
into a `sudo grep -F -- '<line>' <path>` check - mechanically
reconstructing the exact manual command used to verify the SSH example in
week 3, but from whatever the role actually contains rather than
hardcoded to that one spec. Run against the real week-3 role, it derives
all four checks (`PermitRootLogin`, `PasswordAuthentication`,
`MaxAuthTries`, `Port`) correctly and automatically.

### After the reboot: getting ansible-lint and Molecule to actually run

A reboot (the user's own call, once free to do it) settled WSL and Docker
Desktop, confirming the earlier diagnosis: the virtualization subsystem
genuinely needed a clean restart, not a code-level workaround. What
followed was setting up the WSL side for real and running the
WSL-dependent code paths above against live tools for the first time,
rather than only against mocked `run_posix_tool()` calls - and that
surfaced four more real bugs, none of which unit tests (necessarily
mocking the WSL boundary) could have caught.

**WSL's Ubuntu was minimal - no `pip` at all.** Recent Ubuntu blocks
installing into system Python directly (PEP 668, "externally managed
environment"), and `python3-venv` - needed to route around that the
standard way - itself needs `apt`, which needs a sudo password this
session has no way to supply (entering a password on the user's behalf
is out of scope regardless - see this project's own safety rules). The
one `sudo apt install python3-pip python3-venv` had to be run by the user
directly in their own WSL terminal; everything after that (creating a
venv at `~/.forensicforge-tools`, `pip install`ing `ansible-lint` and
`molecule`/`molecule-plugins[vagrant]` into it) could proceed normally.
`config.WSL_TOOLS_VENV` and `scripts/check_wsl_tools.py` reflect this
final setup - a dedicated venv, not WSL's system Python.

**Command strings crossing the Windows subprocess → wsl.exe → WSL bash
boundary reliably corrupt embedded quote characters.** Getting Molecule's
Vagrant driver working needed `ANSIBLE_LIBRARY` set to a path computed by
a small Python snippet (see below); every attempt to pass that snippet
inline via `python3 -c "..."` came out mangled on the WSL side - single
quotes inside double quotes, double quotes inside single quotes, even a
base64-encoded payload (where only the wrapping quotes, not the payload
itself, contained anything to corrupt) - all failed the same way,
reproduced repeatedly with `repr()` of the exact bytes sent confirming
the string was correct *before* the wsl.exe boundary and wrong *after*.
The fix (`scripts/wsl_helpers/print_vagrant_modules_dir.py`,
`wsl_bridge.py`'s `to_wsl_path()`) was to stop putting inline scripts in
command strings altogether: write the logic to a real `.py` file and
invoke it by path, which has no quotes to mangle. Anything that needs to
run POSIX-side Python logic through this bridge in future should follow
the same pattern rather than re-attempting inline `-c` strings.

**`source venv/bin/activate && export X=$(python3 ...)` doesn't reliably
find the venv's `python3` inside the `$(...)` subshell**, even though
`source` ran first in the same `&&` chain and the *same* pattern without
`$(...)` works fine (confirmed: `molecule --version` after `source
activate` correctly finds the venv's `molecule`). Root cause not fully
pinned down; worked around by calling the venv's `python3` by absolute
path (`{WSL_TOOLS_VENV}/bin/python3`), which needs no `PATH` resolution
or prior activation at all. Combined with the quoting problem above, the
most robust fix was to abandon folding the computation into the main
`molecule test` command via `$(...)` entirely: `_find_ansible_library()`
in `molecule_runner.py` is now a *separate* `run_posix_tool()` call whose
captured stdout is read back into this Python process, then passed to
the next call as a literal value - sidestepping both problems by never
asking a subshell three layers deep to hand back a value at all.

**Ansible role resolution failed twice, for two different reasons - both
found by reproducing `ansible-playbook`'s actual "role not found" error
directly rather than trusting Molecule's own summary output.** First:
`ansible-compat`'s local-role-install step (part of Molecule's "prerun")
symlinks the role under a *namespaced* name - `forensicforge.training_vm`,
not bare `training_vm` - derived from `meta/main.yml`'s `galaxy_info.author`
field (confirmed by finding the actual symlink under `~/.ansible/roles/`).
`molecule_writer.py`'s `converge.yml` referenced the bare name, so
resolution failed. Fixed by introducing `ROLE_NAMESPACE` as a single
constant shared between `ansible_writer.py` (which writes the `author:`
field) and `molecule_writer.py` (which writes `converge.yml`'s `roles:`
list) - see `ROLE_NAMESPACE`'s docstring in `ansible_writer.py` - so the
two can't drift apart silently again. Second, and separately: the
Vagrant *provider* choice belongs under `driver.provider.name` in
`molecule.yml`, not `platforms[].provider.name` where the first version
of `MOLECULE_YML_TEMPLATE` put it. That mistake didn't produce an error -
it silently fell back to molecule-plugins' vagrant Ansible module's own
default provider, `virtualbox`, confirmed by inspecting the actual
Vagrantfile Molecule generated (`c.vm.provider "virtualbox"`) before the
fix and `c.vm.provider "hyperv"` after. Silently falling back to
VirtualBox is exactly the failure mode week 3 already worked around by
switching to Hyper-V in the first place, so this bug would have
reintroduced it invisibly - the Vagrantfile `provision` generates was
never wrong, only the *separate* Vagrantfile Molecule generates for its
own ephemeral instance.

With all four fixed, a live `run_molecule()` against the real week-3 role
now gets through `destroy` (proving the `vagrant` Ansible module
resolves - the `ANSIBLE_LIBRARY` fix), `syntax` (proving the role
resolves - the namespace fix), and correctly generates a Hyper-V
Vagrantfile (the provider-location fix) before reaching `create` - the
actual VM boot. That step could not be completed live this session, for
two compounding reasons rather than one: `create` needs the same elevated
terminal `test-deploy`'s `vagrant up` needs (confirmed identically -
`vagrant up --no-provision` failing with the Hyper-V administrative-
privileges message), and separately, this machine's VirtualBox
installation still has multiple VMs stuck `<inaccessible>`
(`E_ACCESSDENIED`, `LockMachine` failing) - the same Memory Integrity
conflict documented in week 3, now also affecting some of Vagrant's own
internal machine-index bookkeeping for the ephemeral instances Molecule's
Vagrant driver creates. Three VMs left behind by this session's own
repeated `molecule create` attempts were cleaned up
(`VBoxManage unregistervm --delete`); three pre-existing `<inaccessible>`
VMs of unknown origin were deliberately left alone rather than deleted
without being sure they weren't something the user cared about
investigating. **The molecule-driven boot itself remains unverified
live** - the configuration is now demonstrably correct (right Vagrantfile,
right role resolution, right module path), but confirming a full
create → converge → verify → destroy cycle actually succeeds needs the
user's own elevated terminal, the same as `test-deploy`.

### report.json and aggregation

Each `validate`/`test-deploy` CLI run writes (or updates)
`report.json` in the run directory: `scans` (checkov, ansible-lint),
`molecule`, and `test_deploy`, each in the common `ScanResult`/
`TestDeployResult` shape above, plus `run_id`, `spec`, and a generation
timestamp. `validate` and `test-deploy` are separate commands writing to
the same file rather than one combined command, because they have
different environment requirements (`validate` is CI-safe; `test-deploy`
needs a real hypervisor and an elevated terminal) and different runtimes
(`validate` finishes in seconds; `test-deploy` takes minutes) - forcing
them into one command would mean either running the slow one every time
or awkwardly flagging it off.

`aggregate_reports()` scans every `generated/*/report.json` and computes,
per tool, `{passed, applicable, rate}` - `applicable` excludes runs where
that tool reported `None` (unavailable), so an unreachable scanner drags
down "applicable" rather than silently counting as a pass or corrupting
the rate. This is deliberately the same shape the DPIaC-Eval benchmark
referenced in the background report uses for a deployability/compliance
rate: with more than one run's worth of `report.json` files (there is
currently one, from week 3, retrofitted with a `validate`/`test-deploy`
pass this week), `forensicforge report-summary` becomes the aggregate
number the dissertation's evaluation chapter needs, computed the same way
every time rather than assembled by hand per chapter draft.

### Why CI doesn't run test-deploy

GitHub's hosted runners don't support nested virtualization, so neither
Vagrant+Hyper-V (this project's actual local setup) nor Vagrant+VirtualBox
could boot a real VM there regardless of provider choice - this isn't a
configuration gap to work around, it's a structural property of the
runners. `test-deploy` stays a local-only command; CI's `validate.yml`
covers `check-packer`, the checkov/ansible-lint scans (via
`scripts/ci_scan.py`, reusing this project's own scanning code rather
than re-implementing invocation logic in YAML), the unit test suite, and
Molecule verification against the checked-in fixture role (Docker driver,
per above) - everything that can genuinely run on a hosted runner, and
nothing that would either fail structurally or need to be faked to pass.

The workflow itself (`.github/workflows/validate.yml`) has not been
exercised by an actual push yet as of writing - recorded honestly rather
than presented as verified, consistent with how the WSL-dependent parts
of this week are also flagged as code-complete-but-not-live-tested below.

## Week 5: closing the attribution gap, and forensic scenario generation

Week 4 ended on an open question: `test_deploy.py` verified that a
generated VM's configuration ended up in the right end state, but not
whether the role's own application had *caused* that state versus the
base image already having it - the exact ambiguity that motivated week
4 in the first place, still unresolved for `test_deploy.py` itself. The
brief for this week named that gap "attribution," pointed out it's the
same problem forensic evidence integrity has to solve (if evidence is
planted, prove it was planted, not that it happened to already be
there), and made closing it this week's opening move before the actual
forensic-scenario work, since the same mechanism serves both.

### Getting CI to actually pass

Week 4 built `.github/workflows/validate.yml` but never pushed it - this
week's first job was to actually exercise it, not just have it exist.
Doing that surfaced a chain of real bugs, none of which unit tests or
local WSL testing had caught, because none of them could have: they were
specific to running on a genuinely fresh checkout, on Linux, on someone
else's infrastructure, none of which this session's own environment
(Windows + WSL + this project's own accumulated local state) actually is.

An unrelated detour happened first: partway through this week, the local
git repository's history was lost (a `.git` deletion during an editor
mishap, then a fresh `git init` and push to recover) - everything from
weeks 1-4 collapsed into a single "Initial commit," and one file
(`.github/workflows/validate.yml` itself) didn't survive the recovery at
all, silently dropped rather than corrupted. Rewritten from scratch
(the content was still fresh from having authored it days earlier) and
re-pushed before CI could be exercised at all - recorded here since it's
a real, if mundane, thing that happened this week, not because it changed
any actual project decisions.

With the workflow actually running, CI failed both jobs on the first
real push, then kept surfacing new, different, genuine failures as each
was fixed - five in total, each one something no amount of local testing
in this specific environment would have shown:

1. **`ansible-lint` was never installed on the CI runner.** `ci_scan.py`
   correctly reported it unavailable and failed the job (exactly the
   behavior week 4 designed it to have) rather than silently skipping it
   - the fix was adding the missing `pip install ansible-lint` step, not
   a workaround. `ansible-lint`'s absence from `pyproject.toml` is
   deliberate (Windows-incompatible, see week 4), but that means every
   environment that needs it - WSL locally, the CI runner here - needs
   its own explicit install, which the workflow had simply forgotten for
   the runner.
2. **The Docker image's Python was too old.** `geerlingguy/docker-ubuntu2004-ansible`
   ships Python 3.8; the `ansible-core` this job pip-installs with no
   version pin (whatever's current) requires 3.9+ on the managed node.
   Fixed by switching to the `2204` (Ubuntu 22.04, Python 3.10) variant of
   the same image family.
3. **`ansible-lint`'s own scope was wrong, and this one mattered beyond
   CI.** Scanning a role directory that contains a `molecule/`
   subdirectory (every generated role has one - `molecule_writer.py`,
   week 4) makes `ansible-lint` also try to syntax-check the scenario's
   own `converge.yml`, whose namespaced role reference can't resolve
   without Molecule's own local-role-install step having run first.
   `--exclude molecule` fixed that specific error - but doing that
   without also setting an explicit working directory changed
   `ansible-lint`'s own project-root discovery enough to silently drop a
   real, unrelated finding (`yaml[truthy]` on a completely different
   file) from the results entirely, discovered only by comparing
   "N files encountered" with and without an explicit `cwd` and noticing
   it jumped from 5 to 86. A `passed: true` that turned out to be missing
   real findings is a worse bug than a `passed: false` CI never reaches -
   `scanners.run_ansible_lint()` now always passes `cwd=role_dir`
   explicitly, and this fix applies to every role scan project-wide, not
   just the CI fixture: a stale, seemingly-clean local result earlier in
   the week turned out to have been accidentally masked the same way, by
   a leftover role symlink from this session's own prior testing that a
   genuinely fresh checkout would never have.
4. **The container's temp-directory and systemd setup needed the
   standard "systemd inside Docker" recipe.** Ansible's own error message
   ("Failed to create temporary directory... consider a path rooted in
   /tmp") pointed at the immediate cause (`remote_tmp` resolving to
   `/.ansible/tmp` - no home directory component at all, because the
   Docker connection plugin's exec context doesn't set `$HOME`) but
   fixing just that wasn't sufficient; the container's systemd hadn't
   finished initializing enough to provide a normal `/tmp`/`/run` at all.
   `provisioner.config_options.defaults.remote_tmp` fixed the path;
   an explicit `volumes: [/sys/fs/cgroup:/sys/fs/cgroup:rw]` and
   `tmpfs: [/run, /run/lock]` (the standard, widely-documented recipe for
   running systemd inside Docker, broader than `cgroupns_mode: host`
   alone) fixed the rest. Confirmed against real research rather than
   trial-and-error alone: the geerlingguy image's own issue tracker has
   multiple open, maintainer-unresolved reports of this exact failure,
   which is why this stopped at the standard documented recipe rather
   than continuing to chase container internals - "don't gold-plate" cuts
   both ways, and a well-established fix that worked was the point to
   stop at.
5. **The container's package index was stale.** Once the role actually
   started converging, `Install OpenSSH server` failed with `No package
   matching 'openssh-server' is available` - an ordinary stale apt cache,
   not fixed by editing the fixture role itself (which stays a faithful,
   unmodified copy of a real generated run) but by adding
   `molecule/ci/prepare.yml`, a `ansible.builtin.apt: update_cache: true`
   step Molecule already calls by convention if present (the "prepare:
   Missing playbook" line in every earlier failed run's log was this
   exact hook, sitting unused).

Both jobs pass as of the final push this week. The two-minute-something
runtime and the "Node.js 20 is deprecated" warnings on `actions/checkout@v4`/
`actions/setup-python@v5` are GitHub's own infrastructure notices (already
auto-mitigated by forcing those actions onto Node 24), not something in
this project's control - left alone rather than chased, in the same
"don't gold-plate" spirit as stopping at the standard systemd-in-Docker
recipe above.

### Closing the attribution gap

Ansible's default console output already prints exactly the distinction
needed: a `TASK [<role> : <task name>]` header followed by `changed:` or
`ok:` per host, depending on whether the task actually modified
anything. `vagrant up`'s `ansible_local` provisioner streams this
straight into the console output `test_deploy.py` was already capturing
into `run_dir/vagrant.log` for error reporting (see week 4's
python-vagrant section) - closing the gap turned out to mean parsing
output already being captured, not adding any new instrumentation.

`test_deploy.py` gained `parse_task_attribution()` (regex over
`TASK [...]` headers and the following `ok:`/`changed:`/etc. line) and
`CheckResult.attribution`, populated by matching each check's task name
(via `DerivedCheck.task_name`, now carried alongside `command`/`expected`)
against the parsed output. Verified against real output rather than
assumed correct: rather than requiring a full VM boot (needing the
user's elevated terminal) just to see what Ansible's console format
actually looks like, the real generated role was run directly inside
WSL against `localhost` - first in `--check` (dry-run) mode to confirm
the format without touching anything, then for real against a throwaway
file (never `/etc/ssh/sshd_config` itself) to see both a `changed:` on
first application and an `ok:` on the idempotent second run. Both
matched the parser's assumptions exactly.

Two more things were found and fixed while wiring this up, both real
correctness bugs rather than gaps:

- A live `vagrant.log` from an earlier session showed `Machine already
  provisioned. Run \`vagrant provision\` or use the \`--provision\` flag
  to force provisioning` - meaning `test_deploy()`'s `v.up()` call,
  without `provision=True`, could silently skip Ansible entirely on a
  machine Vagrant's own bookkeeping considered already provisioned (from
  an earlier attempt, possibly with different content). That would have
  meant `test_deploy()`'s own checks could pass by observing *stale*
  state from a previous run rather than this run's role - the general
  form of the exact attribution problem this feature exists to close,
  now closed for `test_deploy()` itself too: `v.up()` now always passes
  `provision=True`, and `vagrant.log` is truncated fresh at the start of
  each `test_deploy()` call so `parse_task_attribution()` only ever sees
  the current run's output.
- The naive timestamp handling for backdated artefacts (see below) had a
  latent timezone bug: computing an expected epoch via
  `datetime.fromisoformat(...).timestamp()` on a naive value uses *this
  host's* local timezone, while the guest's `touch -d` would use *its*
  local timezone - silently mismatched whenever the two differ. Fixed by
  pinning both sides to UTC explicitly (a trailing `Z` on the `touch -d`
  argument, `.replace(tzinfo=timezone.utc)` on the Python side) and
  confirmed by computing the same value both ways and checking they
  actually matched (`1767225600` for `2026-01-01T00:00:00`, both sides).

**Status: closed**, not parked - `report.json`'s `test_deploy.checks[].attribution`
is now real data (`"changed"` = this run's role/artefacts caused the
state, `"ok"` = it was already there, `None` = the task never ran at
all), live-verified against genuine Ansible output, not just unit-tested
against a mocked one (though it is unit-tested that way too -
`tests/test_validate.py`'s attribution tests mock the WSL boundary the
same way the rest of week 4's tests do, for a fast, hermetic suite; the
WSL localhost runs above were a one-off verification exercise, not part
of the automated suite).

### libguestfs vs. Ansible-based artefact planting

The brief asked for a real feasibility check before committing to
libguestfs, given this project's history of virtualization-stack
surprises (VirtualBox blocked by Memory Integrity in week 3, WSL/Docker
Desktop both hanging for an entire session in week 4). Checked rather
than assumed: WSL2 on this machine does have `/dev/kvm` and the `vmx`
CPU flag, meaning libguestfs's appliance *could* run accelerated rather
than falling back to slow emulation - a genuinely promising finding,
recorded here since it means the door isn't closed for a future need.

Two reasons decided against using it *this week* regardless, one
environmental and one about whether it would actually add anything:

1. **Lifecycle mismatch.** libguestfs needs to open a VM's disk image
   directly, which means the disk has to exist and not be locked by an
   active hypervisor. This project's actual VM lifecycle
   (`test_deploy()`: create → boot → verify → always destroy) never
   leaves a window where that's true for a *per-scenario* disk - Vagrant
   deletes the VHDX on `destroy()` every time. Making libguestfs work
   would mean redesigning the boot lifecycle around it (stop-mount-modify-
   restart, or pre-seeding the shared base box rather than per-run
   disks), a materially bigger change than the artefact-generation work
   itself.
2. **Nothing in the brief's own example artefact list actually needs
   disk-level access.** Fabricated log entries and shell history are
   ordinary file writes. Backdated timestamps are exactly what `touch -d`
   does from user space - no disk tool required. Deleted-file remnants
   don't need libguestfs either: a real process unlinking a real file via
   `rm`/`ansible.builtin.file: state=absent` leaves the same recoverable
   unallocated-block state a disk-level deletion would, on any filesystem
   that doesn't zero blocks on unlink by default (ext4 doesn't, absent
   `discard`) - which is also, not incidentally, a more *realistic*
   artefact than one injected from outside the running system, since a
   real insider threat's deleted files get deleted by a live process too.

Given libguestfs would cost real new environment risk for capability
this project's actual artefact types don't need, **artefacts are planted
through Ansible**, reusing exactly the `ansible_local` provisioner
infrastructure week 3 already built and week 4/5 already verified works.
Kept as a live option: if a future scenario genuinely needs something
only disk-level access can produce (recovering *unplanted* pre-existing
deleted data, say, rather than planting-then-deleting known content),
the KVM finding above means it's not obviously a dead end - just not
needed yet.

### The forensics module

`src/forensicforge/forensics/` adds:

- **`storyline.py`** — `Artefact` (kind, description, target_path,
  content, optional timestamp) and `Storyline` (id, title, narrative,
  `base_spec`, artefacts). `base_spec` is fed into the existing
  `generate_vm_spec()` RAG pipeline completely unchanged - a storyline is
  what the machine should *look like it did*, layered on top of what the
  machine actually *is* (an ordinary curriculum VM spec, generated the
  same way every other run is).
- **`generators.py`** — Faker-backed content: shell-history-shaped
  commands (exfiltration, archiving, history-clearing), syslog-style auth
  log lines, plain-text email drafts, and synthetic "client record" CSVs.
  Every value is Faker-fabricated; nothing here accepts or embeds real
  personal data - the same justification the research tracker already
  gives for why this project's forensic track doesn't need ethics
  approval.
- **`planter.py`** — the core piece. For each artefact kind, builds the
  Ansible task(s) that plant it *and* the verification check(s) that
  confirm it, in the same function (`_build_task_and_check`), so the two
  can never drift out of sync the way a hand-maintained pair of role and
  test file could - the same reasoning behind `ROLE_NAMESPACE` in
  `ansible_writer.py`. Four artefact kinds, four different Ansible/
  verification shapes:
  - `log_entry` / `shell_history` → `ansible.builtin.lineinfile`
    (append), verified by grep - literally the same module and
    verification pattern every generated scenario role already uses, so
    this reuses `test_deploy.py`'s existing machinery with no new check
    logic at all.
  - `email_draft` → `ansible.builtin.copy` (whole file), verified by
    grepping the `Subject:` header line specifically (a multi-line body
    isn't a single grep -F target).
  - `deleted_file` → write then `state: absent`, verified by confirming
    *absence* (`test -e ... || echo CONFIRMED_ABSENT`) rather than
    content.
  - `backdated_file` → write then `touch -d '<timestamp>Z'`, verified by
    `stat -c %Y` against the expected UTC epoch. The `touch` task is
    given `changed_when: true` explicitly (ansible-lint's `no-changed-when`
    rule correctly flags a bare shell command as unable to report
    changed/ok reliably on its own) - meaning attribution for *this one
    task* is always `"changed"` by design, a narrow, documented exception
    to the general attribution mechanism rather than something worth a
    bigger fix, since the timestamp check itself still confirms the
    actual on-disk state regardless.

  A second Ansible role (`forensic_artefacts`), not folded into the
  scenario role: keeps "what the box is" separate from "what evidence is
  on it," and `playbook.yml` is regenerated to run both roles in
  sequence.

  `CheckResult`/`DerivedCheck` gained a `category` field ("config" or
  "artefact") so `test_deploy()` doesn't need to know anything about
  storylines at all - it just runs whatever checks it's given and tags
  results by whatever category they came in with.
  `TestDeployResult.artefacts_verified` is tracked separately from
  `config_verified` for the same reason: "did the baseline config land"
  and "did the evidence get planted" are different questions once a run
  mixes both kinds of check, and blending them into one flag would lose
  that distinction.

- **`scenarios.py`** — three demo storylines (below).
- **`orchestrator.py`** — `provision_storyline()`, which calls the
  existing `provision_spec()` unchanged for the scenario role, then
  `write_artefact_role()` for the evidence.

Real, tool-caught issues found while building this (not hypothetical -
`ansible-lint` run against the actual generated artefact role):
`risky-file-permissions` (the copy/lineinfile tasks had no explicit
`mode:`, fixed with real values - `0600` for private files like shell
history and email drafts, `0644` for things a real log file or note
would plausibly have) and the `no-changed-when` finding on the `touch`
task described above.

### Demo scenarios

Three storylines, not variations on one theme: a departing employee
exfiltrating client data (the brief's own example), a sysadmin
installing unauthorized remote access before being placed on leave, and
a contractor deleting project files after being told their contract
won't be renewed. Different narrative shapes (exfiltration,
unauthorized-access, sabotage/evidence-destruction), each with 5-7
artefacts spanning all four kinds.

This is also a first, partial step against week 4's "only one spec
family has real coverage" limitation - each storyline's `base_spec` is
deliberately *not* SSH-pentesting phrasing (a corporate workstation, an
internal file server, a dev VM with a shared repo). Checked rather than
assumed whether this actually broadened coverage: it doesn't, not yet.
Every generated scenario role still comes back SSH-flavoured (install
openssh-server, manage sshd, sometimes a deliberately weak credential)
regardless of the storyline's own framing, because the RAG corpus
(`knowledge/`) is still SSH/sshd_config-focused - retrieval surfaces what
the corpus has, not what the spec asks for in different words. Real
breadth needs broader corpus content, which is real work for a future
week, not something phrasing alone was ever going to solve - recorded
honestly here rather than claimed as progress it isn't.

### Debugging test-deploy for real: what live Hyper-V boots actually surfaced

Getting from "code that should work" to real `test-deploy` runs against
all the week's scenarios took far more debugging than the feature list
above suggests, and surfaced a genuinely long chain of real, previously-
invisible bugs - none catchable by unit tests (which mock the WSL/vagrant
boundary deliberately, for a fast hermetic suite) or by anything short of
an actual elevated-terminal boot on this actual machine. Recorded here in
full because each one is a real, reproducible finding, not a guess:

1. **`vagrant up` on Hyper-V hung forever**, waiting on an interactive
   "What switch would you like to use?" prompt `test_deploy()` can never
   answer (no stdin fed to it). First fix attempt was wrong: a
   `config.vm.provider "hyperv" do |h| h.vmswitch = ... end` block, which
   Vagrant rejected outright ("The following settings shouldn't exist:
   vmswitch") - checked against Vagrant's actual `config.rb` on GitHub
   afterward and confirmed no such attribute exists at all, despite
   several online guides implying otherwise. The real mechanism, found by
   reading the Hyper-V provider's `configure.rb` action directly: a
   `config.vm.network "public_network", bridge: "<switch name>"` entry -
   ordinary Vagrant networking config, not a Hyper-V-specific setting.
2. **The shell provisioner that creates the upload directory defaults to
   running as root**, so the *next* provisioner's SCP upload (as the
   plain `vagrant` user) failed with a permissions error writing into it.
   `privileged: false` fixed it. This had been silently masked until this
   week: Vagrant's own "already provisioned, skip" default meant it had
   never actually re-run this step on a machine reused from an earlier
   manual boot, until `provision=True` (closing the attribution gap)
   started forcing every `test-deploy` to reprovision from scratch.
3. **`test_deploy()` only ever called `destroy()` if `up()` succeeded** -
   found by hitting exactly the failure mode it caused: a provisioner
   step failed partway through `up()` (after the VM already existed), the
   function returned early, and the VM was left running with a lock that
   then blocked every subsequent attempt against the same run directory.
   Restructured so `destroy()` always runs via `finally`, regardless of
   where or whether `up()` failed. A regression test
   (`test_test_deploy_destroys_even_when_up_fails`) locks this in.
4. **`ansible.builtin.copy`/`lineinfile` don't create missing parent
   directories.** A `deleted_file` artefact targeting
   `/home/vagrant/Documents/clients/export.csv` failed outright
   ("Destination directory ... does not exist") because nothing else in
   the role had created `Documents/clients/`. Fixed with a shared
   `_ensure_dir_task()` helper, applied uniformly to every file-writing
   artefact kind - not just the one that happened to need it for today's
   demo scenarios, since a future storyline could easily target an
   equally unlikely path.
5. **A storyline artefact deleted evidence from other artefacts in the
   same playbook run.** `shell_command_history_clear()` originally
   generated `history -c && rm -f ~/.bash_history` - narratively an
   attempt to cover tracks, but literally correct: it deleted the exact
   file two earlier artefacts (the `tar`/`scp` commands) had just
   written their evidence into, in the same run. Confirmed precisely by
   the failure pattern: every check for a line written *before* this
   task failed, everything written after (nothing, in this case) or
   verified independently of it passed. Fixed to `history -c` alone -
   which is also more forensically realistic (actually deleting the file
   outright is a far more conspicuous move than just clearing the
   in-memory session history).
6. **The guest sometimes received stale content on `roles/`, not what
   was currently on disk.** A rerun on a genuinely fresh VM (confirmed
   via "Importing a Hyper-V instance" in the log, not a resumed one)
   still ran an older version of a role than what the host filesystem
   had at the time of `vagrant up` - no confirmed root cause, but
   Vagrant's directory-copy file provisioner is the only thing between
   "what's on disk here" and "what the guest sees", so the fix was
   forcing a clean destination (`rm -rf roles` before every copy) rather
   than requiring the mechanism to be pinned down first.
7. **A `validate` run after `test-deploy` silently destroyed the
   `test_deploy` section of `report.json`.** `build_validation_report()`
   always sets `test_deploy: None` (it never boots anything), and the CLI
   wrote that dict out wholesale rather than merging it into whatever was
   already there - confirmed by finding real, already-recorded
   `test_deploy` data replaced with `null` after a routine re-validate.
   Fixed to load and preserve the existing `test_deploy` section first
   (`test-deploy` itself already did the equivalent for its own writes;
   `validate` needed the same). The already-lost data for the runs
   affected was reconstructed from the exact terminal transcripts of
   those runs (verbatim commands, matched/attribution results; `output`
   approximated as the expected value on a match or empty on a miss,
   since the raw grep text itself wasn't part of the transcript) rather
   than re-run from scratch at real Hyper-V-boot cost - each
   reconstructed `report.json` carries an explicit note saying so.

### The one finding left genuinely unresolved: some files won't hold evidence

One more anomaly survived two separate, real fix attempts and is
recorded here as an honest, characterized-but-not-root-caused limitation
rather than something forced to look solved. Across every live run:
writes to `/var/log/auth.log` and to the *actively SSH-connected* user's
(`vagrant`'s) `.bash_history` were never reliably verifiable, no matter
how they were written - while writes to every other target (a
`become`-only user's `.bash_history`, deleted files, backdated
timestamps, email drafts) verified correctly, every time, across all
three scenarios.

Two fix attempts were made before concluding this needs a different kind
of investigation than another live-boot cycle:

- Consolidating the three `.bash_history` writes for one storyline into
  a single atomic `blockinfile` task, on the theory that sequential
  separate writes were each getting clobbered by something running
  between them. This didn't hold up: even as one atomic write, two of
  the three lines were still missing at verification time while the
  third (coincidentally-plausible `history -c`) was still there - ruling
  out "multiple separate writes" as the mechanism, since an atomic write
  either all persists or it doesn't.
- The leading hypothesis that remains: the *live* SSH session Ansible/
  Vagrant itself uses is logged in as `vagrant` for every task, and
  something in that session's own shell/login mechanics (rather than
  anything in this project's own tasks) is what's touching
  `vagrant`'s `.bash_history` between tasks - never confirmed against the
  actual guest, since doing so needs a boot cycle kept alive specifically
  to inspect it before destroy runs, which wasn't attempted this week.
  `/var/log/auth.log` doesn't fit that theory directly (it isn't a shell
  history file), so if there is one root cause, it isn't this one; if
  there are two separate causes, this is a hypothesis for one of them.

Chasing this further would have meant more 5+ minute live-boot cycles
against an uncertain payoff - the "don't gold-plate" instruction that
already applied to the CI systemd investigation applies here too.
Documented as real, reproducible, evaluation-relevant data instead: two
specific artefact target types are currently unreliable for verification
on this provider/box combination, everything else is not. A concrete,
actionable takeaway for future storyline design either way: prefer
target paths outside actively-managed system files (a project-owned log,
a non-primary user's history) until this is better understood.

### Evaluation across the scenario set

`report.py`'s `aggregate_reports()` gained two additions for this: a
per-run `test_deploy_artefacts_verified` rate (parallel to the existing
`test_deploy_config_verified`, `None` on runs with no storyline so plain
curriculum-VM runs don't drag it down), and a per-*check* (not per-run)
`artefact_checks` breakdown - total artefact checks across every run,
how many matched, and how many were specifically attributed to `"changed"`
(planted by that run) rather than merely present. The per-check
breakdown matters once there's more than a couple of forensic runs:
"did every artefact in this one run verify" and "how reliably does
artefact planting work overall" are different questions, and only the
second one is a meaningful number to report with a small sample size.

The first real dataset, across all 5 runs so far (1 SSH-pentesting run
from week 3, 3 forensic storylines, and 1 discarded re-roll of the
sabotage storyline kept only for its static-scan data - see the corpus-
coverage discussion above):

```
total_runs: 5
checkov:                      5/5 passed  (1.0)
ansible_lint:                 3/5 passed  (0.6)
molecule:                     0/5 passed  (0.0)  - local elevation/environment, see below
test_deploy_booted:           3/4 applicable  (0.75)
test_deploy_config_verified:  2/2 applicable  (1.0)
test_deploy_artefacts_verified: 0/2 applicable  (0.0)
artefact_checks:  12 total, 8 matched (0.667), 12/12 attributed to their run (1.0)
```

Reading this honestly rather than as a scorecard: checkov's 100% and
ansible-lint's 60% both mean what the week 4/5 sections above say they
mean (checkov mostly has nothing applicable to check; ansible-lint's two
failures are both genuine, one of them the same `generic/ubuntu2004`-vs-
"ubuntu"-user issue documented below). Molecule's 0% is this session's
own elevation/Hyper-V constraints, not a role-quality signal. The
`test_deploy` numbers are the interesting ones: booting succeeded 3 times
out of 4 attempts (the failure is the corpus-gap "ubuntu" user issue,
a real content problem, not infrastructure), config verification was
perfect on the runs that had config checks to verify, and - the number
that matters most for this week's actual point - **every single one of
the 12 artefact-planting tasks across both completed forensic runs was
correctly attributed as `"changed"`: the tooling never once failed to
notice that its own tasks had actually run.** The gap is entirely in the
*separate* question of whether that state was still observable moments
later (8/12, for the reasons above), which is exactly the distinction
attribution was built to make visible rather than blur together.

## Week 6: proving dynamic generation, closing the vulnerability-claim gap, and tying storylines to real VMs

Week 5 left three things genuinely open rather than closed: every demo had
centred on SSH pentesting, so "the pipeline responds to different specs"
was asserted rather than shown; "applied misconfigurations" was still a
claim the LLM made at generation time with no automated way to check it
against a live VM (week 4's attribution work closed *how* a claim would
be checked, but nothing actually read the claims and checked them); and
the three forensic storylines were, on inspection, built independently of
whatever a given run's role actually did. This week closes all three -
the last one by building something new, not by relabelling what already
existed.

### Proving dynamic generation, and what it actually found

Rather than vary a spec's *wording* around the same SSH-pentesting core
(the acknowledged limitation of week 5's own three demo storylines - see
the `scenarios.py` module docstring), three spec categories were
provisioned for real, live, this week: an SSH bastion host, an Ubuntu
server with Telnet enabled and a permissive firewall, and a database
server with PostgreSQL exposed with no authentication. A fourth (audit
logging disabled + world-writable permissions) was added afterward to
get a second, non-SSH, *fully checkable* example for the verify-
vulnerabilities work below.

The honest result: the corpus is broader than "SSH-only" suggests -
`knowledge/misconfigurations/` has eight distinct categories (weak SSH
root login, open firewall, default credentials, unencrypted Telnet,
world-writable permissions, unpatched packages, exposed database, disabled
audit logging), and retrieval genuinely pulled from different ones for
different specs, producing structurally different generated roles, not
the same SSH tasks with a different hostname templated in:

- The **Telnet/firewall** spec produced a role with zero `lineinfile`
  tasks at all - `ansible.builtin.package` (installing `telnetd`) and
  `community.general.ufw` (firewall policy) instead. Genuinely different
  module usage, not a reskin.
- The **audit-logging/permissions** spec produced a role editing
  `/etc/rsyslog.d/50-default.conf` (disabling SSH login logging via
  `authpriv.none`) and creating a `0777` shared directory - again, no
  overlap with the SSH-bastion role's `/etc/ssh/sshd_config` edits.
- The **database** spec reliably retrieved
  `misconfigurations/exposed_database_no_auth.md` and produced PostgreSQL-
  specific tasks (`listen_addresses`, `pg_hba.conf`) - genuinely on-topic
  content - but failed to parse as YAML *both times* it was generated,
  on the same root cause: the LLM wrote
  `line: 'listen_addresses = '*''`, nesting an unescaped `'*'` inside an
  already single-quoted YAML scalar. This is a real, reproducible LLM
  output bug distinct from week 5's "ubuntu user" hallucination - not an
  infrastructure problem, and not fixed this week (rerolling twice and
  getting the identical failure both times is itself the finding; a
  templating/escaping fix on the *prompt* side would be the real fix, and
  is future work, not a week 6 patch).
- Separately, the SSH-bastion role surfaced its own new bug on inspection
  of an earlier run: a task named "Enable weak root login and password
  authentication" used `line: '\1 yes'` - a regex backreference syntax
  that `ansible.builtin.lineinfile`'s `line:` parameter does not support
  (backreferences only work in `regexp:`; `line:` is written literally).
  Applied for real, this task would write the literal string `\1 yes`
  into `sshd_config`, not `PermitRootLogin yes` - a claim that would
  silently fail its own stated purpose. This is exactly the kind of gap
  verify-vulnerabilities (below) exists to catch automatically instead of
  requiring someone to notice it by reading generated YAML.

So: real breadth, real structurally-distinct output for genuinely
different specs - and two new, real, reproducible LLM-output bugs found
in the process of proving it, neither of which is an infrastructure
problem. Both are left as documented findings rather than "fixed" -
fixing LLM output reliability broadly is corpus/prompt-engineering work
for a future week, not something to patch reactively per bug found this
week without turning into exactly the kind of gold-plating this project
has consistently avoided.

### verify-vulnerabilities: closing the claim-vs-reality gap for real

The RAG prompt (`prompts.py`) has always asked the LLM for a second part
beyond the YAML task list: an "Applied misconfigurations" section, one
claim per line. Until this week that text was generated, shown to the
user in the CLI transcript, and then discarded - never written to disk,
never checked against anything. `provision_spec()` now persists both the
original spec text (`spec.txt`) and the full raw LLM output
(`generation.md`) into every run directory, which is what makes checking
a run's claims possible after the fact at all (runs from before this
week don't have these files, and `verify-vulnerabilities` says so clearly
rather than pretending to check them).

`validate/vulnerabilities.py` does the checking:

1. **Parse** the "Applied misconfigurations" section into individual
   claims. The header's exact punctuation and the list marker (`1.` vs
   `-`) are not consistent across real generations - confirmed by seeing
   both `**Applied misconfigurations:**` and `**Applied
   misconfigurations**:` from the *same* spec run twice - so both are
   tolerated.
2. **Match** each claim to the specific task that's supposed to apply it.
   The prompt was tweaked this week to ask the LLM to quote the exact
   directive/line in backticks per claim (e.g. `` `PermitRootLogin yes` ``)
   - and, on real generations after the change, it mostly complied: the
   SSH-bastion run's claims backtick-quoted `Port 2222` and
   `PermitRootLogin yes` directly, both of which matched their
   `lineinfile` tasks' `line:` values exactly. Matching is deliberately
   only against `lineinfile` tasks' literal `line:` value - the one
   place a claim and a task are meant to say the exact same string -
   not fuzzy text similarity against prose.
3. **Boot, check, and attribute.** Matched claims become `DerivedCheck`s
   fed straight into the *existing* `test_deploy()` machinery from week
   5 - same boot/verify/destroy cycle, same `parse_task_attribution()`
   reading Ansible's own `changed`/`ok` output. No new boot/verify
   machinery was built; this module is entirely a new front end onto the
   one that already existed.
4. **Report every claim, not just the checkable ones.** A claim that
   matches no `lineinfile` task is reported `NOT VERIFIABLE` with an
   explicit reason, never silently dropped. This turned out to matter in
   practice, not just in principle: the Telnet/firewall run's three
   claims all named their *task*, not a config value, in backticks (e.g.
   `` `Install telnet server (deliberate misconfiguration)` ``) - and
   none of its tasks were `lineinfile` at all (`package`, `ufw` instead).
   All three come back `NOT VERIFIABLE`, correctly, because there is
   nothing here checkable by the current mechanism. Likewise, the
   audit-logging run's second claim (`0777` permissions on a shared
   directory) is real and true but expressed via `ansible.builtin.file`'s
   `mode:`, not `lineinfile` - also `NOT VERIFIABLE`, for the same
   honest reason, sitting right next to a `authpriv.none` claim from the
   *same run* that matched and verified cleanly. Coverage is per-claim,
   not per-run: a run can have both a fully checkable claim and an
   honestly-unverifiable one at the same time, and the report says so
   for each individually rather than reducing a whole run to one verdict.

This generalizes the ad-hoc manual SSH checks from week 3/4 by
construction (it reads whatever claims a given run's own generation
happened to produce), not by design intent alone - the Telnet/firewall
and audit-logging runs above are non-SSH proof of that, not just an
argument for it. What it does **not** yet do: verify claims expressed
through any module besides `lineinfile` (`file` mode/ownership, `ufw`
rules, `user` password strength, `package` presence-as-vulnerability).
Extending coverage module-by-module is real, bounded future work, not
attempted this week - `lineinfile` covers every claim seen so far that
has an unambiguous single "did this take effect" check, and reporting
the rest as `NOT VERIFIABLE` rather than guessing at a check for e.g. a
`ufw` policy is the more honest choice for a first version of this
command.

`aggregate_reports()` gained a matching `vulnerability_claims` stat
(claimed → verifiable → true-on-VM → attributed), the same shape as week
5's `artefact_checks` stat, feeding the same evaluation summary.

### The audit: storylines were decoupled from the VMs they described

The honest answer to the question this week opened with: **yes, they
were decoupled.** Reading `forensics/orchestrator.py` and
`scenarios.py` again with this specific question in mind (rather than
"does a storyline plant artefacts onto *a* VM," which was already true
and is a different, weaker claim): `provision_storyline()` feeds a
storyline's `base_spec` into the same `generate_vm_spec()` every other
run uses - so the VM itself is generated fresh, same as any run - but
each storyline's `artefacts` list was fixed Python data, written once at
authoring time in `scenarios.py`, with zero dependency on what that
particular generation actually produced. A `departing-employee-
exfiltration` storyline's entry-vector artefact (an off-hours SSH login)
was never checked against whether the VM generated for its `base_spec`
("Ubuntu workstation for a corporate employee...") had SSH weakened at
all - it was just always the same login-based narrative, regardless of
what got generated. For idea 3's own framing - "forensic scenario for
the generated VM," not a separate track running in parallel next to it -
that is a real gap, not a cosmetic one: a storyline could describe an
intrusion through a door that particular VM never actually had.

### Wiring: `storyline_builder.py`, entry vectors from verified claims

`forensics/storyline_builder.py` closes this for the one thing a
narrative most needs to get right: how the "attacker" got in.
`build_storyline_from_vulnerabilities()` takes a run's own
`VulnerabilityReport` (from `verify_vulnerabilities()` above) and:

- Picks the **first finding that is verifiable, true on the live VM, and
  attributed to this run's own role** (`attribution == "changed"`) as
  the entry vector. A claim that's merely `"ok"` - true, but already true
  before this run applied anything - does not qualify, on purpose: using
  one anyway would repeat the exact week 3 `PermitRootLogin` mistake one
  layer up, just inside a narrative instead of a validation report. No
  qualifying finding means `build_storyline_from_vulnerabilities()`
  raises rather than falling back to a generic, spec-decoupled story -
  the same "close it or park it, don't leave it silent" standard this
  whole thread has followed since week 5's attribution work.
- **Classifies** the entry vector by keyword against the claim text,
  its directive, and its task name (SSH / Telnet / database / firewall /
  a generic fallback naming the claim directly), and builds a narrative
  sentence and a log-line artefact (`generators.service_log_entry()`,
  generalized this week from the SSH-only `auth_log_entry()`) specific
  to that service - not a hardcoded `sshd` line regardless of what the
  actual entry vector was.
- Leaves what happens *after* entry generic (archiving data, copying it
  off, clearing history) - reusing the same `generators.py` functions
  `scenarios.py`'s hand-authored storylines already used. That part of
  the story genuinely doesn't depend on which specific misconfiguration
  let the attacker in, so genericity there isn't the same kind of gap.

The three original `scenarios.py` demo storylines are unchanged and kept
- they remain useful, deliberately varied narrative examples, and are
now honestly documented (here and in their own module docstring) as
hand-authored rather than run-derived. `storyline_builder.py` is the new,
additional path that actually closes the point-3 gap: a
`forensic-scenario-from-run <run_dir>` CLI command runs
`verify-vulnerabilities`, builds a storyline from the result, plants it,
and writes a `storyline.json` manifest (`Storyline`/`Artefact` are
already plain dataclasses; `save_storyline()`/`load_storyline()` just
(de)serialize them) that `test-deploy --storyline-file` can verify
against - the same `derive_checks_from_storyline()` / attribution /
blockinfile-batching machinery from week 5, unchanged, now reachable for
a storyline that isn't one of the three fixed demo ids.

### Live results: what three real, distinct runs actually did

Everything above (claim parsing, claim-to-task matching, entry-vector
classification, the "no qualifying claim → refuse" guard) is exercised by
unit tests against real, freshly-generated LLM output
(`tests/test_vulnerabilities.py`), not just hand-written fixtures. Three
of the runs from the corpus-breadth section above were then taken through
the full live cycle - `test-deploy`, `verify-vulnerabilities`,
`forensic-scenario-from-run`, `test-deploy --storyline-file` - on the
user's own elevated terminal (Hyper-V, as every live boot has needed
since week 3).

**SSH bastion: the full chain worked, and live testing caught a real bug
in the process.** `test-deploy` booted and verified all four config
checks, including `PermitRootLogin yes` reporting attribution `"ok"` -
the box already had it, not attributable to this run, the exact week 3
finding reproducing again on a completely independent run one release
later. `verify-vulnerabilities` matched both claims (`Port 2222`,
`PermitRootLogin yes`) and reported them correctly: `Port 2222` true and
attributed (`"changed"`), `PermitRootLogin yes` true but *not*
attributed (`"ok"`) - so `forensic-scenario-from-run` correctly picked
`Port 2222` as the only qualifying entry vector. But the *narrative text*
it generated still read "deliberately applied a weak SSH login (root
login and/or password authentication left enabled)" - describing the
disqualified claim, not the one that actually qualified. The
category-level description text (`_ENTRY_VECTORS` in
`storyline_builder.py`) had been written specifically enough that it
happened to describe `PermitRootLogin`, and got attached to *any* SSH
match regardless of which SSH claim actually qualified. This is exactly
the kind of bug this project's whole live-testing discipline exists to
catch - a unit test checking "does an SSH claim classify as SSH" would
never have caught it, because the bug was in what the *description*
claimed, not in the classification itself. Fixed the same day: the
category description is now deliberately generic ("a weakened SSH
configuration"), and the narrative separately quotes the specific
qualifying claim (`entry.directive`) by name, so it can never assert a
sub-detail the data didn't verify. A regression test
(`test_build_storyline_narrative_names_the_actual_verified_claim_not_just_its_category`)
was added against this exact scenario. The storyline was then
re-derived (from the same real, already-verified findings the live run
produced - not a new boot) with the fix in place; the corrected narrative
now reads "...applied a weakened SSH configuration - specifically, 'Port
2222'...". The already-planted, already-verified artefacts
(`artefacts_verified: True`, all 4 checks matched and attributed) were
unaffected by the bug - it lived only in the narrative/manifest text, not
in what got planted or how it was checked - so nothing needed replanting.

Also worth noting plainly: the claims list matched here (`Port 2222`,
`PermitRootLogin yes`) did not include `PasswordAuthentication yes` -
which the role also set, and which *did* verify as attributable
(`"changed"`) in the plain `test-deploy` run. The LLM's own "Applied
misconfigurations" section under-claimed relative to what its own role
actually did. `verify-vulnerabilities` and the storyline it feeds are
scoped to checking what the LLM *said* it applied, not auditing
everything a role does looking for candidate vulnerabilities - a
reasonable, deliberate scope boundary, but one this run makes concrete
rather than hypothetical.

**Audit-logging/permissions: two real, distinct boot failures, neither
in this project's own code.** First attempt failed inside the Ansible
run itself: a task named "Ensure shared directory is owned by root" used
`ansible.builtin.user` with a `path:` parameter - not a parameter that
module supports (`path:` belongs to `ansible.builtin.file`; the LLM
seems to have confused the two modules for a directory-ownership task).
A third distinct LLM-output bug this week, joining the Postgres
quote-nesting failure and the SSH `\1`-backreference bug in the same
"generated content that doesn't do what it claims" category - none of
these are fixed in code, deliberately, since fixing generation reliability
broadly is corpus/prompt work, not something to patch one bug at a time
as they're found. `verify-vulnerabilities`' own output on this run is
worth highlighting on its own merits, though: it correctly reported the
one matchable claim (`authpriv.none`) as unable to be checked ("the VM
never reached this check - boot likely failed before checks ran") rather
than a false pass or a crash, and correctly left the `0777`-permissions
claim `NOT VERIFIABLE` (that claim is expressed via `ansible.builtin.file`'s
`mode:`, a module this version doesn't cover) - both honest, both
distinguishable from each other in the same report. The *second* attempt
(re-running `verify-vulnerabilities`) failed for a completely unrelated
reason before Ansible even ran: `add-apt-repository ppa:ansible/ansible`
resolved to the non-existent `ppa:~ansible/ubuntu/ansible` on the guest -
a transient Launchpad PPA-resolution hiccup in `ansible_local`'s own
install-Ansible-on-first-use logic, unrelated to anything this project
generates or controls. Two failures, two unrelated causes, both correctly
surfaced with a real error rather than a silent hang or a false result -
consistent with `test_deploy()`'s error-capture behaviour holding up
under a failure mode nobody had hit before this run.
`forensic-scenario-from-run` correctly refused to build a storyline for
this run (no claim both verified and attributed) rather than guessing.

**Telnet/firewall: booted cleanly, confirming the "nothing checkable"
result from static analysis reflects the role's actual content, not a
gap in reading it.** `test-deploy` reported `config_verified: None` (no
`lineinfile` tasks exist to derive checks from) and otherwise booted and
provisioned without error - a real, different VM (Telnet installed, UFW
configured) coming up successfully, just with nothing the current
mechanism can check. This matches exactly what `verify-vulnerabilities`
had already reported without booting at all (all three claims `NOT
VERIFIABLE`, since none reference a `lineinfile` task) - the static
read and the live boot agree, which is itself a small but real piece of
evidence that the "not verifiable" determination isn't a false negative.

### The combined evaluation, across all eight runs so far

`report-summary` now aggregates week 5's five runs and week 6's three
new ones together (a `checkov`/`molecule`/`scans` field of `None` - the
fallback `verify-vulnerabilities`/`forensic-scenario-from-run` write
when no `report.json` exists yet for a run - turned out to crash
`aggregate_reports()` on first real use this week: `.get("scans", {})`
only supplies its default for a *missing* key, not one present with
value `None`. A fourth real bug this week, this time in this project's
own code rather than generated content - fixed with `(r.get("scans") or
{})`, with a regression test):

```
total_runs: 8
checkov:                         5/5 applicable  (1.0)
ansible_lint:                    3/5 applicable  (0.6)
molecule:                        0/5 applicable  (0.0)
test_deploy_booted:               5/7 applicable  (0.71)
test_deploy_config_verified:      3/3 applicable  (1.0)
test_deploy_artefacts_verified:   1/3 applicable  (0.33)
artefact_checks:      16 total, 12 matched (0.75), 16/16 attributed (1.0)
vulnerability_claims:  7 total claims
  verifiable:                     3/7   (0.43)
  true on the VM (of verifiable): 2/3   (0.67)
  attributed (of true):           1/2   (0.5)
```

Read together with the per-run detail above, this is a coherent, honest
picture rather than a single pass/fail number: `test_deploy_booted`
dropping to 0.71 is the audit-logging run's two real failures, not a
regression in anything that worked before. `test_deploy_artefacts_verified`
at 0.33 (1 of 3 forensic runs fully verified) reflects that only the SSH
run reached the artefact-planting stage this week - the audit-logging
run never got a qualifying entry vector to build a storyline around, and
that's the system correctly refusing rather than a failure to reach
100%. The `vulnerability_claims` numbers are the new, central result for
point 2 of this week's brief: of 7 real claims across three genuinely
different specs, 3 were checkable by the current (`lineinfile`-only)
mechanism, 2 of those were actually true on a live VM, and of those, only
1 was attributable to the run that claimed it - the other being the
`PermitRootLogin` "already true, not our doing" case this whole feature
exists to catch. A single run producing one attributable claim and one
non-attributable one, both correctly distinguished, is a small sample,
but it is a *real, live-verified* sample rather than an assertion the
mechanism works.

### Repairing known LLM-output bugs, and one command instead of four

Two follow-up requests came out of reviewing the week 6 results above:
fix the generation bugs that were found rather than just document them,
and collapse the four separate manual commands (`provision`,
`verify-vulnerabilities`, `forensic-scenario-from-run`,
`test-deploy --storyline-file`) a full scenario needs into one.

**`provision/repair.py`: a closed, narrow list of known-shape fixes, not
a general "make the LLM's YAML valid" system.** Three patterns from
earlier this week get recognized and repaired automatically now:

- The Postgres nested-quote failure (`line: 'listen_addresses = '*''`) -
  fixed by finding the exact line PyYAML's own parse error points at and
  re-emitting its value as a properly escaped double-quoted YAML string.
  Live-tested against a fresh generation of the same spec: it worked, but
  surfaced a *second*, related failure the fix hadn't accounted for -
  `line: 'listen_addresses = \'localhost\''`, the LLM applying Python/JS-
  style backslash escaping that single-quoted YAML has no syntax for at
  all. The first version of the repair produced technically-valid YAML
  that still carried the literal, bogus backslashes into the config value
  it wrote - parseable, but wrong for the file it targets. Fixed by also
  stripping `\'`/`\"` sequences before re-quoting (single-quoted YAML
  never has a legitimate use for either), then re-verified live against
  the same spec a third time - correct output, no backslashes, valid
  postgresql.conf syntax.
- The SSH `\1`-backreference misuse (`regexp` capturing
  `(PermitRootLogin|PasswordAuthentication)`, `line: '\1 yes'`, which
  `lineinfile`'s `line:` writes literally rather than as a regex
  replacement) - fixed by splitting one broken task into one task per
  alternative, each with the backreference resolved to that alternative's
  own literal name. Verified against the exact real broken YAML captured
  earlier this week (unit test, not yet re-rolled live - this pattern
  doesn't depend on PyYAML error-location parsing the way the quote fix
  does, so it's lower-risk to trust from a unit test alone).
- The `ansible.builtin.user`/`path:` misuse (a task trying to set
  directory ownership through the wrong module entirely) - fixed by
  rewriting it to the `ansible.builtin.file` task it was actually trying
  to express. Also verified via unit test against the real captured bug,
  not yet re-rolled live.

Every repair is recorded and surfaced, never applied silently - `provision`
and `build-scenario` both print "Auto-repaired N known issue(s)" with
what changed. `tasks/main.yml` on disk reflects the *repaired* tasks;
the LLM's original, unrepaired text is still recoverable from
`generation.md` for anyone who wants to see exactly what was fixed.
Deliberately not attempted: a general repair loop (feed the parse error
back to the LLM and ask it to fix its own YAML) - that trades one
unreliable generation step for two, and every pattern found so far has
had a small, specific, well-understood fix once actually looked at.

**`build-scenario <spec>`: one command, chaining what four used to do
separately.** `provision` → `verify-vulnerabilities` (its own boot+destroy
cycle) → `build_storyline_from_vulnerabilities()` → plant the artefact
role → a final boot that verifies both config and planted evidence. Two
live boots total, down from the four separate commands' effective total
of up to four - `verify-vulnerabilities` still needs its own boot (there's
no way to know what's attributable without watching Ansible apply it
live), but the final `test-deploy`-equivalent boot now does verification
*and* image export in the same cycle rather than needing a separate call.

**Image export, the actual new capability behind "give me a file I can
open in VirtualBox/VMware," not just a recipe.** `test_deploy()` gained a
`post_verify_hook` parameter - called after checks complete but before
`destroy()`, the one point a booted, verified VM is guaranteed to still
exist. `build-scenario` passes a hook that exports the VM's disk
(`imaging/image_export.py`): Hyper-V's `Export-VM` cmdlet copies the disk
safely (including a live VM's - unlike a raw file copy, which risks
reading a locked file, and unlike `Convert-VHD`, which only converts
between Microsoft's own VHD/VHDX formats), then `qemu-img` (run through
the existing WSL bridge - not found installed natively on Windows or
already inside WSL on this machine; `scripts/check_wsl_tools.py` now
checks for it and prints the one-line install command, same "never
installs without asking" policy as ansible-lint/Molecule) converts the
VHDX to VMDK, which both VirtualBox and VMware can import directly as a
disk. The VM still gets destroyed afterward - the export happens *before*
that, not instead of it, so the "never leaves a VM running" guarantee
every other command here has holds for this one too, while still
producing a real, portable file rather than just a re-runnable recipe.
A deterministic Hyper-V VM name (`h.vmname` in the Vagrantfile template,
set to the same hostname `provision_spec()` already generates) makes the
VM findable by name for export, instead of needing to parse Vagrant's
own internal `.vagrant/` state - confirmed `vmname` is a real Hyper-V
provider attribute against Vagrant's own `config.rb` source before
relying on it, having been burned once already this project assuming a
provider option existed (`vmswitch`, week 5) that didn't.

**Honestly: the export step is unverified against a real boot as of this
version.** Every other Hyper-V-touching mechanism in this project needed
at least one round of live iteration before it worked - the switch prompt
hang, the privileged-shell-provisioner bug, `test_deploy()` not always
destroying, and others, all in the dedicated bug lists above. There is no
reason to expect `Export-VM`/`qemu-img` to be different, and no claim
here that it is. What's solid: `test_deploy()`'s new hook mechanism
(unit-tested, including that a hook failure still lets `destroy()` run),
and the `vmname` Vagrantfile change (confirmed rendering correctly for a
real run). What's not yet proven: whether `Export-VM` succeeds against a
Vagrant-managed Hyper-V VM the way it's called here, and whether the
resulting VMDK actually opens cleanly in VirtualBox or VMware - both
need the user's own elevated terminal and a live `build-scenario` run to
find out, the same as everything else this project has needed it for.

## Libraries and tools

- **FastAPI** — the HTTP interface (`POST /generate`). Chosen over Flask
  for built-in request/response validation via Pydantic models, which
  matters once the response shape includes structured fields like
  `snippets` rather than a single string.
- **Uvicorn** — the ASGI server FastAPI runs on; the standard pairing for
  a FastAPI app, no alternative seriously considered.
- **`ollama` (Python client)** — talks to the local Ollama server for text
  generation. Chosen over raw `requests` calls to `/api/generate` for
  built-in request/response handling; see week 1 rationale above.
- **click** — the CLI framework. Chosen over `argparse` for declarative
  option/argument definitions (`@click.option`, `@click.argument`) that
  stay readable as the CLI grows more flags (this week added `--no-rag`).
- **langchain-core** — provides the `Document` schema and retriever
  interface the RAG path is built on. Used instead of the full `langchain`
  package; see the LangChain section above for why.
- **langchain-ollama** — provides `OllamaEmbeddings`, a LangChain-compatible
  wrapper around Ollama's embedding endpoint. Used instead of calling
  `ollama.Client().embeddings()` directly because `langchain-chroma`
  expects a LangChain `Embeddings` interface, and the official adapter is
  less code than hand-writing an equivalent wrapper.
- **langchain-chroma** — the LangChain integration for the Chroma vector
  store. See the vector store rationale above.
- **chromadb** — the underlying embedded vector database `langchain-chroma`
  wraps. Not called directly at the moment; depended on explicitly (rather
  than left as a transitive dependency) because `vectorstore.py` may need
  to reach into it directly in a later week (e.g. for the staleness check
  noted above).
- **pytest** — the test runner. No alternative considered; it is the
  de facto standard for this kind of project.
- **httpx** — a `pytest`-time dependency only, required by FastAPI's
  `TestClient` for in-process request testing.
- **PyYAML** — parses and validates the YAML block extracted from LLM
  output in `ansible_writer.py`. Already present as a transitive dependency
  of other packages before week 3; made an explicit direct dependency now
  that the project imports it itself. Chosen over `ruamel.yaml` because
  nothing here round-trips a YAML document (load, edit, re-dump) — the
  validated text is written to disk verbatim, so `ruamel.yaml`'s comment-
  and formatting-preserving round-trip would be paying for a capability
  this code path never uses; see the week 3 parsing section above.
- **python-hcl2** — parses `.pkr.hcl` into Python data structures for
  `hcl_check.py`'s structural validation. Runs natively everywhere (pure
  Python, no `ansible-core`-style POSIX dependency); the only HCL parser
  seriously considered, since it's the standard choice for this in Python.
- **checkov** — the Ansible-framework security/policy scanner
  (`scanners.run_checkov`). Runs natively on Windows for the same reason
  python-hcl2 does. A large dependency (pulls in `boto3`, `cryptography`,
  and much more Checkov doesn't need for the narrow Ansible-only use this
  project makes of it) — accepted as the cost of using an actively
  maintained, multi-framework scanner that already has *some* Ansible
  checks, rather than hand-rolling policy checks from scratch. See the
  week 4 section above for the honest limit on what those checks actually
  cover.
- **python-vagrant** — wraps the `vagrant` CLI for `test_deploy.py`'s
  boot/verify/destroy automation. The only actively maintained Python
  wrapper for Vagrant; the alternative (shelling out to `vagrant` directly
  and parsing text output) is what this library exists to avoid, though
  building on it surfaced a real gap (see the `check_call` note above)
  that had to be worked around rather than solved by the library itself.
- **ansible-lint** and **Molecule** (+ **molecule-plugins**) — *not*
  Python dependencies of this project (not in `pyproject.toml`). Both are
  invoked via `wsl_bridge.run_posix_tool()`, installed inside WSL locally
  or in the CI runner's own environment, never imported by this Windows
  venv — see the week 4 Windows/POSIX section above for why.
- **Faker** — synthetic evidence content for the forensic scenarios
  (`forensics/generators.py`): names, emails, IPs, filenames, timestamps.
  Already justified in the project's research tracker as the reason the
  forensic track doesn't need ethics approval (synthetic-only data); no
  new justification needed here beyond confirming the actual usage
  matches that justification, which `generators.py`'s own module
  docstring exists to keep true.
- **libguestfs** — investigated, not adopted. See the week 5
  libguestfs-vs-Ansible section above for the full reasoning (KVM
  acceleration is available in WSL2 on this machine, which was the
  promising finding, but the VHDX lifecycle mismatch and the fact that
  every planned artefact type is achievable from inside the guest
  outweighed it). Not installed, not a dependency; recorded here so a
  future revisit doesn't have to re-derive the same investigation.

Outside Python: **Packer** and **Vagrant** (HashiCorp CLI tools) generate
and boot the VM — `packer/ubuntu-base.pkr.hcl` and the generated per-run
`Vagrantfile`s call them, respectively. Vagrant requires a provider: this
project uses **Hyper-V** on the dev machine (week 3), with **VirtualBox**
still what the (unwired) Packer template targets (`virtualbox-iso`
builder) — a known mismatch, noted in the week 3 section, that matters
once the Packer box is actually wired in (still not wired in as of week
5 — see Known limitations below). **Docker** is what CI's Molecule
scenario uses (hosted runners support it natively); **WSL2** is what
`ansible-lint`/Molecule run inside of locally, on Windows.
- **qemu-img** (week 6) — converts the VHDX `build-scenario` exports from
  Hyper-V into a VMDK VirtualBox/VMware can import directly
  (`imaging/image_export.py`). Not found installed natively on Windows or
  already inside WSL on this machine when checked; runs through the same
  WSL bridge `ansible-lint`/Molecule already use, since it's a system
  package (`apt install qemu-utils`), not a Python one -
  `scripts/check_wsl_tools.py` checks for it and prints the one-line
  install command rather than installing it unasked, same policy as the
  other WSL-side tools.

## Known limitations going into week 7

- The knowledge corpus's *breadth* is no longer the open question week 5
  left it as - week 6 proved genuinely distinct specs produce genuinely
  distinct roles (SSH bastion, Telnet/firewall, audit-logging/permissions,
  an attempted database spec - see the week 6 section above), not the
  same SSH content reskinned. What week 6 exposed instead was a
  *reliability* gap sitting behind that breadth - three real, reproducible
  content bugs (a YAML nested-quote failure with two distinct variants, a
  `\1`-backreference in `lineinfile`'s `line:`, and an
  `ansible.builtin.user`/`path:` misuse). All three now have an automatic
  repair (`provision/repair.py`), live-verified for the quote-nesting one
  (re-rolled the same spec twice more after each fix, both clean), unit-
  tested against the real captured bugs for the other two. This closes
  the *specific* instances found, not the underlying reliability gap
  itself - the repair list is closed and narrow by design (three known
  shapes, not a general "fix any broken YAML" system), so a fourth,
  differently-shaped generation bug would fail exactly as before until
  someone finds it and adds a fourth repair. The corpus retrieves the
  right *topic* reliably; the LLM's ability to correctly operate the
  specific Ansible module it picks for that topic remains inconsistent in
  ways this project can only catch after the fact, one pattern at a time.
- verify-vulnerabilities (week 6) only checks claims expressed via
  `ansible.builtin.lineinfile`'s `line:` value - the one place a claim and
  a task are guaranteed to say the same string. Real runs this week
  produced claims about `ufw` policy, `ansible.builtin.file` permissions,
  and task names quoted verbatim in place of a directive - all correctly
  reported `NOT VERIFIABLE`, none silently dropped, but none checkable
  either. Extending coverage module-by-module is bounded future work, not
  attempted this week - see the week 6 section for the reasoning.
- verify-vulnerabilities and the storylines built from it are scoped to
  what the LLM's own "Applied misconfigurations" section *claimed*, not
  everything a role's tasks actually do. The SSH bastion run this week
  made this concrete: `PasswordAuthentication yes` was real, live-verified,
  and attributable (`"changed"`) in a plain `test-deploy` run, but was
  never claimed in generation.md at all, so it was invisible to
  verify-vulnerabilities and never eligible as a storyline's entry
  vector. The LLM under-claims sometimes, not just over-claims/hallucinates
  - a real, distinct failure direction from the ones week 5 and 6 had
  already found.
- There is no cache-invalidation check between `knowledge/` and the
  persisted `.chroma/` store — edits to the corpus require deleting
  `.chroma/` by hand.
- There is no automated comparison metric between grounded and ungrounded
  output yet, only the ability to produce both for the same spec; building
  an actual evaluation metric is deferred to the dissertation's evaluation
  chapter.
- There is no cache-invalidation check between `knowledge/` and the
  persisted `.chroma/` store — edits to the corpus require deleting
  `.chroma/` by hand.
- There is no automated comparison metric between grounded and ungrounded
  output yet, only the ability to produce both for the same spec; building
  an actual evaluation metric is deferred to the dissertation's evaluation
  chapter.
- `packer/ubuntu-base.pkr.hcl` has not been built or verified and is not
  wired into the Vagrantfiles `provision` generates, and still specifically
  targets the wrong provider for this machine's actual Vagrant setup
  (VirtualBox vs. Hyper-V) — flagged again this week (the brief's own
  "loose end, not this week's job") since it remains true; see the
  Packer-vs-stock-box and week 4 Packer-provider sections above.
- Only one Ansible role per run is supported for the *scenario* role (a
  single `role_name`) - the forensic track's `forensic_artefacts` role
  (week 5) is a deliberate, additional exception to this, not a general
  multi-role capability.
- Checkov's Ansible framework covers 6 built-in checks, none of which
  match the modules this project's generated roles actually use — a
  `passed: true` from Checkov in `report.json` currently means "nothing
  applicable was found to check," not "this role was verified secure."
  Still true of the forensic artefact roles too, confirmed this week
  (checkov passes them for the same "nothing applicable" reason). See
  the week 4 section for the full reasoning.
- **Attribution is closed for `test_deploy.py`**, both the scenario
  role's own config checks and (new this week) forensic artefact checks -
  see the week 5 section above. Not closed: whether the *end state a
  check observes* is itself reliably persistent for every kind of target.
  Two specific target types (`/var/log/auth.log`, and the actively
  SSH-connected user's `.bash_history`) were found this week to not
  reliably hold written content through to verification time, for
  reasons not fully root-caused - see the dedicated section above. Every
  planting *task* was still correctly attributed as having run
  (12/12 this week's data) - the gap is specifically in end-state
  persistence for those two target types, not in the attribution
  mechanism itself.
- CI (`.github/workflows/validate.yml`) is pushed, has actually run, and
  both jobs pass as of this week - closing the limitation carried over
  from week 4. Getting there took five real, distinct bugs (missing
  `ansible-lint` install, a Python-version mismatch in the Docker image,
  an `ansible-lint` scope bug that was silently dropping real findings
  even locally, a systemd-in-Docker setup issue, and a stale apt cache) -
  see the dedicated CI section above for the full account.
- `test-deploy` has now completed real, successful end-to-end runs (boot,
  verify, destroy) for both the original SSH-pentesting scenario and two
  of the three forensic storylines - closing the "never completed an
  actual VM boot" limitation from week 4. Getting there surfaced six more
  real bugs specific to live Hyper-V boots (the switch-selection hang, a
  privileged-shell-provisioner ownership bug, `test_deploy()` not always
  destroying, missing parent directories for artefacts, a self-destructive
  artefact, and a stale file-copy issue) - see the dedicated section
  above. One forensic scenario (`sabotage-before-offboarding`) never
  completed a boot at all, for a genuine LLM-content reason (the corpus-
  gap finding above), not an infrastructure one.
- Vagrant's own state can still go stale in ways this project's code
  doesn't fully clean up: a `vagrant up` interrupted mid-way (a Ctrl+C,
  say) can leave a lock that blocks the next attempt against the same
  run directory, needing a manual `vagrant destroy -f` to clear - `test_deploy()`
  destroying more reliably now (see above) narrows this window
  considerably but doesn't eliminate the case of the process itself being
  killed before `finally` can run. Molecule's ephemeral directory naming
  (derived from the role's own directory name, not the full per-run path)
  is a related, separate gap, not fixed this week - a real operational
  consideration for any future automated/repeated test-deploy runs.
- `forensicforge validate`, run a second time after `test-deploy`, used to
  silently destroy the recorded `test_deploy` results (fixed week 5) -
  flagged here as a reminder that the fix is not yet exercised across many
  repeated validate/test-deploy cycles in sequence.
- `aggregate_reports()` crashed (`AttributeError`) on any report.json with
  `scans`/`molecule` explicitly `None` - the fallback dict
  `verify-vulnerabilities`/`forensic-scenario-from-run` write when no
  report.json exists yet for a run. `.get("scans", {})`'s default only
  applies to a *missing* key, not a present one holding `None`. Fixed
  this week (`(r.get("scans") or {})`) with a regression test - the first
  bug this week found in this project's own code rather than in LLM-
  generated content, and found by running the CLI end-to-end against real
  runs rather than by code review or unit tests alone.
- `storyline_builder.py`'s per-category entry-vector description
  (`_ENTRY_VECTORS`) was, until a live run caught it, specific enough to
  assert details ("root login and/or password authentication left
  enabled") that a *particular* qualifying claim within that category
  hadn't actually verified - see the week 6 live-results section above
  for the exact run that surfaced this. Fixed by making the category
  description generic and having the narrative separately name the
  specific verified claim; a regression test was added. Worth flagging
  as a class of bug, not just an instance: any future addition to
  `_ENTRY_VECTORS` needs to stay generic at the category level for the
  same reason, since the fix pattern (name the specific claim separately)
  isn't structurally enforced - a future contributor could reintroduce
  the same mistake for a new category without the regression test
  covering it (it only covers SSH).
- The audit-logging run's two consecutive live-boot failures (a real
  `ansible.builtin.user`/`path:` content bug, then an unrelated transient
  Launchpad PPA-resolution failure on retry) meant no second forensic
  storyline was built end-to-end this week beyond the SSH one - the
  point-3 wiring is demonstrated for exactly one run, live, not several.
  The refuse-rather-than-fake behaviour when no claim qualifies is itself
  now live-verified (this run hit it for real), which is a real, useful
  result on its own, but a second successful full chain (ideally through
  a non-SSH entry vector, since the SSH one already worked) remains open.
- `build-scenario`'s image-export step (`imaging/image_export.py`,
  `Export-VM` + `qemu-img`) has not been through a live boot yet - see
  its own dedicated section above for exactly what is and isn't proven
  so far. Needs a real `build-scenario` run, with `qemu-utils` installed
  in WSL first (`scripts/check_wsl_tools.py` prints the exact command),
  to find out whether it actually works.
- `provision/repair.py`'s repair list is deliberately closed and narrow -
  three specific, real bug shapes, not a general YAML/Ansible-correctness
  checker. A generation bug of a different shape (there is no reason to
  expect the three found so far are the only ones the corpus can produce)
  fails exactly as before, with no repair attempted, until it's found and
  a fourth pattern is added.
