import ollama

from .. import config
from .base import LLMBackend


class OllamaBackend(LLMBackend):
    """Talks to a local Ollama server via the official `ollama` Python client."""

    def __init__(self, model: str = config.MODEL_NAME, host: str = config.OLLAMA_HOST):
        self._client = ollama.Client(host=host)
        self._model = model

    def generate(self, prompt: str) -> str:
        response = self._client.generate(model=self._model, prompt=prompt)
        return response["response"]
