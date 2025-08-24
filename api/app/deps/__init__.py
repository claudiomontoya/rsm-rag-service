from .embeddings import embed_texts, embedding_dimension

__all__ = ["embed_texts", "embedding_dimension"]
"""
Dependencies module - Shared dependencies and utilities.

Provides:
- Embedding generation (OpenAI/local)
- Dependency injection utilities
- Common service dependencies
"""

from .embeddings import embed_texts, embedding_dimension

__all__ = [
    "embed_texts", 
    "embedding_dimension"
]