import pytest
from fastapi.testclient import TestClient

from forensicforge import config
from forensicforge.api import app

from conftest import model_available

pytestmark = pytest.mark.skipif(
    not (model_available(config.MODEL_NAME) and model_available(config.EMBEDDING_MODEL)),
    reason=(
        f"Ollama not running or one of '{config.MODEL_NAME}' / "
        f"'{config.EMBEDDING_MODEL}' not pulled locally"
    ),
)

client = TestClient(app)


def test_generate_returns_nonempty_text():
    response = client.post(
        "/generate",
        json={"spec": "Ubuntu server VM with a deliberately weak SSH config for a pentesting exercise"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["output"], str)
    assert body["output"].strip() != ""
    assert len(body["snippets"]) > 0
