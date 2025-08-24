from __future__ import annotations
from typing import List, Dict, Any
from .interfaces import Retriever
from app.store.memory_bm25 import bm25_index

class BM25Retriever(Retriever):
    """BM25 keyword-based retriever."""
    
    @property
    def name(self) -> str:
        return "bm25"
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using BM25 keyword matching."""
        results = bm25_index.search(query, top_k=top_k)
        formatted_results = []
        for result in results:
            formatted_results.append({
                "text": result["text"],
                "page": result.get("page"),
                "score": result["score"]
            })
        
        return formatted_results