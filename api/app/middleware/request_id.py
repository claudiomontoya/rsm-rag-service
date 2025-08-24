from __future__ import annotations
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add unique request IDs for tracing and correlation."""
    
    def __init__(
        self, 
        app, 
        header_name: str = "X-Request-ID",
        generate_if_missing: bool = True
    ):
        super().__init__(app)
        self.header_name = header_name
        self.generate_if_missing = generate_if_missing
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate request ID
        request_id = request.headers.get(self.header_name.lower())
        
        if not request_id and self.generate_if_missing:
            request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        if request_id:
            # Add to request state for use in handlers
            request.state.request_id = request_id
            
            # Add to logging context
            logger.info(
                f"Request started",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                client_ip=request.client.host if request.client else None
            )
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        if request_id:
            response.headers[self.header_name] = request_id
            
            logger.info(
                f"Request completed",
                request_id=request_id,
                status_code=response.status_code,
                response_size=response.headers.get("content-length", "unknown")
            )
        
        return response