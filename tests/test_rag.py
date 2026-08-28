import pytest

from forensicforge import config
from forensicforge.rag.retriever import retrieve
from forensicforge.service import generate_vm_spec

from conftest import model_available

SPEC = "Ubuntu server VM with a deliberately weak SSH config for a pentesting exercise"

pytestmark = pytest.mark.skipif(
    not (model_available(config.MODEL_NAME) and model_available(config.EMBEDDING_MODEL)),
    reason=(
        f"Ollama not running or one of '{config.MODEL_NAME}' / "
        f"'{config.EMBEDDING_MODEL}' not pulled locally"
    ),
)


def test_retrieval_returns_relevant_snippets():
    docs = retrieve(SPEC)
    assert len(docs) > 0
    sources = [doc.metadata["source"] for doc in docs]
    assert any("ssh" in source.lower() or "misconfigurations" in source.lower() for source in sources)


def test_rag_output_differs_from_ungrounded_output():
    rag_result = generate_vm_spec(SPEC, use_rag=True)
    plain_result = generate_vm_spec(SPEC, use_rag=False)

    assert rag_result.output.strip() != ""
    assert plain_result.output.strip() != ""
    assert rag_result.output != plain_result.output

    assert len(rag_result.snippets) > 0
    assert len(plain_result.snippets) == 0
