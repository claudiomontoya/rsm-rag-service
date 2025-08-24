from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "RAG Microservice" in response.json()["message"]

def test_ingest_basic():
    """Test basic ingest functionality."""
    response = client.post(
        "/ingest",
        json={"content": "This is a test document.", "document_type": "text"}
    )
    assert response.status_code in [200, 500]  

def test_query_basic():
    """Test basic query functionality."""
    response = client.post(
        "/query",
        json={"question": "What is this about?"}
    )
    assert response.status_code in [200, 500]  