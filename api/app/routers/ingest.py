from __future__ import annotations
import asyncio
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal, Optional

from app.services.ingest_service import start_ingest_job
from app.services.redis_job_manager import redis_job_registry
from app.utils.sse_heartbeat import sse_heartbeat_manager
from app.obs.decorators import traced
from app.obs.logging_setup import get_logger
from app.utils.robust_sse import robust_sse_manager
from fastapi import Header
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()
logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

# Schemas definidos directamente aquí para evitar imports circulares
class IngestRequest(BaseModel):
    content: str
    document_type: Literal["text", "html", "markdown"] = "text"

class IngestResponse(BaseModel):
    status: Literal["success", "error"]
    message: str
    job_id: str
    chunks_created: int = 0

class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "success", "error"]
    stage: str
    progress: float
    message: Optional[str] = None
    chunks_created: int
    created_at: float
    updated_at: float


async def verify_sse_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify SSE access token."""
    token = credentials.credentials
    
    if not token or len(token) < 10:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing SSE token"
        )
    return token


@traced("ingest_endpoint")
@router.post("", response_model=IngestResponse)
async def ingest_document(request: IngestRequest) -> IngestResponse:
    try:
        job_id = await start_ingest_job(request.content, request.document_type)
        return IngestResponse(
            status="success",
            message="Ingestion job started",
            job_id=job_id,
            chunks_created=0
        )
    except Exception as e:
        logger.error("Failed to start ingestion", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion: {str(e)}")


@traced("job_status_endpoint")
@router.get("/{job_id}/status", response_model=JobStatusResponse)
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

@traced("job_stream_endpoint")
@router.get("/{job_id}/stream")
async def stream_job_progress(
    job_id: str, 
    request: Request,
    token: str = Depends(verify_sse_token),
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):
    """Stream job progress with reconnection support."""
    
    # Verify job exists
    job = await redis_job_registry.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Create robust SSE connection
    connection = robust_sse_manager.create_connection(
        job_id=job_id,
        client_id=client_id,
        last_event_id=last_event_id
    )
    
    async def event_generator():
        """Generate events from Redis pub/sub."""
        try:
            # Send current job state first
            current_job = await redis_job_registry.get_job(job_id)
            if current_job:
                yield {
                    "type": "job_status",
                    "job_id": current_job.job_id,
                    "status": current_job.status.value,
                    "stage": current_job.stage,
                    "progress": current_job.progress,
                    "message": current_job.message,
                    "chunks_created": current_job.chunks_created
                }
            
            # Subscribe to job events
            async for event in redis_job_registry.subscribe_to_job_events(job_id):
                yield event
                
                # Stop on completion
                if event.get("type") == "job_updated" and \
                   event.get("status") in ["success", "error", "cancelled"]:
                    break
                    
        except Exception as e:
            logger.error(f"Event generator error", job_id=job_id, error=str(e))
            yield {
                "type": "stream_error",
                "message": f"Stream error: {str(e)}"
            }
    
    # Stream with reconnection support
    event_stream = robust_sse_manager.stream_with_reconnection(
        connection=connection,
        event_source=event_generator(),
        request=request
    )
    
    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Connection-ID": connection.connection_id,
            "X-Client-ID": connection.client_id,
            "X-Supports-Reconnection": "true"
        }
    )

@traced("list_active_jobs")
@router.get("/jobs/active")
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