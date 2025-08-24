from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import IngestRequest, IngestResponse, JobStatusResponse
from app.services.ingest_service import start_ingest_job
from app.services.job_manager import job_registry
from app.utils.sse import create_sse_message, create_sse_heartbeat, create_sse_close

router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("", response_model=IngestResponse)
async def ingest_document(request: IngestRequest) -> IngestResponse:
    """Start document ingestion job."""
    try:
        job_id = await start_ingest_job(request.content, request.document_type)
        
        return IngestResponse(
            status="success",
            message="Ingestion job started",
            job_id=job_id,
            chunks_created=0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion: {str(e)}")

@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get job status."""
    job = job_registry.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,  # ← ARREGLADO: convertir Enum a string
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        chunks_created=job.chunks_created,
        created_at=job.created_at,
        updated_at=job.updated_at
    )

@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """Stream job progress via Server-Sent Events."""
    job = job_registry.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    event_queue = job_registry.get_event_stream(job_id)
    if not event_queue:
        raise HTTPException(status_code=404, detail="Event stream not found")
    
    async def event_generator():
        """Generate SSE events."""
        try:
            # Send initial job state
            initial_event = {
                "type": "job_status",
                "job_id": job.job_id,
                "status": job.status.value,  # ← ARREGLADO aquí también
                "stage": job.stage,
                "progress": job.progress,
                "message": job.message,
                "chunks_created": job.chunks_created
            }
            yield create_sse_message(initial_event)
            
            # Stream events until job is complete
            while True:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    yield create_sse_message(event)
                    
                    # Check if job is finished
                    if event.get("type") == "job_updated" and event.get("status") in ["success", "error"]:
                        break
                        
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield create_sse_heartbeat()
                    continue
                    
        except Exception as e:
            error_event = {
                "type": "error",
                "message": f"Stream error: {str(e)}"
            }
            yield create_sse_message(error_event)
        finally:
            yield create_sse_close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )