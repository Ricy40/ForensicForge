from langchain_chroma import Chroma
from langchain_core.documents import Document

from .. import config
from .embeddings import get_embeddings

COLLECTION_NAME = "knowledge_corpus"


def _load_corpus_documents() -> list[Document]:
    documents = []
    for path in sorted(config.KNOWLEDGE_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        source = path.relative_to(config.KNOWLEDGE_DIR).as_posix()
        documents.append(Document(page_content=text, metadata={"source": source}))
    return documents


def build_vectorstore() -> Chroma:
    """(Re)build the persistent vector store from knowledge/ on disk."""
    documents = _load_corpus_documents()
    if not documents:
        raise RuntimeError(f"No corpus documents found under {config.KNOWLEDGE_DIR}")
    return Chroma.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        collection_name=COLLECTION_NAME,
        persist_directory=str(config.VECTORSTORE_DIR),
    )


def load_vectorstore() -> Chroma:
    """Load the persistent vector store, building it on first run.

    Delete FORENSICFORGE_VECTORSTORE_DIR (default `.chroma/`) to force a
    rebuild after editing the knowledge/ corpus.
    """
    if not config.VECTORSTORE_DIR.exists():
        return build_vectorstore()
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(config.VECTORSTORE_DIR),
    )
