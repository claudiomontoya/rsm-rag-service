from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from .obs.otel import setup_tracing
from .obs.logging_setup import setup_logging
from .obs.middleware import MetricsMiddleware

from .routers import health, ingest, query, metrics

setup_tracing()
setup_logging(
    structured=os.getenv("LOG_STRUCTURED", "true").lower() == "true"
)

app = FastAPI(
    title="RAG Microservice", 
    version="0.3.0",
    description="RAG pipeline with advanced observability, async jobs, SSE streaming, and multiple retrieval strategies"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(MetricsMiddleware)

FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="/health,/metrics,/metrics/health"  
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(metrics.router)

@app.get("/")
async def root():
    """Root endpoint with comprehensive API information."""
    return {
        "message": "RAG Microservice v0.3", 
        "version": "0.3.0",
        "features": [
            "Async document ingestion with job tracking",
            "Server-Sent Events (SSE) streaming", 
            "Multiple retrieval strategies: dense, BM25, hybrid, rerank",
            "OpenTelemetry distributed tracing",
            "Langfuse LLM observability",
            "Structured logging with correlation",
            "Comprehensive metrics collection"
        ],
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "ingest": "/ingest",
            "query": "/query", 
            "stream_query": "/query/stream",
            "metrics": "/metrics",
            "metrics_health": "/metrics/health"
        },
        "observability": {
            "tracing": "OpenTelemetry → Jaeger",
            "metrics": "JSON endpoint + Prometheus-ready",
            "logging": "Structured JSON with trace correlation",
            "llm_tracking": "Langfuse integration"
        }
    }

@app.on_event("startup")
async def startup_event():
    """Application startup with observability initialization."""
    from .obs.logging_setup import get_logger
    
    logger = get_logger("startup")
    logger.info("🚀 RAG Microservice v0.3 starting up...")
    logger.info("📊 Features: Observability, Jobs, SSE, Multiple Retrievers")
    logger.info("🔍 Tracing: OpenTelemetry → Jaeger")
    logger.info("📈 Metrics: JSON + system metrics")
    logger.info("📝 Logging: Structured with trace correlation")

@app.on_event("shutdown") 
async def shutdown_event():
    """Application shutdown with cleanup."""
    from .obs.logging_setup import get_logger
    
    logger = get_logger("shutdown")
    logger.info("🛑 RAG Microservice v0.3 shutting down...")
    
    # Flush any remaining telemetry
    try:
        from opentelemetry import trace
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, 'shutdown'):
            tracer_provider.shutdown()
    except Exception as e:
        logger.error(f"Error during telemetry shutdown: {e}")