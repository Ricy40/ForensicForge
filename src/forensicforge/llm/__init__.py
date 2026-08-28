from .base import LLMBackend
from .ollama_backend import OllamaBackend


def get_backend() -> LLMBackend:
    """Return the active LLM backend.

    Single swap point for later weeks: once a hosted backend (OpenAI,
    Anthropic, ...) is implemented, this is the only place that needs
    to change to select between them (e.g. via a config flag).
    """
    return OllamaBackend()


__all__ = ["LLMBackend", "OllamaBackend", "get_backend"]
