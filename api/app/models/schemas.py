from __future__ import annotations
from typing import List, Literal
from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    content: str = Field(..., description="Document content or URL")
    document_type: Literal["text", "html", "markdown"] = "text"

class IngestResponse(BaseModel):
    status: Literal["success", "error"]
    message: str
    chunks_created: int

class QueryRequest(BaseModel):
    question: str

class Source(BaseModel):
    page: int | None = None
    text: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]