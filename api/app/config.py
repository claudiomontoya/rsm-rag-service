from __future__ import annotations
import os

# Qdrant Configuration
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "docs_v1")

# Embeddings Configuration
EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local").lower()
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT: str | None = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "rag-microservice")

# Langfuse Configuration
LANGFUSE_PUBLIC_KEY: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY: str | None = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Reranking Configuration
RERANK_ENABLED: bool = os.getenv("RERANK_ENABLED", "false").lower() == "true"
RERANK_MODEL: str = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")