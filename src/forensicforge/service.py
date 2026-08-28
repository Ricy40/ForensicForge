from dataclasses import dataclass, field

from .llm import get_backend
from .prompts import build_prompt
from .rag.chain import Snippet, run_rag_chain


@dataclass
class GenerationResult:
    output: str
    snippets: list[Snippet] = field(default_factory=list)


def generate_vm_spec(spec: str, use_rag: bool = True) -> GenerationResult:
    """Shared entry point used by both the API and the CLI.

    use_rag=True (default) grounds generation in the knowledge/ corpus via
    the RAG chain. use_rag=False reproduces the week-1 ungrounded prompt,
    kept around so grounded vs ungrounded output can be compared directly.
    """
    backend = get_backend()

    if use_rag:
        result = run_rag_chain(spec, backend)
        return GenerationResult(output=result.output, snippets=result.snippets)

    prompt = build_prompt(spec)
    return GenerationResult(output=backend.generate(prompt))
