from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import observability with error handling
try:
    from .obs.otel import setup_tracing
    from .obs.logging_setup import setup_logging
    from .obs.middleware import MetricsMiddleware
    OBSERVABILITY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Observability not available: {e}")
    OBSERVABILITY_AVAILABLE = False

# Import routers
from .routers import health, ingest, query
try:
    from .routers import metrics
    METRICS_AVAILABLE = True
except ImportError:
    print("⚠️  Metrics router not available")
    METRICS_AVAILABLE = False

# Initialize observability if available
if OBSERVABILITY_AVAILABLE:
    setup_tracing()
    setup_logging(
        structured=os.getenv("LOG_STRUCTURED", "true").lower() == "true"
    )

# Create FastAPI app
app = FastAPI(
    title="RAG Microservice", 
    version="0.3.0",
    description="RAG pipeline with observability, async jobs, SSE streaming, and multiple retrieval strategies"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics middleware if available
if OBSERVABILITY_AVAILABLE:
    try:
        app.add_middleware(MetricsMiddleware)
        print("📊 Metrics middleware enabled")
    except Exception as e:
        print(f"⚠️  Metrics middleware error: {e}")

# Auto-instrument FastAPI if available
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/health,/metrics,/metrics/health"
    )
    print("🔍 FastAPI auto-instrumentation enabled")
except ImportError:
    print("⚠️  FastAPI instrumentation not available")
except Exception as e:
    print(f"⚠️  FastAPI instrumentation error: {e}")

# Include routers
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)

if METRICS_AVAILABLE:
    app.include_router(metrics.router)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "RAG Microservice v0.3", 
        "version": "0.3.0",
        "features": [
            "Async document ingestion with job tracking",
            "Server-Sent Events (SSE) streaming", 
            "Multiple retrieval strategies: dense, BM25, hybrid, rerank",
            "OpenTelemetry distributed tracing" if OBSERVABILITY_AVAILABLE else "Basic logging",
            "Comprehensive metrics collection" if OBSERVABILITY_AVAILABLE else "Basic metrics"
        ],
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "ingest": "/ingest",
            "query": "/query", 
            "stream_query": "/query/stream"
        }
    }

@app.on_event("startup")
async def startup_event():
    """Application startup."""
    print("🚀 RAG Microservice v0.3 starting up...")
    print("📊 Features: Jobs, SSE, Multiple Retrievers")
    if OBSERVABILITY_AVAILABLE:
        print("🔍 Observability: Enabled")
    else:
        print("⚠️  Observability: Disabled (missing dependencies)")

@app.on_event("shutdown") 
async def shutdown_event():
    """Application shutdown."""
    print("🛑 RAG Microservice v0.3 shutting down...")
    
    if OBSERVABILITY_AVAILABLE:
        try:
            from opentelemetry import trace
            tracer_provider = trace.get_tracer_provider()
            if hasattr(tracer_provider, 'shutdown'):
                tracer_provider.shutdown()
        except Exception as e:
            print(f"⚠️  Error during telemetry shutdown: {e}")