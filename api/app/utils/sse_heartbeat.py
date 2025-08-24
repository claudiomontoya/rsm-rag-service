from __future__ import annotations
import asyncio
import time
from typing import AsyncGenerator, Dict, Any, Optional
from app.obs.logging_setup import get_logger
from app.config import HEARTBEAT_INTERVAL

logger = get_logger(__name__)

class SSEHeartbeatManager:
    """Manages SSE connections with configurable heartbeats."""
    
    def __init__(self, heartbeat_interval: int = HEARTBEAT_INTERVAL):
        self.heartbeat_interval = heartbeat_interval
        self.active_connections: Dict[str, float] = {}
    
    def create_sse_event(self, event_type: str = "message", data: Dict[str, Any] = None, event_id: Optional[str] = None) -> str:
        """Create properly formatted SSE event."""
        lines = []
        
        if event_id:
            lines.append(f"id: {event_id}")
        
        lines.append(f"event: {event_type}")
        
        if data:
            import json
            json_data = json.dumps(data, ensure_ascii=False, default=str)
            # Handle multiline data
            for line in json_data.split('\n'):
                lines.append(f"data: {line}")
        else:
            lines.append("data: ")
        
        lines.append("")  # Empty line to end event
        return "\n".join(lines) + "\n"
    
    def create_heartbeat(self, connection_id: str) -> str:
        """Create heartbeat event."""
        return self.create_sse_event(
            event_type="heartbeat",
            data={
                "type": "heartbeat",
                "timestamp": time.time(),
                "connection_id": connection_id
            }
        )
    
    def create_connection_start(self, connection_id: str, metadata: Dict[str, Any] = None) -> str:
        """Create connection start event."""
        return self.create_sse_event(
            event_type="connection",
            data={
                "type": "connection_start",
                "connection_id": connection_id,
                "timestamp": time.time(),
                "heartbeat_interval": self.heartbeat_interval,
                **(metadata or {})
            }
        )
    
    def create_connection_end(self, connection_id: str) -> str:
        """Create connection end event."""
        return self.create_sse_event(
            event_type="connection",
            data={
                "type": "connection_end",
                "connection_id": connection_id,
                "timestamp": time.time()
            }
        )
    
    async def heartbeat_stream(
        self, 
        connection_id: str,
        event_source: AsyncGenerator[str, None],
        client_disconnect_check: Optional[callable] = None
    ) -> AsyncGenerator[str, None]:
        """
        Wrap an event source with heartbeat management.
        
        Args:
            connection_id: Unique connection identifier
            event_source: Async generator yielding SSE events
            client_disconnect_check: Optional function to check if client disconnected
        """
        self.active_connections[connection_id] = time.time()
        
        try:
            # Send connection start
            yield self.create_connection_start(connection_id)
            
            # Create heartbeat task
            heartbeat_task = asyncio.create_task(
                self._heartbeat_sender(connection_id)
            )
            
            # Process events from source
            async for event in event_source:
                # Check for client disconnect
                if client_disconnect_check and client_disconnect_check():
                    logger.info(f"Client disconnected", connection_id=connection_id)
                    break
                
                # Update last activity
                self.active_connections[connection_id] = time.time()
                yield event
            
            # Cancel heartbeat
            heartbeat_task.cancel()
            
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled", connection_id=connection_id)
            raise
        except Exception as e:
            logger.error(f"SSE stream error", connection_id=connection_id, error=str(e))
            raise
        finally:
            # Clean up
            self.active_connections.pop(connection_id, None)
            yield self.create_connection_end(connection_id)
    
    async def _heartbeat_sender(self, connection_id: str):
        """Send periodic heartbeats."""
        try:
            while connection_id in self.active_connections:
                await asyncio.sleep(self.heartbeat_interval)
                
                if connection_id in self.active_connections:
                    # Check if connection is stale
                    last_activity = self.active_connections[connection_id]
                    if time.time() - last_activity > self.heartbeat_interval * 3:
                        logger.warning(f"Stale SSE connection detected", connection_id=connection_id)
                        break
                    
                    # This would be yielded by the main stream
                    # In practice, we integrate this differently
                    logger.debug(f"Heartbeat for connection", connection_id=connection_id)
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat error", connection_id=connection_id, error=str(e))

# Global heartbeat manager
sse_heartbeat_manager = SSEHeartbeatManager()