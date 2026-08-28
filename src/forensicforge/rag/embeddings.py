from langchain_ollama import OllamaEmbeddings

from .. import config


def get_embeddings() -> OllamaEmbeddings:
    """Local embedding model served by Ollama - the RAG-equivalent of get_backend()."""
    return OllamaEmbeddings(model=config.EMBEDDING_MODEL, base_url=config.OLLAMA_HOST)
