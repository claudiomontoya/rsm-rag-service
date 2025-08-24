from __future__ import annotations
import time
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

# Application metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

INGEST_JOBS_TOTAL = Counter(
    'ingest_jobs_total',
    'Total ingestion jobs',
    ['status', 'document_type']
)

INGEST_JOB_DURATION = Histogram(
    'ingest_job_duration_seconds',
    'Ingestion job duration in seconds',
    ['status']
)

QUERY_COUNT = Counter(
    'queries_total',
    'Total queries processed',
    ['retriever_type']
)

QUERY_DURATION = Histogram(
    'query_duration_seconds', 
    'Query processing duration in seconds',
    ['retriever_type']
)

DOCUMENTS_RETRIEVED = Histogram(
    'documents_retrieved',
    'Number of documents retrieved per query',
    ['retriever_type']
)

EMBEDDINGS_GENERATED = Counter(
    'embeddings_generated_total',
    'Total embeddings generated'
)

# System metrics
MEMORY_USAGE = Gauge(
    'process_memory_bytes',
    'Process memory usage in bytes'
)

CPU_USAGE = Gauge(
    'process_cpu_percent',
    'Process CPU usage percentage'
)

ACTIVE_JOBS = Gauge(
    'active_jobs',
    'Number of active background jobs'
)

REDIS_CONNECTION_POOL = Gauge(
    'redis_connection_pool_size',
    'Redis connection pool size'
)

# Service info
SERVICE_INFO = Info(
    'service_info',
    'Service information'
)

def init_service_info():
    """Initialize service info metrics."""
    SERVICE_INFO.info({
        'version': '1.0.0',
        'service': 'rag-microservice',
        'environment': 'production'
    })

class PrometheusMetrics:
    """Prometheus metrics collector with convenience methods."""
    
    def __init__(self):
        init_service_info()
        logger.info("Prometheus metrics initialized")
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration_seconds: float):
        """Record HTTP request metrics."""
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration_seconds)
    
    def record_ingest_job(self, status: str, document_type: str, duration_seconds: float):
        """Record ingestion job metrics."""
        INGEST_JOBS_TOTAL.labels(status=status, document_type=document_type).inc()
        INGEST_JOB_DURATION.labels(status=status).observe(duration_seconds)
    
    def record_query(self, retriever_type: str, duration_seconds: float, docs_retrieved: int):
        """Record query metrics."""
        QUERY_COUNT.labels(retriever_type=retriever_type).inc()
        QUERY_DURATION.labels(retriever_type=retriever_type).observe(duration_seconds)
        DOCUMENTS_RETRIEVED.labels(retriever_type=retriever_type).observe(docs_retrieved)
    
    def record_embeddings(self, count: int):
        """Record embeddings generated."""
        EMBEDDINGS_GENERATED.inc(count)
    
    def update_system_metrics(self, memory_bytes: float, cpu_percent: float):
        """Update system metrics."""
        MEMORY_USAGE.set(memory_bytes)
        CPU_USAGE.set(cpu_percent)
    
    def update_active_jobs(self, count: int):
        """Update active jobs gauge."""
        ACTIVE_JOBS.set(count)
    
    def get_prometheus_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest()
    
    def get_content_type(self) -> str:
        """Get Prometheus content type."""
        return CONTENT_TYPE_LATEST

# Global Prometheus metrics instance
prometheus_metrics = PrometheusMetrics()