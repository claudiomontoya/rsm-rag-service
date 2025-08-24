"""
Observability module - Tracing, metrics, and logging.

Provides:
- OpenTelemetry distributed tracing
- Langfuse LLM observability
- Prometheus metrics collection
- Structured logging with correlation
- Performance monitoring decorators
"""

from .otel import setup_tracing, get_tracer
from .langfuse import get_langfuse_client, trace_with_langfuse
from .metrics import metrics_registry, record_metric
from .logging_setup import setup_logging, get_logger
from .decorators import traced, timed, monitor_errors

__all__ = [
    "setup_tracing", 
    "get_tracer",
    "get_langfuse_client", 
    "trace_with_langfuse", 
    "metrics_registry", 
    "record_metric",
    "setup_logging",
    "get_logger", 
    "traced", 
    "timed", 
    "monitor_errors"
]