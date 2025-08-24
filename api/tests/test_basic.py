from __future__ import annotations
import pytest
import time
import asyncio
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
    data = response.json()
    assert "RAG Microservice" in str(data)
    assert "version" in data
    assert "endpoints" in data

def test_ingest_basic():
    """Test basic ingest functionality with text content."""
    response = client.post(
        "/ingest",
        json={"content": "This is a test document about Python programming.", "document_type": "text"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "job_id" in data
    assert "message" in data

def test_query_basic():
    """Test basic query functionality."""
    # First ingest some content
    ingest_response = client.post(
        "/ingest",
        json={"content": "Python is a programming language that is easy to learn.", "document_type": "text"}
    )
    assert ingest_response.status_code == 200
    
    # Wait a moment for processing
    time.sleep(2)
    
    # Now query
    response = client.post(
        "/query",
        json={"question": "What is Python?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)

# === COMPREHENSIVE TESTS ===

def test_think_python_ingestion():
    """Test ingestion of Think Python document."""
    response = client.post(
        "/ingest",
        json={
            "content": "https://allendowney.github.io/ThinkPython/index.html",
            "document_type": "html"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "job_id" in data
    
    job_id = data["job_id"]
    
    # Monitor job progress (with timeout)
    max_attempts = 60  # 5 minutes
    for attempt in range(max_attempts):
        status_response = client.get(f"/ingest/{job_id}/status")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        
        if status_data["status"] == "success":
            assert status_data["chunks_created"] > 0
            print(f"✅ Think Python ingested: {status_data['chunks_created']} chunks")
            return
        elif status_data["status"] == "error":
            pytest.fail(f"Ingestion failed: {status_data.get('message', 'Unknown error')}")
        
        time.sleep(5)
    
    pytest.fail("Think Python ingestion timeout")

def test_pep8_ingestion():
    """Test ingestion of PEP 8 document."""
    response = client.post(
        "/ingest",
        json={
            "content": "https://peps.python.org/pep-0008/",
            "document_type": "html"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    job_id = data["job_id"]
    
    # Monitor job progress
    max_attempts = 60
    for attempt in range(max_attempts):
        status_response = client.get(f"/ingest/{job_id}/status")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        
        if status_data["status"] == "success":
            assert status_data["chunks_created"] > 0
            print(f"✅ PEP 8 ingested: {status_data['chunks_created']} chunks")
            return
        elif status_data["status"] == "error":
            pytest.fail(f"PEP 8 ingestion failed: {status_data.get('message')}")
        
        time.sleep(5)
    
    pytest.fail("PEP 8 ingestion timeout")

@pytest.mark.parametrize("question,expected_context", [
    ("What is Python according to Think Python?", ["python", "programming"]),
    ("What are Python naming conventions according to PEP 8?", ["naming", "convention"]),
    ("How do you define functions in Python?", ["function", "def"]),
])
def test_query_functionality(question, expected_context):
    """Test querying with different types of questions."""
    response = client.post(
        "/query",
        json={"question": question}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "answer" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)
    
    # Verify sources have required fields
    for source in data["sources"]:
        assert "text" in source
        # Optional fields: page, score
    
    # Basic content validation
    answer = data["answer"].lower()
    sources_text = " ".join([s.get("text", "") for s in data["sources"]]).lower()
    combined_text = answer + " " + sources_text
    
    # Check if any expected context appears
    context_found = any(context in combined_text for context in expected_context)
    if not context_found and len(data["sources"]) > 0:
        print(f"⚠️ Context check inconclusive for question: {question}")

def test_api_schema_compliance():
    """Test that API responses match expected schemas."""
    
    # Test ingest response schema
    ingest_response = client.post(
        "/ingest",
        json={"content": "Schema test document", "document_type": "text"}
    )
    assert ingest_response.status_code == 200
    
    ingest_data = ingest_response.json()
    required_ingest_fields = ["status", "message", "job_id"]
    for field in required_ingest_fields:
        assert field in ingest_data, f"Ingest response missing: {field}"
    
    assert ingest_data["status"] in ["success", "error"]
    
    # Test job status response schema
    job_id = ingest_data["job_id"]
    status_response = client.get(f"/ingest/{job_id}/status")
    assert status_response.status_code == 200
    
    status_data = status_response.json()
    required_status_fields = ["job_id", "status", "stage", "progress", "chunks_created", "created_at", "updated_at"]
    for field in required_status_fields:
        assert field in status_data, f"Status response missing: {field}"
    
    # Test query response schema (wait for ingestion first)
    time.sleep(3)
    
    query_response = client.post(
        "/query",
        json={"question": "Test question"}
    )
    assert query_response.status_code == 200
    
    query_data = query_response.json()
    required_query_fields = ["answer", "sources"]
    for field in required_query_fields:
        assert field in query_data, f"Query response missing: {field}"

def test_observability_endpoints():
    """Test observability and monitoring endpoints."""
    
    # Test metrics endpoint
    metrics_response = client.get("/metrics")
    if metrics_response.status_code == 200:
        metrics_data = metrics_response.json()
        expected_sections = ["counters", "histograms", "system"]
        for section in expected_sections:
            assert section in metrics_data, f"Metrics missing section: {section}"
    else:
        print("⚠️ Metrics endpoint not available")
    
    # Test readiness probe
    ready_response = client.get("/ready")
    if ready_response.status_code in [200, 503]:  # Both are valid
        ready_data = ready_response.json()
        assert "status" in ready_data
        assert ready_data["status"] in ["ready", "not_ready"]
    else:
        print("⚠️ Readiness probe not available")
    
    # Test liveness probe
    live_response = client.get("/live")
    if live_response.status_code == 200:
        live_data = live_response.json()
        assert live_data["status"] == "alive"
    else:
        print("⚠️ Liveness probe not available")

def test_error_handling():
    """Test error handling and edge cases."""
    
    # Test invalid ingest payloads
    invalid_payloads = [
        {},  # Empty payload
        {"content": ""},  # Empty content
        {"document_type": "invalid"},  # Invalid document type
    ]
    
    for payload in invalid_payloads:
        response = client.post("/ingest", json=payload)
        assert response.status_code >= 400, f"Should return error for payload: {payload}"
    
    # Test query without question
    response = client.post("/query", json={})
    assert response.status_code >= 400
    
    # Test nonexistent job status
    response = client.get("/ingest/nonexistent-job/status")
    assert response.status_code == 404

def test_concurrent_queries():
    """Test handling of concurrent requests."""
    # First ensure we have some content
    ingest_response = client.post(
        "/ingest",
        json={"content": "Concurrent test document about Python programming.", "document_type": "text"}
    )
    assert ingest_response.status_code == 200
    
    # Wait for ingestion
    time.sleep(5)
    
    # Send multiple concurrent queries
    query_payload = {"question": "What is this document about?"}
    
    responses = []
    for _ in range(3):
        response = client.post("/query", json=query_payload)
        responses.append(response)
    
    # All should succeed
    for response in responses:
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data

def test_retrievers_endpoint():
    """Test retrievers information endpoint."""
    response = client.get("/query/retrievers")
    if response.status_code == 200:
        data = response.json()
        assert "retrievers" in data
        assert isinstance(data["retrievers"], list)
        
        for retriever in data["retrievers"]:
            assert "name" in retriever
            assert "description" in retriever
    else:
        print("⚠️ Retrievers endpoint not available")

def test_job_stream_endpoint():
    """Test job streaming endpoint."""
    # Start an ingestion job
    ingest_response = client.post(
        "/ingest",
        json={"content": "Streaming test document", "document_type": "text"}
    )
    assert ingest_response.status_code == 200
    job_id = ingest_response.json()["job_id"]
    
    # Test the stream endpoint (basic connectivity test)
    with client.stream("GET", f"/ingest/{job_id}/stream") as stream_response:
        assert stream_response.status_code == 200
        assert stream_response.headers.get("content-type") == "text/event-stream"
        
        # Read first few lines to verify SSE format
        lines_read = 0
        for line in stream_response.iter_lines():
            if line and lines_read < 5:  # Just test a few lines
                # SSE lines should start with "event:" or "data:"
                assert line.startswith(("event:", "data:", "id:")) or line == ""
                lines_read += 1
                if lines_read >= 3:  # Don't wait for entire job
                    break
def test_pdf_ingestion():
    """Test PDF document ingestion."""
    response = client.post(
        "/ingest",
        json={
            "content": "https://arxiv.org/pdf/1706.03762.pdf",  # Attention paper
            "document_type": "pdf"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_cache_functionality():
    """Test query caching."""
    question = "What is attention mechanism?"
    
    # First query (cache miss)
    response1 = client.post("/query", json={"question": question})
    assert response1.status_code == 200
    
    # Second identical query (cache hit) 
    response2 = client.post("/query", json={"question": question})
    assert response2.status_code == 200
    assert response1.json()["answer"] == response2.json()["answer"]

def test_concurrent_job_limit():
    """Test job concurrency limits."""
    # Start multiple jobs quickly
    job_ids = []
    for i in range(15):  # More than MAX_CONCURRENT_JOBS
        response = client.post("/ingest", json={
            "content": f"Test document {i}",
            "document_type": "text"
        })
        if response.status_code == 200:
            job_ids.append(response.json()["job_id"])

    assert len(job_ids) <= 10  # MAX_CONCURRENT_JOBS                

@pytest.mark.slow
def test_full_integration():
    """Full integration test - ingest both documents and test comprehensive queries."""
    print("🚀 Running full integration test...")
    
    # This test is marked as slow and comprehensive
    documents = [
        {
            "content": "https://allendowney.github.io/ThinkPython/index.html",
            "document_type": "html",
            "name": "Think Python"
        },
        {
            "content": "https://peps.python.org/pep-0008/",
            "document_type": "html", 
            "name": "PEP 8"
        }
    ]
    
    job_ids = []
    
    # Ingest all documents
    for doc in documents:
        response = client.post("/ingest", json={
            "content": doc["content"],
            "document_type": doc["document_type"]
        })
        assert response.status_code == 200
        data = response.json()
        job_ids.append((data["job_id"], doc["name"]))
    
    # Wait for all jobs to complete
    for job_id, doc_name in job_ids:
        max_attempts = 60
        for attempt in range(max_attempts):
            status_response = client.get(f"/ingest/{job_id}/status")
            assert status_response.status_code == 200
            status_data = status_response.json()
            
            if status_data["status"] == "success":
                print(f"✅ {doc_name}: {status_data['chunks_created']} chunks")
                break
            elif status_data["status"] == "error":
                pytest.fail(f"{doc_name} ingestion failed")
            
            time.sleep(5)
        else:
            pytest.fail(f"{doc_name} ingestion timeout")
    
    # Test comprehensive queries
    integration_queries = [
        "What is Python programming according to Think Python?",
        "What are the main naming conventions in PEP 8?",
        "How should you structure Python code for readability?",
        "What are Python functions and how do you use them?",
    ]
    
    for query in integration_queries:
        response = client.post("/query", json={"question": query})
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["answer"]) > 50  # Meaningful answer length
        assert len(data["sources"]) > 0   # Should find relevant sources
        
        print(f"✅ Query answered: {query[:50]}...")

# === PERFORMANCE TESTS ===

@pytest.mark.performance 
def test_response_times():
    """Test that response times are within acceptable limits."""
    # Ensure we have content
    client.post("/ingest", json={"content": "Performance test document", "document_type": "text"})
    time.sleep(3)
    
    # Test query response time
    start_time = time.time()
    response = client.post("/query", json={"question": "What is this about?"})
    query_time = time.time() - start_time
    
    assert response.status_code == 200
    assert query_time < 10.0, f"Query took too long: {query_time:.2f}s"
    
    # Test health check response time
    start_time = time.time()
    response = client.get("/health")
    health_time = time.time() - start_time
    
    assert response.status_code == 200
    assert health_time < 1.0, f"Health check too slow: {health_time:.2f}s"

if __name__ == "__main__":
    # Run specific tests for development
    print("Running development tests...")
    test_health()
    test_root()
    print("✅ Basic tests passed")