from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os
from app.models.schemas import IngestRequest, IngestResponse, JobStatusResponse
from app.services.ingest_service import start_ingest_job
from app.services.redis_job_manager import redis_job_registry
from app.obs.decorators import traced
from app.obs.logging_setup import get_logger
from app.utils.robust_sse import robust_sse_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

# 🔐 CONFIGURACIÓN DE TOKENS PARA PRUEBAS
HARDCODED_SSE_TOKENS = {
    "dev-token-123": "development",
    "test-token-456": "testing", 
    "demo-token-789": "demo",
    "admin-super-secret": "admin"
}

# Token por defecto para desarrollo rápido
DEFAULT_DEV_TOKEN = "dev-token-123"

# Configuración desde variables de entorno
SSE_AUTH_ENABLED = os.getenv("SSE_AUTH_ENABLED", "true").lower() == "true"
SSE_ALLOW_NO_TOKEN = os.getenv("SSE_ALLOW_NO_TOKEN", "false").lower() == "true"

security = HTTPBearer(auto_error=False)  

async def verify_sse_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Verificar token SSE para desarrollo y pruebas.
    
    Tokens válidos hardcodeados:
    - dev-token-123 (desarrollo)
    - test-token-456 (testing)
    - demo-token-789 (demo)
    - admin-super-secret (admin)
    
    Variables de entorno:
    - SSE_AUTH_ENABLED=true/false (habilitar/deshabilitar auth)
    - SSE_ALLOW_NO_TOKEN=true/false (permitir acceso sin token)
    """
    
    if not SSE_AUTH_ENABLED:
        logger.info("SSE auth disabled, allowing access")
        return "auth_disabled"
    
    if not credentials:
        if SSE_ALLOW_NO_TOKEN:
            logger.info("No SSE token provided, but no-token access is allowed")
            return "no_token_allowed"
        else:
            logger.warning("SSE token required but not provided")
            raise HTTPException(
                status_code=401, 
                detail={
                    "error": "SSE token required",
                    "hint": f"Use: curl -H 'Authorization: Bearer {DEFAULT_DEV_TOKEN}' ...",
                    "valid_tokens": list(HARDCODED_SSE_TOKENS.keys())
                }
            )
    
    token = credentials.credentials
    

    if token in HARDCODED_SSE_TOKENS:
        token_type = HARDCODED_SSE_TOKENS[token]
        logger.info(f"Valid SSE token used", token_type=token_type)
        return token
    
    # Token inválido
    logger.warning(f"Invalid SSE token attempted", token_preview=token[:10] + "...")
    raise HTTPException(
        status_code=401,
        detail={
            "error": "Invalid SSE token",
            "hint": f"Try using: {DEFAULT_DEV_TOKEN}",
            "valid_tokens": list(HARDCODED_SSE_TOKENS.keys())
        }
    )


@traced("ingest_endpoint")
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
    token: str = Depends(verify_sse_token),  # 🔐 Token verificado aquí
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):
    """
    Stream job progress with reconnection support.
    
    Requiere token de autenticación. Tokens válidos para pruebas:
    - dev-token-123 (desarrollo)
    - test-token-456 (testing)  
    - demo-token-789 (demo)
    - admin-super-secret (admin)
    
    Ejemplo de uso:
    curl -N -H "Authorization: Bearer dev-token-123" \\
         http://localhost:8000/ingest/{job_id}/stream
    """
    
    logger.info(f"SSE stream requested", 
               job_id=job_id, 
               client_id=client_id,
               token_used=token != "auth_disabled")
    
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
            yield {
                "type": "auth_success",
                "message": f"SSE stream authenticated with token: {token[:10]}...",
                "connection_id": connection.connection_id,
                "timestamp": asyncio.get_event_loop().time()
            }
            
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
            "X-Supports-Reconnection": "true",
            "X-Auth-Method": "hardcoded-token"
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

@router.get("/auth/tokens")
async def list_valid_tokens():
    """List valid SSE tokens for development (remove in production!)."""
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "valid_tokens": HARDCODED_SSE_TOKENS,
        "default_token": DEFAULT_DEV_TOKEN,
        "auth_enabled": SSE_AUTH_ENABLED,
        "allow_no_token": SSE_ALLOW_NO_TOKEN,
        "usage_examples": {
            "curl": f"curl -H 'Authorization: Bearer {DEFAULT_DEV_TOKEN}' http://localhost:8000/ingest/{{job_id}}/stream",
            "javascript": """
const eventSource = new EventSource('/ingest/job123/stream', {
    headers: {
        'Authorization': 'Bearer dev-token-123'
    }
});
            """.strip(),
            "python": f"""
import httpx

headers = {{"Authorization": "Bearer {DEFAULT_DEV_TOKEN}"}}
with httpx.stream("GET", "http://localhost:8000/ingest/job123/stream", headers=headers) as r:
    for line in r.iter_lines():
        print(line)
            """.strip()
        }
    }