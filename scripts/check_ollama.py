"""Check that Ollama is installed, running, and has a code-capable model and
an embedding model pulled.

Never pulls a model without asking first - models are multi-gigabyte
downloads.
"""

import shutil
import subprocess
import sys

import ollama

OLLAMA_HOST = "http://localhost:11434"

# Reasonable local coder models in the ~7-14B range as of writing. Check
# https://ollama.com/search?c=code for what's current before pulling -
# new versions show up often.
RECOMMENDED_CODE_MODELS = [
    ("qwen2.5-coder:7b", "~4.7 GB - good default, strong at code/config generation"),
    ("qwen2.5-coder:14b", "~9 GB - stronger reasoning, needs more RAM/VRAM"),
    ("deepseek-coder-v2:16b", "~8.9 GB - mixture-of-experts, strong alternative"),
]
CODE_MODEL_KEYWORDS = ("coder", "code", "starcoder", "codellama")

# Local embedding models for the RAG corpus. Check
# https://ollama.com/search?c=embedding for what's current before pulling.
RECOMMENDED_EMBEDDING_MODELS = [
    ("nomic-embed-text", "~274 MB - good default, large context window, widely used"),
    ("mxbai-embed-large", "~670 MB - larger/stronger, more RAM/VRAM"),
    ("bge-m3", "~1.2 GB - multilingual, strong alternative"),
]
EMBEDDING_MODEL_KEYWORDS = ("embed",)


def check_binary_installed() -> bool:
    return shutil.which("ollama") is not None


def list_installed_models() -> list[str] | None:
    """Return installed model names, or None if the server isn't reachable."""
    try:
        response = ollama.Client(host=OLLAMA_HOST).list()
    except Exception:
        return None
    names = []
    for m in response.models:
        name = getattr(m, "model", None) or getattr(m, "name", None)
        if name:
            names.append(name)
    return names


def has_model(models: list[str], keywords: tuple[str, ...]) -> bool:
    return any(any(k in name.lower() for k in keywords) for name in models)


def prompt_pull(model: str) -> None:
    answer = input(f"Pull '{model}' now? [y/N] ").strip().lower()
    if answer == "y":
        subprocess.run(["ollama", "pull", model], check=True)
    else:
        print(f"Skipped. Pull it manually later with: ollama pull {model}")


def check_category(models: list[str], keywords: tuple[str, ...], label: str,
                    library_url: str, recommended: list[tuple[str, str]]) -> None:
    if has_model(models, keywords):
        print(f"A {label} model is already installed.")
        return

    print(f"No {label} model found locally. Suggested options "
          f"(double-check {library_url} for anything newer):")
    for name, note in recommended:
        print(f"  - {name}  {note}")
    prompt_pull(recommended[0][0])


def main() -> int:
    if not check_binary_installed():
        print("Ollama is not installed. Install it from https://ollama.com/download")
        return 1

    models = list_installed_models()
    if models is None:
        print(
            "Ollama is installed but the server doesn't seem to be running.\n"
            "Start it (the Ollama app, or `ollama serve`) and re-run this script."
        )
        return 1

    print(f"Ollama is running. Installed models: {models or '(none)'}")

    check_category(
        models, CODE_MODEL_KEYWORDS, "code-capable",
        "https://ollama.com/search?c=code", RECOMMENDED_CODE_MODELS,
    )
    check_category(
        models, EMBEDDING_MODEL_KEYWORDS, "embedding",
        "https://ollama.com/search?c=embedding", RECOMMENDED_EMBEDDING_MODELS,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
