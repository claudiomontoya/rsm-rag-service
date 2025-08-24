from __future__ import annotations
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running" 
    SUCCESS = "success"
    ERROR = "error"

@dataclass
class JobState:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    stage: str = "initialized"
    progress: float = 0.0
    message: Optional[str] = None
    chunks_created: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

class JobRegistry:
    """In-memory job registry for tracking async operations."""
    
    def __init__(self):
        self._jobs: Dict[str, JobState] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()
    
    async def create_job(self) -> JobState:
        """Create a new job."""
        async with self._lock:
            job_id = f"job_{uuid.uuid4().hex[:8]}"
            job = JobState(job_id=job_id)
            self._jobs[job_id] = job
            self._event_queues[job_id] = asyncio.Queue()
            
            # Send initial event
            await self._publish_event(job_id, {
                "type": "job_created",
                "job_id": job_id,
                "status": job.status,
                "timestamp": time.time()
            })
            
            return job
    
    def get_job(self, job_id: str) -> Optional[JobState]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    async def update_job(self, job_id: str, **updates) -> None:
        """Update job state."""
        job = self._jobs.get(job_id)
        if not job:
            return
            
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        job.updated_at = time.time()
        
        # Publish update event
        await self._publish_event(job_id, {
            "type": "job_updated",
            "job_id": job_id,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "message": job.message,
            "chunks_created": job.chunks_created,
            "timestamp": job.updated_at
        })
    
    async def _publish_event(self, job_id: str, event: Dict[str, Any]) -> None:
        """Publish event to job's queue."""
        queue = self._event_queues.get(job_id)
        if queue:
            await queue.put(event)
    
    def get_event_stream(self, job_id: str) -> Optional[asyncio.Queue]:
        """Get event stream for a job."""
        return self._event_queues.get(job_id)

# Global job registry instance
job_registry = JobRegistry()