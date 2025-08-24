from __future__ import annotations
import asyncio
import time
from typing import List, Dict, Any, Optional
from app.deps.embeddings import embed_texts, embedding_dimension
from app.retrieval.rerank_wrapper import RerankWrapper
from app.retrieval.dense_retriever import DenseRetriever
from app.store.qdrant_store import ensure_collection
from app.obs.logging_setup import get_logger
from app.obs.decorators import traced

logger = get_logger(__name__)

class ModelWarmupService:
    """Service to warm up models during application startup."""
    
    def __init__(self):
        self.warmup_completed = False
        self.warmup_results: Dict[str, Any] = {}
    
    @traced("model_warmup_embeddings")
    async def warmup_embeddings(self) -> Dict[str, Any]:
        """Warm up embedding model."""
        logger.info("Starting embeddings model warm-up")
        
        try:
            start_time = time.time()
            
            # Test embeddings with sample texts
            sample_texts = [
                "This is a test document for warming up the embedding model.",
                "Machine learning and artificial intelligence are transforming technology.",
                "Vector databases enable semantic search capabilities."
            ]
            
            # Generate embeddings
            embeddings = embed_texts(sample_texts)
            
            # Verify results
            if not embeddings or len(embeddings) != len(sample_texts):
                raise ValueError("Embedding generation failed")
            
            # Verify dimensions
            expected_dim = embedding_dimension()
            actual_dim = len(embeddings[0]) if embeddings else 0
            
            if actual_dim != expected_dim:
                logger.warning(f"Embedding dimension mismatch", 
                             expected=expected_dim, 
                             actual=actual_dim)
            
            warmup_time = time.time() - start_time
            
            result = {
                "status": "success",
                "model_type": "embeddings",
                "warmup_time_seconds": round(warmup_time, 3),
                "test_texts": len(sample_texts),
                "embedding_dimension": actual_dim,
                "embeddings_generated": len(embeddings)
            }
            
            logger.info("Embeddings warm-up completed", **result)
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "model_type": "embeddings",
                "error": str(e)
            }
            logger.error("Embeddings warm-up failed", **error_result)
            return error_result
    
    @traced("model_warmup_reranker")
    async def warmup_reranker(self) -> Dict[str, Any]:
        """Warm up reranking model."""
        logger.info("Starting reranker model warm-up")
        
        try:
            from app.config import RERANK_ENABLED, RERANK_MODEL
            
            if not RERANK_ENABLED:
                return {
                    "status": "skipped",
                    "model_type": "reranker",
                    "reason": "Reranking disabled in configuration"
                }
            
            start_time = time.time()
            
            # Create test retriever with reranking
            base_retriever = DenseRetriever()
            rerank_wrapper = RerankWrapper(base_retriever, model_name=RERANK_MODEL)
            
            # Force model loading with test data
            test_query = "test query for model warmup"
            test_candidates = [
                {"text": "This is a relevant document about testing.", "score": 0.8},
                {"text": "Another document for reranking evaluation.", "score": 0.7},
                {"text": "Third test document for model preparation.", "score": 0.6}
            ]
            
            # This will load the model
            reranked = await rerank_wrapper._rerank_candidates(test_query, test_candidates)
            
            warmup_time = time.time() - start_time
            
            result = {
                "status": "success",
                "model_type": "reranker",
                "model_name": RERANK_MODEL,
                "warmup_time_seconds": round(warmup_time, 3),
                "test_candidates": len(test_candidates),
                "reranked_results": len(reranked)
            }
            
            logger.info("Reranker warm-up completed", **result)
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "model_type": "reranker",
                "error": str(e)
            }
            logger.error("Reranker warm-up failed", **error_result)
            return error_result
    
    @traced("model_warmup_vector_db")
    async def warmup_vector_database(self) -> Dict[str, Any]:
        """Warm up vector database connection and collection."""
        logger.info("Starting vector database warm-up")
        
        try:
            start_time = time.time()
            
            # Ensure collection exists
            dim = embedding_dimension()
            ensure_collection(dim)
            
            # Test connection and basic operations
            from app.store.qdrant_store import client, search_vectors
            
            # Get collection info
            collections = client().get_collections()
            collection_count = len(collections.collections)
            
            # Test search with dummy vector
            dummy_vector = [0.1] * dim
            search_results = search_vectors(dummy_vector, limit=1)
            
            warmup_time = time.time() - start_time
            
            result = {
                "status": "success",
                "service_type": "vector_database",
                "warmup_time_seconds": round(warmup_time, 3),
                "collections_found": collection_count,
                "search_test_results": len(search_results),
                "embedding_dimension": dim
            }
            
            logger.info("Vector database warm-up completed", **result)
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "service_type": "vector_database",
                "error": str(e)
            }
            logger.error("Vector database warm-up failed", **error_result)
            return error_result
    
    @traced("full_model_warmup")
    async def warmup_all_models(self) -> Dict[str, Any]:
        """Warm up all models and services."""
        logger.info("Starting full model warm-up sequence")
        
        start_time = time.time()
        results = {}
        
        # Run warm-ups in parallel where possible
        warmup_tasks = [
            ("vector_database", self.warmup_vector_database()),
            ("embeddings", self.warmup_embeddings()),
            ("reranker", self.warmup_reranker())
        ]
        
        for service_name, task in warmup_tasks:
            try:
                result = await task
                results[service_name] = result
            except Exception as e:
                results[service_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        total_time = time.time() - start_time
        
        # Summary
        success_count = sum(1 for r in results.values() if r.get("status") == "success")
        error_count = sum(1 for r in results.values() if r.get("status") == "error")
        
        overall_status = "success" if error_count == 0 else "partial" if success_count > 0 else "failed"
        
        summary = {
            "overall_status": overall_status,
            "total_warmup_time_seconds": round(total_time, 3),
            "services_attempted": len(warmup_tasks),
            "services_successful": success_count,
            "services_failed": error_count,
            "results": results
        }
        
        self.warmup_completed = True
        self.warmup_results = summary
        
        if overall_status == "success":
            logger.info("All model warm-ups completed successfully", **summary)
        else:
            logger.warning("Model warm-up completed with issues", **summary)
        
        return summary

# Global warmup service
model_warmup_service = ModelWarmupService()