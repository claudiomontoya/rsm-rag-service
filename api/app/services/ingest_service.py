from __future__ import annotations
import asyncio
import uuid
from typing import List
import httpx
from app.utils.semantic_chunking import semantic_chunker
from app.utils.retry_backoff import retry_with_backoff, DEFAULT_HTTP_RETRY
from app.deps.embeddings import embed_texts, embedding_dimension
from app.store.qdrant_store import ensure_collection, add_documents
from app.store.memory_bm25 import bm25_index
from app.services.redis_job_manager import redis_job_registry, JobStatus
from app.obs.decorators import traced, timed
from app.obs.langfuse import trace_with_langfuse
from app.obs.logging_setup import get_logger
from app.obs.prometheus_metrics import prometheus_metrics

logger = get_logger(__name__)

@retry_with_backoff(
    config=DEFAULT_HTTP_RETRY, 
    operation_name="fetch_content"
)
@traced(operation_name="fetch_content", include_args=True)
async def _fetch_content(content: str, document_type: str) -> str:
    """Fetch and clean content with retry logic."""
    try:
        if content.startswith(("http://", "https://")):
            logger.info(f"Fetching content from URL", url=content)
            
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10)
            ) as client:
                response = await client.get(content)
                response.raise_for_status()
                raw_content = response.text
                
            logger.info(f"Successfully fetched content", 
                       url=content, 
                       content_length=len(raw_content),
                       status_code=response.status_code)
        else:
            raw_content = content
            logger.info(f"Using provided content", content_length=len(raw_content))
        
        return raw_content
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching content", 
                    url=content if content.startswith(("http://", "https://")) else "inline",
                    error=str(e))
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching content", 
                    content_preview=content[:100],
                    error=str(e))
        raise Exception(f"Failed to fetch content: {str(e)}")

