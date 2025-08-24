from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.obs.metrics import metrics_registry
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["metrics"])

@router.get("/metrics")
async def get_metrics() -> JSONResponse:
    """Get application metrics in JSON format."""
    try:
        metrics_data = metrics_registry.get_metrics()
        
        # Add some additional system info
        import psutil
        import os
        
        system_metrics = {
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "process_memory_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            }
        }
        
        # Combine application and system metrics
        response_data = {
            **metrics_data,
            **system_metrics
        }
        
        logger.info("Metrics endpoint accessed")
        return JSONResponse(response_data)
        
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
        return JSONResponse(
            {"error": "Failed to collect metrics", "detail": str(e)}, 
            status_code=500
        )

@router.get("/metrics/health")
async def metrics_health() -> JSONResponse:
    """Lightweight health check for metrics system."""
    try:
        # Basic metrics system health check
        metrics_count = len(metrics_registry.get_metrics().get("counters", {}))
        
        return JSONResponse({
            "status": "healthy",
            "metrics_collected": metrics_count,
            "timestamp": metrics_registry.get_metrics()["timestamp"]
        })
        
    except Exception as e:
        logger.error(f"Metrics health check failed: {e}")
        return JSONResponse(
            {"status": "unhealthy", "error": str(e)},
            status_code=500
        )