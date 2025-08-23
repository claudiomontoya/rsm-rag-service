from __future__ import annotations
import os

# Qdrant Configuration
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "docs_v1")

# Embeddings Configuration
EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local").lower()
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")