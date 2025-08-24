from __future__ import annotations
import time
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response
from app.obs.prometheus_metrics import prometheus_metrics
from app.services.redis_job_manager import redis_job_registry
from app.store.qdrant_store import client as qdrant_client
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """
    Kubernetes-style readiness probe.
    Checks if service is ready to receive traffic.
    """
    checks = {}
    overall_healthy = True
    start_time = time.time()
    
    try:
        # Check Redis connection
        try:
            redis_health = await redis_job_registry.health_check()
            checks["redis"] = redis_health
            if redis_health["status"] != "healthy":
                overall_healthy = False
        except Exception as e:
            checks["redis"] = {"status": "unhealthy", "error": str(e)}
            overall_healthy = False
        
        # Check Qdrant connection
        try:
            qdrant_start = time.time()
            collections = qdrant_client().get_collections()
            qdrant_time = (time.time() - qdrant_start) * 1000
            
            checks["qdrant"] = {
                "status": "healthy",
                "collections_count": len(collections.collections),
                "response_time_ms": round(qdrant_time, 2)
            }
        except Exception as e:
            checks["qdrant"] = {"status": "unhealthy", "error": str(e)}
            overall_healthy = False
        
        # Check system resources
        try:
            import psutil
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Consider unhealthy if memory > 90% or disk > 95%
            memory_healthy = memory.percent < 90
            disk_healthy = disk.percent < 95
            
            checks["system"] = {
                "status": "healthy" if (memory_healthy and disk_healthy) else "degraded",
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "memory_healthy": memory_healthy,
                "disk_healthy": disk_healthy
            }
            
            if not (memory_healthy and disk_healthy):
                overall_healthy = False
                
        except Exception as e:
            checks["system"] = {"status": "unhealthy", "error": str(e)}
            overall_healthy = False
        
        total_time = (time.time() - start_time) * 1000
        
        response_data = {
            "status": "ready" if overall_healthy else "not_ready",
            "timestamp": time.time(),
            "checks": checks,
            "response_time_ms": round(total_time, 2)
        }
        
        status_code = 200 if overall_healthy else 503
        
        if not overall_healthy:
            logger.warning("Readiness check failed", checks=checks)
        
        return JSONResponse(response_data, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Readiness check error: {e}", exc_info=True)
        return JSONResponse({
            "status": "not_ready",
            "error": str(e),
            "timestamp": time.time()
        }, status_code=503)

@router.get("/live")
async def liveness_check() -> JSONResponse:
    """
    Kubernetes-style liveness probe.
    Simple check that service is running.
    """
    return JSONResponse({
        "status": "alive",
        "timestamp": time.time(),
        "service": "rag-microservice",
        "version": "1.0.0"
    })

@router.get("/metrics/prometheus")
async def prometheus_metrics_endpoint():
    """Prometheus metrics endpoint."""
    try:
        # Update system metrics before serving
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_bytes = process.memory_info().rss
        cpu_percent = process.cpu_percent()
        
        prometheus_metrics.update_system_metrics(memory_bytes, cpu_percent)
        
        # Update active jobs count
        try:
            active_jobs = len(await redis_job_registry.list_active_jobs(limit=1000))
            prometheus_metrics.update_active_jobs(active_jobs)
        except Exception:
            pass  # Don't fail metrics if Redis is down
        
        metrics_data = prometheus_metrics.get_prometheus_metrics()
        content_type = prometheus_metrics.get_content_type()
        
        return Response(
            content=metrics_data,
            media_type=content_type
        )
        
    except Exception as e:
        logger.error(f"Prometheus metrics error: {e}")
        raise HTTPException(status_code=500, detail="Metrics collection failed")

@router.get("/metrics/health")
async def metrics_health_check() -> JSONResponse:
    """Health check for metrics system."""
    try:
        # Simple metrics availability check
        metrics_data = prometheus_metrics.get_prometheus_metrics()
        
        return JSONResponse({
            "status": "healthy",
            "metrics_size_bytes": len(metrics_data),
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Metrics health check failed: {e}")
        return JSONResponse({
            "status": "unhealthy", 
            "error": str(e)
        }, status_code=500)