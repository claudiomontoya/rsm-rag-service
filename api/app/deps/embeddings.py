from __future__ import annotations
from typing import Iterable, List
import numpy as np
from app.config import EMBEDDING_PROVIDER, EMBEDDING_MODEL, OPENAI_API_KEY
from openai import OpenAI
from app.obs.logging_setup import get_logger
logger = get_logger(__name__)

def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    texts = list(texts)
    
    if EMBEDDING_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.embeddings.create(
                model="text-embedding-3-small", 
                input=texts
            )
            vecs = [e.embedding for e in response.data]
        except ImportError:
            logger.warning("OpenAI package not installed, using mock embeddings")
            vecs = [np.random.rand(1536).tolist() for _ in texts]
        except Exception as e:
            logger.error(f"OpenAI API error: {e}, falling back to mock embeddings")
            vecs = [np.random.rand(1536).tolist() for _ in texts]
    else:
        logger.info("Using mock embeddings (no OpenAI configuration)")
        vecs = [np.random.rand(1536).tolist() for _ in texts]
    
    arr = np.asarray(vecs, dtype=np.float32)
    arr = arr / (np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12)
    return arr.astype(np.float32).tolist()


def embedding_dimension() -> int:
    """Return embedding dimension."""
    return 1536 