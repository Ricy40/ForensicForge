from fastapi import FastAPI
from pydantic import BaseModel

from .service import generate_vm_spec

app = FastAPI(title="ForensicForge")


class GenerateRequest(BaseModel):
    spec: str
    use_rag: bool = True


class SnippetResponse(BaseModel):
    source: str
    content: str


class GenerateResponse(BaseModel):
    output: str
    snippets: list[SnippetResponse] = []


@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    result = generate_vm_spec(request.spec, use_rag=request.use_rag)
    return GenerateResponse(
        output=result.output,
        snippets=[SnippetResponse(source=s.source, content=s.content) for s in result.snippets],
    )