@traced(operation_name="ingest_job", langfuse_trace=True)
@timed("ingest_job_duration_seconds")
async def run_ingest_job(job_id: str, content: str, document_type: str) -> None:
    """Run the ingestion job with semantic chunking and retries."""
    
    job_start_time = asyncio.get_event_loop().time()
    
    logger.info(f"Starting ingest job", 
               job_id=job_id, 
               document_type=document_type,
               content_preview=content[:100])
    
    with trace_with_langfuse("document_ingestion", {
        "job_id": job_id,
        "document_type": document_type,
        "content_length": len(content)
    }) as lf_ctx:
        
        try:
            # Step 1: Fetch and clean content
            await redis_job_registry.update_job(
                job_id, 
                status=JobStatus.RUNNING,
                stage="fetching",
                progress=10.0,
                message="Fetching and cleaning content..."
            )
            
            cleaned_content = await _fetch_content(content, document_type)
            
            if not cleaned_content.strip():
                await redis_job_registry.update_job(
                    job_id,
                    status=JobStatus.ERROR,
                    message="No content after cleaning"
                )
                prometheus_metrics.record_ingest_job("failed", document_type, 0)
                return
            
            # Step 2: Semantic chunking
            await redis_job_registry.update_job(
                job_id,
                stage="chunking",
                progress=20.0,
                message="Creating semantic chunks..."
            )
            
            semantic_chunks = semantic_chunker.chunk_text(cleaned_content, document_type)
            
            if not semantic_chunks:
                await redis_job_registry.update_job(
                    job_id,
                    status=JobStatus.ERROR,
                    message="No chunks created from content"
                )
                prometheus_metrics.record_ingest_job("failed", document_type, 0)
                return
            
            logger.info(f"Semantic chunking completed", 
                       job_id=job_id, 
                       chunks_count=len(semantic_chunks))
            
            # Step 3: Generate embeddings
            await redis_job_registry.update_job(
                job_id,
                stage="embedding",
                progress=40.0,
                message=f"Creating embeddings for {len(semantic_chunks)} chunks..."
            )
            
            # Extract text from semantic chunks
            chunk_texts = [chunk.text for chunk in semantic_chunks]
            
            with trace_with_langfuse("embedding_generation", {
                "chunks_count": len(chunk_texts),
                "embedding_model": "configured_model"
            }):
                embeddings = embed_texts(chunk_texts)
            
            prometheus_metrics.record_embeddings(len(embeddings))
            
            logger.info(f"Embeddings generated", 
                       job_id=job_id,
                       embeddings_count=len(embeddings))
            
            # Step 4: Store in vector database
            await redis_job_registry.update_job(
                job_id,
                stage="storing",
                progress=70.0,
                message="Storing in vector database..."
            )
            
            ensure_collection(embedding_dimension())
            chunks_created = add_documents(chunk_texts, embeddings)
            
            logger.info(f"Documents stored in vector DB", 
                       job_id=job_id,
                       chunks_stored=chunks_created)
            
            # Step 5: Build BM25 index
            await redis_job_registry.update_job(
                job_id,
                stage="indexing",
                progress=85.0,
                message="Building BM25 index..."
            )
            
            # Create metadata from semantic chunks
            metadata = []
            for i, chunk in enumerate(semantic_chunks):
                metadata.append({
                    "page": chunk.page or (i + 1),
                    "doc_id": str(uuid.uuid4()),
                    "title": chunk.title,
                    "section": chunk.section,
                    "chunk_index": chunk.chunk_index,
                    "word_count": chunk.word_count,
                    "has_title_context": chunk.metadata.get("has_title_context", False)
                })
            
            bm25_index.add_documents(chunk_texts, metadata)
            
            logger.info(f"BM25 index updated", 
                       job_id=job_id,
                       documents_indexed=len(chunk_texts))
            
            # Step 6: Complete
            job_duration = asyncio.get_event_loop().time() - job_start_time
            
            await redis_job_registry.update_job(
                job_id,
                status=JobStatus.SUCCESS,
                stage="completed",
                progress=100.0,
                message=f"Successfully ingested {chunks_created} semantic chunks",
                chunks_created=chunks_created
            )
            
            # Record metrics
            prometheus_metrics.record_ingest_job("success", document_type, job_duration)
            
            logger.info(f"Ingest job completed successfully", 
                       job_id=job_id,
                       chunks_created=chunks_created,
                       duration_seconds=round(job_duration, 2))
            
            # Log to Langfuse
            if lf_ctx and lf_ctx.get("trace"):
                lf_ctx["trace"].update(output={
                    "status": "success",
                    "chunks_created": chunks_created,
                    "semantic_chunks": len(semantic_chunks),
                    "duration_seconds": job_duration
                })
            
        except Exception as e:
            job_duration = asyncio.get_event_loop().time() - job_start_time
            
            logger.error(f"Ingest job failed", 
                        job_id=job_id,
                        error=str(e),
                        duration_seconds=round(job_duration, 2),
                        exc_info=True)
            
            await redis_job_registry.update_job(
                job_id,
                status=JobStatus.ERROR,
                stage="error",
                message=f"Ingestion failed: {str(e)}"
            )
            
            # Record error metrics
            prometheus_metrics.record_ingest_job("failed", document_type, job_duration)
            
            # Log to Langfuse
            if lf_ctx and lf_ctx.get("trace"):
                lf_ctx["trace"].update(output={
                    "status": "error",
                    "error": str(e),
                    "duration_seconds": job_duration
                })

# CAMBIAR start_ingest_job para que retorne job_id:
# app/services/ingest_service.py
@traced(operation_name="start_ingest_job")
async def start_ingest_job(content: str, document_type: str) -> str:
    job = await redis_job_registry.create_job(timeout_seconds=600, max_retries=2)
    logger.info("Created ingest job", job_id=job.job_id, document_type=document_type)
    asyncio.create_task(run_ingest_job(job.job_id, content, document_type))
    return job.job_id
