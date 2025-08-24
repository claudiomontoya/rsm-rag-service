from __future__ import annotations
import json
import time
import os
from typing import Dict, Any, Optional
import redis.asyncio as redis
from app.config import REDIS_URL
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

class DistributedSSEManager:
    """Redis-backed SSE manager for multi-instance deployment."""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or REDIS_URL
        self._redis: Optional[redis.Redis] = None
        self.instance_id = f"api_{time.time()}_{os.getpid()}"
    
    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                connection_pool_class=redis.BlockingConnectionPool,
                max_connections=10
            )
        return self._redis
    
    def _connection_key(self, connection_id: str) -> str:
        return f"sse:conn:{connection_id}"
    
    def _event_history_key(self, job_id: str) -> str:
        return f"sse:events:{job_id}"
    
    async def store_connection(self, connection_data: Dict[str, Any], ttl: int = 3600):
        """Store connection state in Redis."""
        redis_client = await self._get_redis()
        key = self._connection_key(connection_data["connection_id"])
        
        await redis_client.hset(key, mapping={
            "data": json.dumps(connection_data),
            "instance_id": self.instance_id,
            "created_at": time.time()
        })
        await redis_client.expire(key, ttl)
    
    async def get_connection(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get connection state from Redis."""
        redis_client = await self._get_redis()
        key = self._connection_key(connection_id)
        
        data = await redis_client.hget(key, "data")
        if data:
            return json.loads(data)
        return None
    
    async def store_event(self, job_id: str, event: Dict[str, Any], max_events: int = 100):
        """Store event in Redis for replay."""
        redis_client = await self._get_redis()
        key = self._event_history_key(job_id)
        
        # Store event with timestamp as score
        event_data = json.dumps(event)
        await redis_client.zadd(key, {event_data: time.time()})
        
        # Keep only last N events
        await redis_client.zremrangebyrank(key, 0, -(max_events + 1))
        
        # Set TTL
        await redis_client.expire(key, 3600)  # 1 hour
    
    async def get_events_after(self, job_id: str, after_timestamp: float) -> List[Dict[str, Any]]:
        """Get events after specific timestamp."""
        redis_client = await self._get_redis()
        key = self._event_history_key(job_id)
        
        # Get events with score > after_timestamp
        events_data = await redis_client.zrangebyscore(
            key, after_timestamp, "+inf", withscores=False
        )
        
        events = []
        for event_data in events_data:
            try:
                events.append(json.loads(event_data))
            except json.JSONDecodeError:
                continue
        
        return events

distributed_sse_manager = DistributedSSEManager()