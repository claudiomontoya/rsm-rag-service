from __future__ import annotations
from typing import List, Dict, Any
from .interfaces import Retriever
from app.deps.embeddings import embed_texts
from app.store.qdrant_store import search_similar

class DenseRetriever(Retriever):
    """Dense vector similarity retriever using OpenAI embeddings."""
    
    @property
    def name(self) -> str:
        return "dense"
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using dense vector similarity."""
        # Generate query embedding
        query_embeddings = embed_texts([query])
        query_vector = query_embeddings[0]
        
        # Search in Qdrant
        results = search_similar(query_vector, limit=top_k)
        
        return results