from __future__ import annotations
import asyncio
import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from dataclasses import dataclass, field
from collections import deque
import json
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

@dataclass
class SSEEvent:
    """SSE event with metadata for replay."""
    id: str
    event_type: str
    data: Dict[str, Any]
    timestamp: float
    connection_id: str

@dataclass
class SSEConnection:
    """SSE connection state management."""
    connection_id: str
    client_id: str
    job_id: str
    created_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    last_event_id: Optional[str] = None
    is_active: bool = True
    event_buffer: deque = field(default_factory=lambda: deque(maxlen=100))

class RobustSSEManager:
    """Production-ready SSE with reconnection support."""
    
    def __init__(self, heartbeat_interval: int = 30, event_buffer_size: int = 100):
        self.heartbeat_interval = heartbeat_interval
        self.event_buffer_size = event_buffer_size
        
        # Connection tracking
        self.connections: Dict[str, SSEConnection] = {}
        self.job_connections: Dict[str, List[str]] = {}  # job_id -> connection_ids
        
        # Event storage for replay
        self.event_history: Dict[str, deque] = {}  # job_id -> events
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background cleanup of stale connections."""
        async def cleanup_loop():
            while True:
                try:
                    await self._cleanup_stale_connections()
                    await asyncio.sleep(60)  # Cleanup every minute
                except Exception as e:
                    logger.error(f"SSE cleanup error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    def create_connection(
        self, 
        job_id: str, 
        client_id: Optional[str] = None,
        last_event_id: Optional[str] = None
    ) -> SSEConnection:
        """Create or restore SSE connection."""
        
        connection_id = f"sse_{uuid.uuid4().hex[:12]}"
        client_id = client_id or f"client_{uuid.uuid4().hex[:8]}"
        
        connection = SSEConnection(
            connection_id=connection_id,
            client_id=client_id,
            job_id=job_id,
            last_event_id=last_event_id
        )
        
        # Track connection
        self.connections[connection_id] = connection
        
        # Track job connections
        if job_id not in self.job_connections:
            self.job_connections[job_id] = []
        self.job_connections[job_id].append(connection_id)
        
        # Initialize event history for job
        if job_id not in self.event_history:
            self.event_history[job_id] = deque(maxlen=self.event_buffer_size)
        
        logger.info(f"SSE connection created", 
                   connection_id=connection_id,
                   client_id=client_id,
                   job_id=job_id,
                   reconnection=last_event_id is not None)
        
        return connection
    
    def create_sse_event(
        self, 
        event_type: str, 
        data: Dict[str, Any],
        connection: SSEConnection,
        event_id: Optional[str] = None
    ) -> str:
        """Create SSE event with proper formatting and tracking."""
        
        event_id = event_id or f"evt_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        # Create event object
        sse_event = SSEEvent(
            id=event_id,
            event_type=event_type,
            data=data,
            timestamp=time.time(),
            connection_id=connection.connection_id
        )
        
        # Store in connection buffer
        connection.event_buffer.append(sse_event)
        connection.last_event_id = event_id
        
        # Store in job history
        if connection.job_id in self.event_history:
            self.event_history[connection.job_id].append(sse_event)
        
        # Format as SSE
        lines = []
        lines.append(f"id: {event_id}")
        lines.append(f"event: {event_type}")
        
        # Handle multiline data
        json_data = json.dumps(data, ensure_ascii=False, default=str)
        for line in json_data.split('\n'):
            lines.append(f"data: {line}")
        
        lines.append("")  # Empty line to end event
        return "\n".join(lines) + "\n"
    
    def get_missed_events(self, connection: SSEConnection) -> List[SSEEvent]:
        """Get events that client missed during disconnection."""
        
        if not connection.last_event_id or connection.job_id not in self.event_history:
            return []
        
        job_events = list(self.event_history[connection.job_id])
        
        # Find events after last_event_id
        missed_events = []
        found_last = False
        
        for event in job_events:
            if found_last:
                missed_events.append(event)
            elif event.id == connection.last_event_id:
                found_last = True
        
        logger.info(f"Found missed events", 
                   connection_id=connection.connection_id,
                   missed_count=len(missed_events))
        
        return missed_events
    
    async def stream_with_reconnection(
        self,
        connection: SSEConnection,
        event_source: AsyncGenerator[Dict[str, Any], None],
        request: Any
    ) -> AsyncGenerator[str, None]:
        """Stream events with reconnection support."""
        
        try:
            # Send connection start
            yield self.create_sse_event(
                "connection",
                {
                    "type": "connection_start",
                    "connection_id": connection.connection_id,
                    "client_id": connection.client_id,
                    "heartbeat_interval": self.heartbeat_interval,
                    "supports_reconnection": True
                },
                connection
            )
            
            # Send missed events if reconnection
            missed_events = self.get_missed_events(connection)
            for event in missed_events:
                yield self.create_sse_event(
                    "replay",
                    {
                        "type": "event_replay", 
                        "original_event": event.event_type,
                        "original_data": event.data,
                        "original_timestamp": event.timestamp
                    },
                    connection,
                    f"replay_{event.id}"
                )
            
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._send_heartbeats(connection)
            )
            
            # Stream events
            async for event_data in event_source:
                # Check disconnection
                if await request.is_disconnected():
                    logger.info(f"Client disconnected", 
                              connection_id=connection.connection_id)
                    break
                
                # Update connection activity
                connection.last_ping = time.time()
                
                # Send event
                yield self.create_sse_event(
                    event_data.get("type", "message"),
                    event_data,
                    connection
                )
                
                # Break on job completion
                if event_data.get("type") == "job_updated" and \
                   event_data.get("status") in ["success", "error", "cancelled"]:
                    break
            
            # Cancel heartbeat
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled", connection_id=connection.connection_id)
            raise
        except Exception as e:
            logger.error(f"SSE stream error", 
                        connection_id=connection.connection_id, 
                        error=str(e))
            
            # Send error event
            yield self.create_sse_event(
                "error",
                {
                    "type": "stream_error",
                    "message": str(e),
                    "timestamp": time.time()
                },
                connection
            )
        finally:
            # Cleanup connection
            await self._cleanup_connection(connection.connection_id)
    
    async def _send_heartbeats(self, connection: SSEConnection):
        """Send periodic heartbeats to connection."""
        try:
            while connection.is_active:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Check if connection is still tracked
                if connection.connection_id not in self.connections:
                    break
                
                # Update ping time
                connection.last_ping = time.time()
                
                # Heartbeat is sent by yielding from main stream
                logger.debug(f"Heartbeat sent", connection_id=connection.connection_id)
                
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat task cancelled", connection_id=connection.connection_id)
    
    async def _cleanup_connection(self, connection_id: str):
        """Clean up connection resources."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        connection.is_active = False
        
        # Remove from job connections
        if connection.job_id in self.job_connections:
            try:
                self.job_connections[connection.job_id].remove(connection_id)
                
                # Clean up empty job connection lists
                if not self.job_connections[connection.job_id]:
                    del self.job_connections[connection.job_id]
            except ValueError:
                pass
        
        # Remove connection
        del self.connections[connection_id]
        
        logger.info(f"SSE connection cleaned up", connection_id=connection_id)
    
    async def _cleanup_stale_connections(self):
        """Clean up stale connections that haven't pinged recently."""
        current_time = time.time()
        stale_threshold = self.heartbeat_interval * 3  # 3x heartbeat interval
        
        stale_connections = []
        for conn_id, connection in self.connections.items():
            if current_time - connection.last_ping > stale_threshold:
                stale_connections.append(conn_id)
        
        for conn_id in stale_connections:
            logger.warning(f"Cleaning up stale connection", connection_id=conn_id)
            await self._cleanup_connection(conn_id)
        
        # Clean old event history
        for job_id in list(self.event_history.keys()):
            if job_id not in self.job_connections:
                # No active connections for this job
                if len(self.event_history[job_id]) > 0:
                    last_event_time = self.event_history[job_id][-1].timestamp
                    if current_time - last_event_time > 3600:  # 1 hour
                        del self.event_history[job_id]

# Global robust SSE manager
robust_sse_manager = RobustSSEManager()