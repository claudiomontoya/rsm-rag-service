from __future__ import annotations
import json
import time
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import redis.asyncio as redis
from app.obs.logging_setup import get_logger
from app.obs.decorators import traced
from app.config import REDIS_URL

logger = get_logger(__name__)

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running" 
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"

@dataclass
class RedisJobState:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    stage: str = "initialized"
    progress: float = 0.0
    message: Optional[str] = None
    chunks_created: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.updated_at == 0.0:
            self.updated_at = time.time()
        if self.metadata is None:
            self.metadata = {}

class RedisJobRegistry:
    """Redis-backed job registry for production durability."""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or REDIS_URL or "redis://localhost:6379"
        self._redis: Optional[redis.Redis] = None
        self._pubsub_clients: Dict[str, redis.Redis] = {}
        
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection with lazy initialization."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    max_connections=20
                )
                # Test connection
                await self._redis.ping()
                logger.info("Redis connection established", redis_url=self.redis_url)
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                raise
        return self._redis
    
    def _job_key(self, job_id: str) -> str:
        """Redis key for job data."""
        return f"job:{job_id}"
    
    def _job_events_key(self, job_id: str) -> str:
        """Redis key for job events stream."""
        return f"job:events:{job_id}"
    
    def _job_list_key(self) -> str:
        """Redis key for job list."""
        return "jobs:active"
    
    @traced("redis_create_job")
    async def create_job(self, timeout_seconds: int = 300, max_retries: int = 3) -> RedisJobState:
        """Create a new job in Redis."""
        redis_client = await self._get_redis()
        
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = RedisJobState(
            job_id=job_id,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries
        )
        
        # Store job in Redis
        job_data = asdict(job)
        job_data["status"] = job.status.value               # Enum -> str
        job_data["metadata"] = json.dumps(job.metadata)     # dict -> str

        # eliminar None (redis no acepta None)
        job_data = {k: v for k, v in job_data.items() if v is not None}

        pipe = redis_client.pipeline()
        pipe.hset(self._job_key(job_id), mapping=job_data)
        pipe.sadd(self._job_list_key(), job_id)
        pipe.expire(self._job_key(job_id), timeout_seconds + 3600)
        await pipe.execute()
        
        # Publish creation event
        await self._publish_event(job_id, {
            "type": "job_created",
            "job_id": job_id,
            "status": job.status.value,
            "timestamp": job.created_at
        })
        
        logger.info(f"Redis job created", job_id=job_id)
        return job
    
    @traced("redis_get_job")
    async def get_job(self, job_id: str) -> Optional[RedisJobState]:
        """Get job from Redis."""
        redis_client = await self._get_redis()
        
        job_data = await redis_client.hgetall(self._job_key(job_id))
        if not job_data:
            return None
        
        # Convert back to dataclass
        job_data['status'] = JobStatus(job_data['status'])
        job_data['progress'] = float(job_data['progress'])
        job_data['chunks_created'] = int(job_data['chunks_created'])
        job_data['created_at'] = float(job_data['created_at'])
        job_data['updated_at'] = float(job_data['updated_at'])
        job_data['retry_count'] = int(job_data['retry_count'])
        job_data['max_retries'] = int(job_data['max_retries'])
        job_data['timeout_seconds'] = int(job_data['timeout_seconds'])
        
        # Parse metadata if present
        if 'metadata' in job_data and job_data['metadata']:
            job_data['metadata'] = json.loads(job_data['metadata'])
        else:
            job_data['metadata'] = {}
        
        return RedisJobState(**job_data)
    
    @traced("redis_update_job")
    async def update_job(self, job_id: str, **updates) -> bool:
        """Update job in Redis."""
        redis_client = await self._get_redis()
        
        # Get current job
        current_job = await self.get_job(job_id)
        if not current_job:
            logger.warning(f"Job not found for update", job_id=job_id)
            return False
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(current_job, key):
                if key == 'status' and isinstance(value, str):
                    value = JobStatus(value)
                setattr(current_job, key, value)
        
        current_job.updated_at = time.time()
        
        # Convert to dict for Redis
        job_data = asdict(current_job)
        job_data['status'] = current_job.status.value
        job_data['metadata'] = json.dumps(current_job.metadata)
        
        # Update in Redis
        await redis_client.hset(self._job_key(job_id), mapping=job_data)
        
        # Publish update event
        await self._publish_event(job_id, {
            "type": "job_updated",
            "job_id": job_id,
            "status": current_job.status.value,
            "stage": current_job.stage,
            "progress": current_job.progress,
            "message": current_job.message,
            "chunks_created": current_job.chunks_created,
            "timestamp": current_job.updated_at
        })
        
        logger.debug(f"Redis job updated", job_id=job_id, **updates)
        return True
    
    async def _publish_event(self, job_id: str, event: Dict[str, Any]) -> None:
        """Publish event to Redis pub/sub."""
        redis_client = await self._get_redis()
        
        event_json = json.dumps(event, default=str)
        await redis_client.publish(self._job_events_key(job_id), event_json)
        
        # Also store in a list for history (limited size)
        pipe = redis_client.pipeline()
        pipe.lpush(f"{self._job_events_key(job_id)}:history", event_json)
        pipe.ltrim(f"{self._job_events_key(job_id)}:history", 0, 99)  # Keep last 100 events
        pipe.expire(f"{self._job_events_key(job_id)}:history", 3600)  # 1 hour TTL
        await pipe.execute()
    
    async def subscribe_to_job_events(self, job_id: str):
        """Subscribe to job events via Redis pub/sub."""
        redis_client = redis.from_url(self.redis_url, decode_responses=True)
        pubsub = redis_client.pubsub()
        
        try:
            await pubsub.subscribe(self._job_events_key(job_id))
            logger.info(f"Subscribed to job events", job_id=job_id)
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        event = json.loads(message['data'])
                        yield event
                    except json.JSONDecodeError:
                        logger.error(f"Invalid event JSON", job_id=job_id)
                        continue
        except Exception as e:
            logger.error(f"Pub/sub error", job_id=job_id, error=str(e))
        finally:
            await pubsub.unsubscribe(self._job_events_key(job_id))
            await redis_client.close()
    
    @traced("redis_list_jobs")
    async def list_active_jobs(self, limit: int = 100) -> List[RedisJobState]:
        """List active jobs."""
        redis_client = await self._get_redis()
        
        job_ids = await redis_client.smembers(self._job_list_key())
        jobs = []
        
        for job_id in list(job_ids)[:limit]:
            job = await self.get_job(job_id)
            if job:
                jobs.append(job)
            else:
                # Clean up stale job ID
                await redis_client.srem(self._job_list_key(), job_id)
        
        return sorted(jobs, key=lambda x: x.updated_at, reverse=True)
    
    @traced("redis_cleanup_job")
    async def cleanup_job(self, job_id: str) -> bool:
        """Clean up job data (for completed/failed jobs)."""
        redis_client = await self._get_redis()
        
        pipe = redis_client.pipeline()
        pipe.delete(self._job_key(job_id))
        pipe.delete(f"{self._job_events_key(job_id)}:history")
        pipe.srem(self._job_list_key(), job_id)
        results = await pipe.execute()
        
        logger.info(f"Redis job cleaned up", job_id=job_id)
        return results[0] > 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Redis health check."""
        try:
            redis_client = await self._get_redis()
            start_time = time.time()
            await redis_client.ping()
            ping_time = (time.time() - start_time) * 1000
            
            info = await redis_client.info("memory")
            active_jobs = await redis_client.scard(self._job_list_key())
            
            return {
                "status": "healthy",
                "ping_ms": round(ping_time, 2),
                "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
                "active_jobs": active_jobs
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Global Redis job registry instance
redis_job_registry = RedisJobRegistry()