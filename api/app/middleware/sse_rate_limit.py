import time
from collections import defaultdict
from typing import Dict
import asyncio

class SSERateLimiter:
    """Rate limiter specifically for SSE connections."""
    
    def __init__(self, max_connections_per_ip: int = 5, window_seconds: int = 60):
        self.max_connections_per_ip = max_connections_per_ip
        self.window_seconds = window_seconds
        self.connections: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client IP is within rate limits."""
        async with self._lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds
            
            # Clean old connections
            self.connections[client_ip] = [
                conn_time for conn_time in self.connections[client_ip]
                if conn_time > window_start
            ]
            
            # Check limit
            if len(self.connections[client_ip]) >= self.max_connections_per_ip:
                return False
            
            # Record this connection
            self.connections[client_ip].append(current_time)
            return True

sse_rate_limiter = SSERateLimiter()