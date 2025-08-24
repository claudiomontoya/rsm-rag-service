from __future__ import annotations
from typing import List, Dict, Any, Optional
from .interfaces import Retriever
from app.obs.decorators import traced, timed
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

class RerankWrapper(Retriever):
    """Wrapper that adds cross-encoder reranking to any retriever."""
    
    def __init__(
        self, 
        base_retriever: Retriever, 
        model_name: str = "BAAI/bge-reranker-v2-m3",
        top_k_candidates: int = 20
    ):
        self.base_retriever = base_retriever
        self.model_name = model_name
        self.top_k_candidates = top_k_candidates
        self._model = None
        logger.info(f"Initialized reranker with model: {model_name}")
    
    def _load_model(self):
        """Lazy load the reranking model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading reranking model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("Reranking model loaded successfully")
            except ImportError as e:
                logger.error("sentence-transformers not available for reranking")
                raise ImportError("sentence-transformers required for reranking") from e
            except Exception as e:
                logger.error(f"Failed to load reranking model: {e}")
                raise
        return self._model
    
    @property
    def name(self) -> str:
        return f"{self.base_retriever.name}_rerank"
    
    @traced(operation_name="rerank_search", include_args=True, langfuse_trace=True)
    @timed("rerank_search_duration_ms")
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search with reranking."""
        
        # Step 1: Get initial candidates from base retriever
        logger.info(
            f"Retrieving candidates using {self.base_retriever.name}",
            query=query,
            candidates_requested=self.top_k_candidates
        )
        
        candidates = await self.base_retriever.search(
            query, 
            top_k=self.top_k_candidates
        )
        
        if not candidates:
            logger.warning("No candidates found by base retriever")
            return []
        
        if len(candidates) <= top_k:
            logger.info(f"Returning {len(candidates)} candidates without reranking")
            return candidates
        
        # Step 2: Rerank using cross-encoder
        logger.info(f"Reranking {len(candidates)} candidates")
        
        try:
            reranked = await self._rerank_candidates(query, candidates)
            final_results = reranked[:top_k]
            
            logger.info(
                f"Reranking complete",
                original_count=len(candidates),
                reranked_count=len(reranked),
                final_count=len(final_results)
            )
            
            return final_results
            
        except Exception as e:
            logger.error(f"Reranking failed, returning base results: {e}")
            return candidates[:top_k]
    
    @traced(operation_name="rerank_candidates")
    @timed("rerank_model_inference_ms")
    async def _rerank_candidates(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rerank candidates using cross-encoder."""
        
        # Load model
        model = self._load_model()
        
        # Prepare query-document pairs
        pairs = []
        for candidate in candidates:
            document_text = candidate.get("text", "")
            pairs.append([query, document_text])
        
        logger.debug(f"Computing cross-encoder scores for {len(pairs)} pairs")
        
        # Get reranking scores
        try:
            scores = model.predict(pairs)
            
            # Add rerank scores to candidates
            for candidate, score in zip(candidates, scores):
                candidate["rerank_score"] = float(score)
                # Keep original score for reference
                if "score" in candidate and "original_score" not in candidate:
                    candidate["original_score"] = candidate["score"]
                # Update main score to rerank score
                candidate["score"] = float(score)
            
            # Sort by rerank score
            reranked = sorted(
                candidates, 
                key=lambda x: x.get("rerank_score", 0), 
                reverse=True
            )
            
            logger.debug(
                f"Reranking scores range: {min(scores):.4f} to {max(scores):.4f}"
            )
            
            return reranked
            
        except Exception as e:
            logger.error(f"Cross-encoder inference failed: {e}")
            raise

def create_rerank_retriever(base_retriever: Retriever, enabled: bool = True) -> Retriever:
    """Factory function to optionally wrap retriever with reranking."""
    if not enabled:
        return base_retriever
    
    from app.config import RERANK_MODEL
    return RerankWrapper(base_retriever, model_name=RERANK_MODEL)