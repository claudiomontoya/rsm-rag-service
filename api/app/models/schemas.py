from __future__ import annotations
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    content: str = Field(..., description="Document content or URL")
    document_type: Literal["text", "html", "markdown"] = "text"

class IngestResponse(BaseModel):
    status: Literal["success", "error"]
    message: str
    job_id: str
    chunks_created: int = 0

class QueryRequest(BaseModel):
    question: str

class Source(BaseModel):
    page: Optional[int] = None
    text: str
    score: Optional[float] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    retriever_used: str
    metadata: Optional[Dict[str, Any]] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "success", "error"]
    stage: str
    progress: float
    message: Optional[str] = None
    chunks_created: int
    created_at: float
    updated_at: float

class StreamEvent(BaseModel):
    type: str
    job_id: Optional[str] = None
    data: Dict[str, Any] = {}
    timestamp: float
    
class QueryStreamEvent(BaseModel):
    type: Literal["search_start", "search_results", "generation_start", "generation_chunk", "generation_complete"]
    data: Dict[str, Any]
    timestamp: float