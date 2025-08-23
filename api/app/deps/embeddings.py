from __future__ import annotations
from typing import Iterable, List
import numpy as np
from app.config import EMBEDDING_PROVIDER, EMBEDDING_MODEL, OPENAI_API_KEY


def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    """Generate embeddings using OpenAI or mock."""
    texts = list(texts)
    
    if EMBEDDING_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.embeddings.create(
                model="text-embedding-3-small", 
                input=texts
            )
            vecs = [e.embedding for e in response.data]
        except Exception as e:
            print(f"⚠️  OpenAI API error: {e}")
            print("⚠️  Using mock embeddings instead")
            vecs = [np.random.rand(1536).tolist() for _ in texts]
    else:
        # Mock embeddings para pruebas sin API key
        print("⚠️  Using mock embeddings (no OpenAI API key)")
        vecs = [np.random.rand(1536).tolist() for _ in texts]
    
    # Normalize vectors
    arr = np.asarray(vecs, dtype=np.float32)
    arr = arr / (np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12)
    return arr.astype(np.float32).tolist()


def embedding_dimension() -> int:
    """Return embedding dimension."""
    return 1536  # OpenAI text-embedding-3-small dimension