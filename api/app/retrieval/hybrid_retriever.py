from __future__ import annotations
from typing import List, Dict, Any
from .interfaces import Retriever
from .dense_retriever import DenseRetriever
from .bm25_retriever import BM25Retriever

class HybridRetriever(Retriever):
    """Hybrid retriever combining dense and sparse (BM25) search."""
    
    def __init__(self, dense_weight: float = 0.7, bm25_weight: float = 0.3):
        self.dense_retriever = DenseRetriever()
        self.bm25_retriever = BM25Retriever()
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
    
    @property
    def name(self) -> str:
        return "hybrid"
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using both dense and sparse retrieval, then combine scores."""
        # Get results from both retrievers
        dense_results = await self.dense_retriever.search(query, top_k=top_k*2)
        bm25_results = await self.bm25_retriever.search(query, top_k=top_k*2)
        
        # Normalize scores and combine
        combined_scores = {}
        
        # Process dense results
        max_dense_score = max([r["score"] for r in dense_results], default=0)
        if max_dense_score > 0:
            for result in dense_results:
                text = result["text"]
                normalized_score = result["score"] / max_dense_score
                combined_scores[text] = {
                    "text": text,
                    "page": result.get("page"),
                    "score": self.dense_weight * normalized_score,
                    "dense_score": result["score"],
                    "bm25_score": 0
                }
        
        # Process BM25 results
        max_bm25_score = max([r["score"] for r in bm25_results], default=0)
        if max_bm25_score > 0:
            for result in bm25_results:
                text = result["text"]
                normalized_score = result["score"] / max_bm25_score
                
                if text in combined_scores:
                    # Combine with existing dense score
                    combined_scores[text]["score"] += self.bm25_weight * normalized_score
                    combined_scores[text]["bm25_score"] = result["score"]
                else:
                    # New result from BM25 only
                    combined_scores[text] = {
                        "text": text,
                        "page": result.get("page"),
                        "score": self.bm25_weight * normalized_score,
                        "dense_score": 0,
                        "bm25_score": result["score"]
                    }
        
        # Sort by combined score and return top k
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        return sorted_results[:top_k]