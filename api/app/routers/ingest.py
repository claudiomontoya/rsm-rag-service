from __future__ import annotations
import httpx
from fastapi import APIRouter, HTTPException
from app.models.schemas import IngestRequest, IngestResponse
from app.utils.split import strip_html, strip_markdown, simple_word_split
from app.deps.embeddings import embed_texts, embedding_dimension
from app.store.qdrant_store import ensure_collection, add_documents

router = APIRouter(prefix="/ingest", tags=["ingest"])

async def _fetch_content(content: str, document_type: str) -> str:
    """Fetch and clean content based on type."""
    
    if content.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as client:
            response = await client.get(content)
            response.raise_for_status()
            raw_content = response.text
    else:
        raw_content = content
    
    if document_type == "html":
        return strip_html(raw_content)
    elif document_type == "markdown":
        return strip_markdown(raw_content)
    else:
        return raw_content

@router.post("", response_model=IngestResponse)
async def ingest_document(request: IngestRequest) -> IngestResponse:
    """Ingest a document into the vector store."""
    try:
        cleaned_content = await _fetch_content(request.content, request.document_type)
        chunks = simple_word_split(cleaned_content)
        if not chunks or not chunks[0].strip():
            return IngestResponse(
                status="error",
                message="No content to ingest",
                chunks_created=0
            )
        embeddings = embed_texts(chunks)
        ensure_collection(embedding_dimension())        
        chunks_created = add_documents(chunks, embeddings)       
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {chunks_created} chunks",
            chunks_created=chunks_created
        )
        
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch content: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")