from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from .. import config
from .vectorstore import load_vectorstore


def get_retriever(k: int | None = None) -> BaseRetriever:
    vectorstore = load_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": k or config.RETRIEVAL_K})


def retrieve(spec: str, k: int | None = None) -> list[Document]:
    return get_retriever(k=k).invoke(spec)
