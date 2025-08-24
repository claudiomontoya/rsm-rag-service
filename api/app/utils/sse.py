from __future__ import annotations
import json
from typing import Dict, Any

def create_sse_message(data: Dict[str, Any], event_type: str = "message") -> str:
    """Create a Server-Sent Event formatted message."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"

def create_sse_heartbeat() -> str:
    """Create a heartbeat SSE message."""
    return "event: heartbeat\ndata: {\"type\":\"heartbeat\"}\n\n"

def create_sse_close() -> str:
    """Create a close SSE message."""
    return "event: close\ndata: {\"type\":\"close\"}\n\n"