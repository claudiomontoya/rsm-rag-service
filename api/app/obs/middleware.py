from __future__ import annotations
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.obs.metrics import inc_counter, record_duration
from app.obs.otel import get_tracer

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""
    
    def __init__(self, app):
        super().__init__(app)
        self.tracer = get_tracer("middleware")
    
    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()
        
        # Extract path and method
        path = request.url.path
        method = request.method
        
        # Start span
        with self.tracer.start_as_current_span(
            f"{method} {path}",
            attributes={
                "http.method": method,
                "http.url": str(request.url),
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname,
            }
        ) as span:
            
            try:
                # Process request
                response: Response = await call_next(request)
                
                # Record metrics
                duration_ms = (time.time() - start_time) * 1000
                status_code = response.status_code
                
                # Labels for metrics
                labels = {
                    "method": method,
                    "path": path,
                    "status": str(status_code)
                }
                
                # Increment request counter
                inc_counter("http_requests_total", labels)
                
                # Record duration
                record_duration("http_request_duration_ms", duration_ms, labels)
                
                # Add span attributes
                span.set_attribute("http.status_code", status_code)
                span.set_attribute("http.response_size", 
                                 response.headers.get("content-length", 0))
                
                # Mark span as success or error
                if status_code >= 400:
                    span.set_attribute("error", True)
                    inc_counter("http_requests_errors_total", labels)
                
                return response
                
            except Exception as e:
                # Record error
                inc_counter("http_requests_errors_total", {
                    "method": method,
                    "path": path,
                    "status": "500"
                })
                
                # Add error to span
                span.record_exception(e)
                span.set_attribute("error", True)
                
                raise