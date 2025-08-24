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
from app.obs.decorators import traced, timed
from app.obs.langfuse import trace_with_langfuse, log_retrieval
from app.obs.logging_setup import get_logger
from app.obs.metrics import inc_counter, record_duration

logger = get_logger(__name__)

@traced(operation_name="fetch_content", include_args=True)
async def _fetch_content(content: str, document_type: str) -> str:
    """Fetch and clean content based on type."""
    try:
        if content.startswith(("http://", "https://")):
            logger.info(f"Fetching content from URL", url=content)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(content)
                response.raise_for_status()
                raw_content = response.text
                
            logger.info(f"Successfully fetched content", 
                       url=content, 
                       content_length=len(raw_content))
        else:
            raw_content = content
            logger.info(f"Using provided content", content_length=len(raw_content))
        
        if document_type == "html":
            cleaned = strip_html(raw_content)
        elif document_type == "markdown":
            cleaned = strip_markdown(raw_content)
        else:
            cleaned = raw_content
        
        logger.info(f"Content cleaned", 
                   original_length=len(raw_content),
                   cleaned_length=len(cleaned),
                   document_type=document_type)
        
        return cleaned
        
    except Exception as e:
        logger.error(f"Failed to fetch/clean content", 
                    content_preview=content[:100],
                    document_type=document_type,
                    error=str(e))
        raise Exception(f"Failed to fetch content: {str(e)}")

@traced(operation_name="ingest_job", langfuse_trace=True)
@timed("ingest_job_duration_ms")
async def run_ingest_job(job_id: str, content: str, document_type: str) -> None:
    """Run the ingestion job asynchronously with full observability."""
    
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
            await job_registry.update_job(
                job_id, 
                status=JobStatus.RUNNING,
                stage="fetching",
                progress=10.0,
                message="Fetching and cleaning content..."
            )
            
            cleaned_content = await _fetch_content(content, document_type)
            
            if not cleaned_content.strip():
                logger.error("No content after cleaning", job_id=job_id)
                await job_registry.update_job(
                    job_id,
                    status=JobStatus.ERROR,
                    message="No content to process after cleaning"
                )
                inc_counter("ingest_jobs_failed", {"reason": "empty_content"})
                return
        
            await job_registry.update_job(
                job_id,
                stage="splitting",
                progress=20.0,
                message="Splitting content into chunks..."
            )
            
            chunks = simple_word_split(cleaned_content)
            
            if not chunks:
                logger.error("No chunks created", job_id=job_id)
                await job_registry.update_job(
                    job_id,
                    status=JobStatus.ERROR,
                    message="No chunks created from content"
                )
                inc_counter("ingest_jobs_failed", {"reason": "no_chunks"})
                return
            
            logger.info(f"Content split into chunks", 
                       job_id=job_id, 
                       chunks_count=len(chunks))
            await job_registry.update_job(
                job_id,
                stage="embedding",
                progress=40.0,
                message=f"Creating embeddings for {len(chunks)} chunks..."
            )
            
            with trace_with_langfuse("embedding_generation", {
                "chunks_count": len(chunks),
                "embedding_model": "configured_model"
            }):
                embeddings = embed_texts(chunks)
                
            logger.info(f"Embeddings generated", 
                       job_id=job_id,
                       embeddings_count=len(embeddings))
            await job_registry.update_job(
                job_id,
                stage="storing",
                progress=70.0,
                message="Storing in vector database..."
            )
            
            ensure_collection(embedding_dimension())
            chunks_created = add_documents(chunks, embeddings)
            
            logger.info(f"Documents stored in vector DB", 
                       job_id=job_id,
                       chunks_stored=chunks_created)
            await job_registry.update_job(
                job_id,
                stage="indexing",
                progress=85.0,
                message="Building BM25 keyword index..."
            )
            
            metadata = [{"page": i+1, "doc_id": str(uuid.uuid4())} for i in range(len(chunks))]
            bm25_index.add_documents(chunks, metadata)
            
            logger.info(f"BM25 index updated", 
                       job_id=job_id,
                       documents_indexed=len(chunks))
            await job_registry.update_job(
                job_id,
                status=JobStatus.SUCCESS,
                stage="completed",
                progress=100.0,
                message=f"Successfully ingested {chunks_created} chunks",
                chunks_created=chunks_created
            )
            inc_counter("ingest_jobs_completed")
            inc_counter("documents_ingested", value=chunks_created)
            
            logger.info(f"Ingest job completed successfully", 
                       job_id=job_id,
                       chunks_created=chunks_created)
            if lf_ctx and lf_ctx.get("trace"):
                lf_ctx["trace"].update(output={
                    "status": "success",
                    "chunks_created": chunks_created
                })
            
        except Exception as e:
            logger.error(f"Ingest job failed", 
                        job_id=job_id,
                        error=str(e),
                        exc_info=True)
            
            await job_registry.update_job(
                job_id,
                status=JobStatus.ERROR,
                stage="error",
                message=f"Ingestion failed: {str(e)}"
            )
            inc_counter("ingest_jobs_failed", {"reason": "exception"})
            if lf_ctx and lf_ctx.get("trace"):
                lf_ctx["trace"].update(output={
                    "status": "error",
                    "error": str(e)
                })

@traced(operation_name="start_ingest_job")
async def start_ingest_job(content: str, document_type: str) -> str:
    """Start an async ingestion job and return job_id."""
    job = await job_registry.create_job()
    
    logger.info(f"Created ingest job", 
               job_id=job.job_id,
               document_type=document_type)
    asyncio.create_task(run_ingest_job(job.job_id, content, document_type))
    inc_counter("ingest_jobs_created", {"document_type": document_type})
    
    return job.job_id