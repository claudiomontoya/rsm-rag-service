import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_sse_reconnection():
    """Test SSE reconnection with event replay."""
    
    # Start ingestion job
    response = client.post("/ingest", json={
        "content": "Test document for SSE",
        "document_type": "text"
    })
    job_id = response.json()["job_id"]
    
    # First connection - simulate early disconnect
    events_received = []
    
    with client.stream("GET", f"/ingest/{job_id}/stream") as stream:
        lines = []
        for line in stream.iter_lines():
            lines.append(line)
            if len(lines) >= 6:  # Get first few events
                break
    
    # Parse events to get last event ID
    last_event_id = None
    for line in lines:
        if line.startswith("id: "):
            last_event_id = line[4:]
    
    # Second connection - with Last-Event-ID header
    reconnect_headers = {}
    if last_event_id:
        reconnect_headers["Last-Event-ID"] = last_event_id
        reconnect_headers["X-Client-ID"] = "test_client_123"
    
    with client.stream("GET", f"/ingest/{job_id}/stream", headers=reconnect_headers) as stream:
        reconnect_events = []
        for line in stream.iter_lines():
            if line.startswith("event: replay"):
                reconnect_events.append("replay_event")
            if len(reconnect_events) >= 1:  # Found replay event
                break
    
    assert len(reconnect_events) > 0, "Should receive replay events on reconnection"

def test_sse_heartbeat():
    """Test SSE heartbeat functionality."""
    response = client.post("/ingest", json={
        "content": "Heartbeat test",
        "document_type": "text"
    })
    job_id = response.json()["job_id"]
    
    heartbeat_received = False
    with client.stream("GET", f"/ingest/{job_id}/stream") as stream:
        for line in stream.iter_lines():
            if line.startswith("event: heartbeat"):
                heartbeat_received = True
                break
            # Don't wait too long
            if len(line) > 1000:
                break
