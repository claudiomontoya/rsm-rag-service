from __future__ import annotations
import time
from typing import Dict, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Basic security middleware for production."""
    
    def __init__(
        self,
        app,
        rate_limit_requests: int = 100,
        rate_limit_window: int = 60,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        timeout_seconds: int = 30
    ):
        super().__init__(app)
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.max_request_size = max_request_size
        self.timeout_seconds = timeout_seconds
        
        # Simple in-memory rate limiting (use Redis in production cluster)
        self.request_counts: Dict[str, list] = {}
        self.blocked_ips: Set[str] = set()
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP with proxy header support."""
        # Check proxy headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        return request.client.host if request.client else "unknown"
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client exceeds rate limit."""
        if client_ip == "unknown":
            return True  # Allow unknown IPs (internal calls)
        
        current_time = time.time()
        window_start = current_time - self.rate_limit_window
        
        # Clean old entries
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                timestamp for timestamp in self.request_counts[client_ip]
                if timestamp > window_start
            ]
        else:
            self.request_counts[client_ip] = []
        
        # Check limit
        request_count = len(self.request_counts[client_ip])
        
        if request_count >= self.rate_limit_requests:
            logger.warning(
                f"Rate limit exceeded",
                client_ip=client_ip,
                requests_in_window=request_count,
                limit=self.rate_limit_requests
            )
            return False
        
        # Record this request
        self.request_counts[client_ip].append(current_time)
        return True
    
    def _check_request_size(self, request: Request) -> bool:
        """Check request size limits."""
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    logger.warning(
                        f"Request size too large",
                        size_bytes=size,
                        limit_bytes=self.max_request_size,
                        client_ip=self._get_client_ip(request)
                    )
                    return False
            except ValueError:
                pass
        
        return True
    
    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
    
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = self._get_client_ip(request)
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            logger.warning(f"Blocked IP attempted access", client_ip=client_ip)
            return JSONResponse(
                {"error": "Access denied"},
                status_code=403
            )
        
        # Rate limiting
        if not self._check_rate_limit(client_ip):
            return JSONResponse(
                {"error": "Rate limit exceeded", "retry_after": self.rate_limit_window},
                status_code=429
            )
        
        # Request size check
        if not self._check_request_size(request):
            return JSONResponse(
                {"error": "Request too large"},
                status_code=413
            )
        
        # Process request with timeout
        import asyncio
        
        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Request timeout",
                client_ip=client_ip,
                path=request.url.path,
                timeout=self.timeout_seconds
            )
            return JSONResponse(
                {"error": "Request timeout"},
                status_code=408
            )
        
        # Add security headers
        self._add_security_headers(response)
        
        return response

class ContentSanitizer:
    """Utility class for sanitizing input content."""
    
    @staticmethod
    def sanitize_html(html: str, max_length: int = 1_000_000) -> str:
        """Sanitize HTML content for security."""
        if len(html) > max_length:
            raise ValueError(f"HTML content too large: {len(html)} > {max_length}")
        
        # Remove potentially dangerous elements
        import re
        
        # Remove script tags and content
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove style tags and content  
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove dangerous attributes
        dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'javascript:']
        for attr in dangerous_attrs:
            html = re.sub(rf'{attr}[^>]*', '', html, flags=re.IGNORECASE)
        
        # Remove data: URLs (potential XSS vector)
        html = re.sub(r'data:[^"\'>\s]+', '', html, flags=re.IGNORECASE)
        
        return html
    
    @staticmethod
    def sanitize_markdown(markdown: str, max_length: int = 1_000_000) -> str:
        """Sanitize Markdown content."""
        if len(markdown) > max_length:
            raise ValueError(f"Markdown content too large: {len(markdown)} > {max_length}")
        
        import re
        
        # Remove HTML script tags that might be embedded
        markdown = re.sub(r'<script[^>]*>.*?</script>', '', markdown, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove potentially dangerous HTML attributes in embedded HTML
        markdown = re.sub(r'onclick\s*=\s*["\'][^"\']*["\']', '', markdown, flags=re.IGNORECASE)
        markdown = re.sub(r'javascript:[^"\'>\s]+', '', markdown, flags=re.IGNORECASE)
        
        return markdown
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize URL for safe fetching."""
        if not url.startswith(('http://', 'https://')):
            raise ValueError("Only HTTP/HTTPS URLs are allowed")
        
        # Block localhost and private IP ranges
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        
        if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
            raise ValueError("Localhost URLs not allowed")
        
        # Block private IP ranges (basic check)
        if parsed.hostname and (
            parsed.hostname.startswith('192.168.') or
            parsed.hostname.startswith('10.') or  
            parsed.hostname.startswith('172.16.')
        ):
            raise ValueError("Private IP addresses not allowed")
        
        return url