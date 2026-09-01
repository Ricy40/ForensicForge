import os
from pathlib import Path

# Where the local Ollama server is listening.
OLLAMA_HOST = os.environ.get("FORENSICFORGE_OLLAMA_HOST", "http://localhost:11434")

# Default model used for generation. Must already be pulled locally
# (see scripts/check_ollama.py). Override with FORENSICFORGE_MODEL.
MODEL_NAME = os.environ.get("FORENSICFORGE_MODEL", "qwen2.5-coder:7b")

# Embedding model used for the RAG corpus. Must already be pulled locally
# (see scripts/check_ollama.py). Override with FORENSICFORGE_EMBEDDING_MODEL.
EMBEDDING_MODEL = os.environ.get("FORENSICFORGE_EMBEDDING_MODEL", "nomic-embed-text")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Source markdown corpus retrieval is grounded in.
KNOWLEDGE_DIR = Path(os.environ.get("FORENSICFORGE_KNOWLEDGE_DIR", PROJECT_ROOT / "knowledge"))

# Where the persistent Chroma vector store lives. Derived from KNOWLEDGE_DIR
# on first run; safe to delete to force a rebuild.
VECTORSTORE_DIR = Path(os.environ.get("FORENSICFORGE_VECTORSTORE_DIR", PROJECT_ROOT / ".chroma"))

# Number of corpus snippets retrieved per request.
RETRIEVAL_K = int(os.environ.get("FORENSICFORGE_RETRIEVAL_K", "4"))

# Where per-run `provision` output (Ansible role + Vagrantfile) is written.
# Each run gets its own subdirectory named after its run-id.
GENERATED_DIR = Path(os.environ.get("FORENSICFORGE_GENERATED_DIR", PROJECT_ROOT / "generated"))

# Stock Vagrant box the generated Vagrantfile boots by default. See
# docs/METHODOLOGY.md for why this is a stock box rather than the
# Packer-built one in packer/ this week.
VAGRANT_BOX = os.environ.get("FORENSICFORGE_VAGRANT_BOX", "generic/ubuntu2004")

# Vagrant provider used for both `provision`-generated Vagrantfiles and
# test-deploy. See docs/METHODOLOGY.md (week 3) for why this is Hyper-V
# rather than VirtualBox on this machine specifically.
VAGRANT_PROVIDER = os.environ.get("FORENSICFORGE_VAGRANT_PROVIDER", "hyperv")

# Hyper-V virtual switch the generated Vagrantfile attaches to. Without
# this set explicitly, `vagrant up` prompts interactively ("What switch
# would you like to use?") whenever more than one switch exists - which
# test_deploy() can never answer (no stdin is fed to it), so it just
# hangs forever. "Default Switch" is the NAT switch Windows creates
# automatically when Hyper-V is enabled - see docs/METHODOLOGY.md (week 5).
VAGRANT_HYPERV_SWITCH = os.environ.get("FORENSICFORGE_VAGRANT_HYPERV_SWITCH", "Default Switch")

# ansible-lint and Molecule depend on ansible-core, which needs POSIX-only
# stdlib modules (grp, fcntl) not present on Windows. Both are invoked
# through WSL instead of the local venv - see docs/METHODOLOGY.md (week 4)
# for why, and scripts/check_wsl_tools.py for the setup this requires
# inside the WSL distro itself (a *separate* install from this venv).
WSL_DISTRO = os.environ.get("FORENSICFORGE_WSL_DISTRO")  # None = WSL's default distro
RUNS_ON_WINDOWS = os.name == "nt"

# Dedicated venv inside WSL where ansible-lint/molecule are installed
# (Ubuntu's system Python is externally-managed per PEP 668, and there's
# no reason to mix these into whatever else the user's WSL distro is
# used for). A WSL-side path, not a Windows one - always POSIX/~-relative.
WSL_TOOLS_VENV = os.environ.get("FORENSICFORGE_WSL_TOOLS_VENV", "~/.forensicforge-tools")

# Name of the report file written per test-deploy/validate run.
REPORT_FILENAME = "report.json"

# Per-run files persisting what `provision_spec()` actually asked for and
# actually got back from the LLM - needed by verify-vulnerabilities (week 6)
# to check a run's *own* claimed misconfigurations rather than a hardcoded
# SSH-specific list. Not written before week 6, so older runs under
# generated/ won't have them - see docs/METHODOLOGY.md (week 6).
SPEC_FILENAME = "spec.txt"
GENERATION_FILENAME = "generation.md"
RETRIEVAL_FILENAME = "retrieval.json"
