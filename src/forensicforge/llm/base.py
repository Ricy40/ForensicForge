from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """Common interface every LLM backend (local or hosted) must implement."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Send a prompt to the backend and return the raw text completion."""
