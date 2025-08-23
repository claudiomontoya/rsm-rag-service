from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.models.schemas import QueryRequest, QueryResponse, Source
from app.deps.embeddings import embed_texts
from app.store.qdrant_store import search_similar

router = APIRouter(prefix="/query", tags=["query"])

def _generate_answer(question: str, sources: list) -> str:
    """Generate a simple answer based on sources (dummy implementation)."""
    if not sources:
        return "No relevant information found."
    context = " ".join([source["text"][:200] for source in sources[:3]])
    return f"Based on the available information: {context[:400]}..."

@router.post("", response_model=QueryResponse)
async def query_documents(request: QueryRequest) -> QueryResponse:
    """Query documents using dense retrieval."""
    try:
        query_embeddings = embed_texts([request.question])
        query_vector = query_embeddings[0]
        similar_docs = search_similar(query_vector, limit=5)
        sources = [
            Source(page=doc.get("page"), text=doc["text"])
            for doc in similar_docs
        ]
        answer = _generate_answer(request.question, similar_docs)
        return QueryResponse(answer=answer, sources=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")