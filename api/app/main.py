from __future__ import annotations
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Import observability setup
from .obs.otel import setup_tracing
from .obs.logging_setup import setup_logging
from .obs.middleware import MetricsMiddleware
from .obs.prometheus_metrics import prometheus_metrics

# Import middleware
from .middleware.request_id import RequestIDMiddleware
from .middleware.security import SecurityMiddleware

# Import services
from .services.model_warmup import model_warmup_service

# Import routers
from .routers import health, ingest, query, readiness

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with startup and shutdown logic."""
    
    # Startup
    print("🚀 RAG Microservice v1.0 starting up...")
    
    # Initialize observability
    setup_tracing()
    setup_logging(
        structured=os.getenv("LOG_STRUCTURED", "true").lower() == "true"
    )
    
    # Warm up models
    print("🔥 Starting model warm-up...")
    warmup_results = await model_warmup_service.warmup_all_models()
    
    if warmup_results["overall_status"] == "success":
        print("✅ All models warmed up successfully")
    else:
        print("⚠️  Some models failed to warm up - check logs")
    
    print("🎯 RAG Microservice ready for requests")
    
    yield
    
    # Shutdown
    print("🛑 RAG Microservice shutting down...")
    
    # Graceful shutdown
    try:
        from opentelemetry import trace
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, 'shutdown'):
            tracer_provider.shutdown()
    except Exception as e:
        print(f"Error during telemetry shutdown: {e}")
    
    print("👋 Shutdown complete")

# Create FastAPI app with lifespan
app = FastAPI(
    title="RAG Microservice", 
    version="1.0.0",
    description="Production-ready RAG pipeline with Redis jobs, observability, and semantic search",
    lifespan=lifespan
)

# Security middleware (first)
app.add_middleware(
    SecurityMiddleware,
    rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
    rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
    max_request_size=int(os.getenv("MAX_REQUEST_SIZE", "10485760")),
    timeout_seconds=int(os.getenv("REQUEST_TIMEOUT", "30"))
)

# Trusted host middleware
if os.getenv("ALLOWED_HOSTS"):
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics middleware (before FastAPI instrumentation)
app.add_middleware(MetricsMiddleware)

# Auto-instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="/health,/ready,/live,/metrics/prometheus,/metrics/health"
)

# Include routers
app.include_router(health.router)
app.include_router(readiness.router)
app.include_router(ingest.router)
app.include_router(query.router)

@app.get("/")
async def root():
    """Root endpoint with comprehensive API information."""
    return {
        "service": "RAG Microservice",
        "version": "1.0.0",
        "status": "production",
        "features": [
            "Redis-backed job management",
            "Semantic chunking with title bubbling",
            "Multiple retrieval strategies with reranking",
            "OpenTelemetry distributed tracing",
            "Langfuse LLM observability",
            "Prometheus metrics + Grafana ready",
            "SSE streaming with heartbeats",
            "Request-ID correlation",
            "Security middleware",
            "Model warm-up on startup"
        ],
        "endpoints": {
            "health": "/health - Basic health check",
            "ready": "/ready - Kubernetes readiness probe", 
            "live": "/live - Kubernetes liveness probe",
            "ingest": "/ingest - Start document ingestion job",
            "ingest_status": "/ingest/{job_id}/status - Check job status",
            "ingest_stream": "/ingest/{job_id}/stream - Stream job progress",
            "query": "/query - Query documents",
            "query_stream": "/query/stream - Stream query results",
            "metrics": "/metrics - JSON metrics",
            "prometheus": "/metrics/prometheus - Prometheus metrics"
        },
        "observability": {
            "tracing": "OpenTelemetry → Jaeger (port 16686)",
            "metrics": "Prometheus format + JSON",
            "logging": "Structured JSON with trace correlation",
            "llm_tracking": "Langfuse integration"
        },
        "warmup_status": model_warmup_service.warmup_results.get("overall_status", "not_started")
    }