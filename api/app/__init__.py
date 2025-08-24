"""
RAG Microservice - Production-ready Retrieval-Augmented Generation service.

A comprehensive microservicio with:
- Semantic chunking and document ingestion
- Multiple retrieval strategies (dense, BM25, hybrid, reranking)
- Redis-backed job management
- OpenTelemetry observability
- Server-sent events streaming
- Robust error handling and security
"""

__version__ = "1.0.0"
__author__ = "RAG Team"
__description__ = "Production-ready RAG microservice with advanced observability"

# Export main application
from .main import app

__all__ = ["app"]