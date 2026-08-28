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
