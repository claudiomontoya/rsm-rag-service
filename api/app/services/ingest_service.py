from __future__ import annotations
import asyncio
import uuid
from typing import List
import httpx
from app.utils.split import strip_html, strip_markdown, simple_word_split
from app.deps.embeddings import embed_texts, embedding_dimension
from app.store.qdrant_store import ensure_collection, add_documents
from app.store.memory_bm25 import bm25_index
from app.services.job_manager import job_registry, JobStatus

async def _fetch_content(content: str, document_type: str) -> str:
    """Fetch and clean content based on type."""
    try:
        # If it's a URL, fetch it
        if content.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(content)
                response.raise_for_status()
                raw_content = response.text
        else:
            raw_content = content
        
        # Clean based on document type
        if document_type == "html":
            return strip_html(raw_content)
        elif document_type == "markdown":
            return strip_markdown(raw_content)
        else:
            return raw_content
    except Exception as e:
        raise Exception(f"Failed to fetch content: {str(e)}")

async def run_ingest_job(job_id: str, content: str, document_type: str) -> None:
    """Run the ingestion job asynchronously."""
    try:
        await job_registry.update_job(
            job_id, 
            status=JobStatus.RUNNING,
            stage="fetching",
            progress=10.0,
            message="Fetching content..."
        )
        
        # Fetch and clean content
        cleaned_content = await _fetch_content(content, document_type)
        
        if not cleaned_content.strip():
            await job_registry.update_job(
                job_id,
                status=JobStatus.ERROR,
                message="No content to process"
            )
            return
        
        await job_registry.update_job(
            job_id,
            stage="splitting",
            progress=20.0,
            message="Splitting into chunks..."
        )
        
        # Split into chunks
        chunks = simple_word_split(cleaned_content)
        
        if not chunks:
            await job_registry.update_job(
                job_id,
                status=JobStatus.ERROR,
                message="No chunks created"
            )
            return
        
        await job_registry.update_job(
            job_id,
            stage="embedding",
            progress=40.0,
            message=f"Creating embeddings for {len(chunks)} chunks..."
        )
        
        # Generate embeddings
        embeddings = embed_texts(chunks)
        
        await job_registry.update_job(
            job_id,
            stage="storing",
            progress=70.0,
            message="Storing in vector database..."
        )
        
        # Ensure collection exists
        ensure_collection(embedding_dimension())
        
        # Add to vector store
        chunks_created = add_documents(chunks, embeddings)
        
        await job_registry.update_job(
            job_id,
            stage="indexing",
            progress=85.0,
            message="Building BM25 index..."
        )
        
        # Add to BM25 index
        metadata = [{"page": i+1, "doc_id": str(uuid.uuid4())} for i in range(len(chunks))]
        bm25_index.add_documents(chunks, metadata)
        
        await job_registry.update_job(
            job_id,
            status=JobStatus.SUCCESS,
            stage="completed",
            progress=100.0,
            message=f"Successfully ingested {chunks_created} chunks",
            chunks_created=chunks_created
        )
        
    except Exception as e:
        await job_registry.update_job(
            job_id,
            status=JobStatus.ERROR,
            stage="error",
            message=f"Ingestion failed: {str(e)}"
        )

async def start_ingest_job(content: str, document_type: str) -> str:
    """Start an async ingestion job and return job_id."""
    job = await job_registry.create_job()
    
    # Start the job in background
    asyncio.create_task(run_ingest_job(job.job_id, content, document_type))
    
    return job.job_id