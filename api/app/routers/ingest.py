from __future__ import annotations
import asyncio
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import IngestRequest, IngestResponse, JobStatusResponse
from app.services.ingest_service import start_ingest_job
from app.services.redis_job_manager import redis_job_registry
from app.utils.sse_heartbeat import sse_heartbeat_manager
from app.obs.decorators import traced
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("", response_model=IngestResponse)
@traced("ingest_endpoint")
async def ingest_document(request: IngestRequest) -> IngestResponse:
    """Start document ingestion job."""
    try:
        job = await redis_job_registry.create_job()
        
        # Start the job in background
        asyncio.create_task(start_ingest_job(job.job_id, request.content, request.document_type))
        
        return IngestResponse(
            status="success",
            message="Ingestion job started",
            job_id=job.job_id,
            chunks_created=0
        )
        
    except Exception as e:
        logger.error(f"Failed to start ingestion", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion: {str(e)}")

@router.get("/{job_id}/status", response_model=JobStatusResponse)
@traced("job_status_endpoint")
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get job status."""
    job = await redis_job_registry.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        chunks_created=job.chunks_created,
        created_at=job.created_at,
        updated_at=job.updated_at
    )

@router.get("/{job_id}/stream")
@traced("job_stream_endpoint")
async def stream_job_progress(job_id: str, request: Request):
    """Stream job progress via Server-Sent Events with heartbeats."""
    
    # Verify job exists
    job = await redis_job_registry.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    connection_id = f"ingest_{job_id}_{uuid.uuid4().hex[:8]}"
    
    async def event_generator():
        """Generate SSE events for job progress."""
        try:
            # Send initial job state
            initial_event = sse_heartbeat_manager.create_sse_event(
                event_type="job_status",
                data={
                    "type": "job_status",
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "stage": job.stage,
                    "progress": job.progress,
                    "message": job.message,
                    "chunks_created": job.chunks_created
                }
            )
            yield initial_event
            
            # Subscribe to Redis events
            last_heartbeat = 0
            async for event in redis_job_registry.subscribe_to_job_events(job_id):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from job stream", job_id=job_id)
                    break
                
                # Send event
                sse_event = sse_heartbeat_manager.create_sse_event(
                    event_type="job_update",
                    data=event
                )
                yield sse_event
                
                # Send heartbeat if needed
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > sse_heartbeat_manager.heartbeat_interval:
                    heartbeat = sse_heartbeat_manager.create_heartbeat(connection_id)
                    yield heartbeat
                    last_heartbeat = current_time
                
                # Break on job completion
                if event.get("type") == "job_updated" and event.get("status") in ["success", "error", "cancelled"]:
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"Job stream cancelled", job_id=job_id)
        except Exception as e:
            logger.error(f"Job stream error", job_id=job_id, error=str(e))
            error_event = sse_heartbeat_manager.create_sse_event(
                event_type="error",
                data={
                    "type": "stream_error",
                    "message": f"Stream error: {str(e)}"
                }
            )
            yield error_event
    
    # Wrap with heartbeat manager
    wrapped_generator = sse_heartbeat_manager.heartbeat_stream(
        connection_id=connection_id,
        event_source=event_generator(),
        client_disconnect_check=lambda: asyncio.create_task(request.is_disconnected())
    )
    
    return StreamingResponse(
        wrapped_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Connection-ID": connection_id
        }
    )

@router.get("/jobs/active")
@traced("list_active_jobs")
async def list_active_jobs(limit: int = 50):
    """List active jobs."""
    try:
        jobs = await redis_job_registry.list_active_jobs(limit=limit)
        return {
            "jobs": [
                {
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "stage": job.stage,
                    "progress": job.progress,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at
                }
                for job in jobs
            ],
            "total": len(jobs)
        }
    except Exception as e:
        logger.error(f"Failed to list jobs", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))