import ollama

from forensicforge import config


def model_available(model: str) -> bool:
    try:
        ollama.Client(host=config.OLLAMA_HOST).show(model)
        return True
    except Exception:
        return False
