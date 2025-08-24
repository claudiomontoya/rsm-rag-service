from __future__ import annotations
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import uuid
from app.config import QDRANT_URL, COLLECTION_NAME

_client: QdrantClient | None = None

def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
    return _client

def ensure_collection(dim: int) -> None:
    """Create collection if it doesn't exist."""
    c = client()
    try:
        c.get_collection(COLLECTION_NAME)
    except:
        c.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

def add_documents(texts: List[str], embeddings: List[List[float]]) -> int:
    """Add documents to Qdrant."""
    points = []
    for i, (text, embedding) in enumerate(zip(texts, embeddings)):
        points.append(PointStruct(
            id=uuid.uuid4().hex,
            vector=embedding,
            payload={"text": text, "page": i + 1}
        ))
    
    client().upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)

def search_similar(query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
    """Search for similar documents."""
    results = client().search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit
    )
    
    return [
        {
            "text": hit.payload["text"],
            "page": hit.payload.get("page"),
            "score": float(hit.score)
        }
        for hit in results
    ]
def search_vectors(query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
    """Search vectors in Qdrant."""
    return search_similar(query_vector, limit)    