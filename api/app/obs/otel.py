from __future__ import annotations
import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ALWAYS_ON
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from app.config import OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME

def setup_tracing() -> None:
    """Initialize OpenTelemetry tracing."""
    
    # Set up B3 propagation (widely supported)
    set_global_textmap(B3MultiFormat())
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": OTEL_SERVICE_NAME,
        "service.version": "0.3.0",
        "deployment.environment": os.getenv("ENVIRONMENT", "development")
    })
    
    # Configure sampling (always sample in dev, ratio in prod)
    sample_rate = float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))
    sampler = ALWAYS_ON if sample_rate >= 1.0 else TraceIdRatioBased(sample_rate)
    
    # Create tracer provider
    tracer_provider = TracerProvider(
        resource=resource,
        sampler=sampler
    )
    
    # Add OTLP exporter if endpoint configured
    if OTEL_EXPORTER_OTLP_ENDPOINT:
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces",
            timeout=10
        )
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=512,
            max_export_batch_size=256,
            export_timeout_millis=30000
        )
        tracer_provider.add_span_processor(span_processor)
    
    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)
    
    # Auto-instrument common libraries
    RequestsInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)
    
    print(f"🔍 OpenTelemetry configured for service: {OTEL_SERVICE_NAME}")

def get_tracer(name: str = "rag-microservice") -> trace.Tracer:
    """Get OpenTelemetry tracer instance."""
    return trace.get_tracer(name, version="0.3.0")