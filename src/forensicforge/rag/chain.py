from dataclasses import dataclass

from ..llm.base import LLMBackend
from ..prompts import build_rag_prompt
from .retriever import retrieve


@dataclass
class Snippet:
    source: str
    content: str


@dataclass
class RagResult:
    output: str
    snippets: list[Snippet]


def run_rag_chain(spec: str, backend: LLMBackend, k: int | None = None) -> RagResult:
    """Retrieve grounding snippets, compose a prompt, and generate through backend.

    This is the orchestration step: retrieval and prompt composition are
    handled here (via LangChain's Chroma retriever), while text generation
    still goes through the same LLMBackend interface from week 1 - RAG
    changes what we ask the model, not how we talk to it.
    """
    docs = retrieve(spec, k=k)
    prompt = build_rag_prompt(spec, docs)
    output = backend.generate(prompt)
    snippets = [
        Snippet(source=doc.metadata.get("source", "unknown"), content=doc.page_content)
        for doc in docs
    ]
    return RagResult(output=output, snippets=snippets)
