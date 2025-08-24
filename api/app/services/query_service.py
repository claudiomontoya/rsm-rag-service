from __future__ import annotations
from typing import Dict, Any, Optional
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.rerank_wrapper import create_rerank_retriever
from app.obs.decorators import traced, timed
from app.obs.langfuse import trace_with_langfuse, log_retrieval
from app.obs.logging_setup import get_logger
from app.obs.metrics import inc_counter, record_duration
from app.config import RERANK_ENABLED
from app.services.llm_service import llm_service
logger = get_logger(__name__)

class RetrieverFactory:
    """Factory for creating different retriever types with observability."""
    
    @staticmethod
    @traced(operation_name="create_retriever")
    def create_retriever(retriever_type: str = "dense"):
        """Create retriever by type with optional reranking."""
        retriever_type = retriever_type.lower()
        
        logger.info(f"Creating retriever", retriever_type=retriever_type)
        
        # Create base retriever
        if retriever_type == "dense":
            base_retriever = DenseRetriever()
        elif retriever_type == "bm25":
            base_retriever = BM25Retriever()
        elif retriever_type == "hybrid":
            base_retriever = HybridRetriever()
        elif retriever_type.endswith("_rerank"):
            # Handle explicit rerank request
            base_type = retriever_type.replace("_rerank", "")
            base_retriever = RetrieverFactory.create_retriever(base_type)
            return create_rerank_retriever(base_retriever, enabled=True)
        else:
            logger.error(f"Unknown retriever type", retriever_type=retriever_type)
            raise ValueError(f"Unknown retriever type: {retriever_type}")
        
        # Optionally wrap with reranking
        if RERANK_ENABLED and not retriever_type.endswith("_rerank"):
            logger.info("Wrapping retriever with reranking", base_type=retriever_type)
            return create_rerank_retriever(base_retriever, enabled=True)
        
        return base_retriever

@traced(operation_name="generate_answer", include_args=True)
async def _generate_answer(question: str, sources: list, retriever_name: str) -> str:
    """Generate answer using LLM service."""
    return await llm_service.generate_answer(question, sources)

@traced(operation_name="query_documents", langfuse_trace=True)
@timed("query_duration_ms")
async def query_documents(question: str, retriever_type: str = "dense", top_k: int = 5) -> Dict[str, Any]:
    """Query documents with comprehensive observability."""
    
    logger.info(f"Processing query", 
               question=question,
               retriever_type=retriever_type,
               top_k=top_k)
    
    with trace_with_langfuse("document_query", {
        "question": question,
        "retriever_type": retriever_type,
        "top_k": top_k
    }) as lf_ctx:
        
        try:
            # Create retriever
            retriever = RetrieverFactory.create_retriever(retriever_type)
            
            # Perform search
            logger.info(f"Searching with {retriever.name}")
            results = await retriever.search(question, top_k=top_k)
            
            # Log retrieval to Langfuse
            if lf_ctx and lf_ctx.get("trace"):
                log_retrieval(lf_ctx["trace"], question, results, retriever.name)
            
            # Generate answer
            answer = _generate_answer(question, results, retriever.name)
            
            # Record metrics
            inc_counter("queries_processed", {"retriever": retriever.name})
            inc_counter("documents_retrieved", value=len(results))
            
            response = {
                "answer": answer,
                "sources": results,
                "retriever_used": retriever.name,
                "metadata": {
                    "total_sources": len(results),
                    "query_method": retriever_type,
                    "avg_score": sum(r.get("score", 0) for r in results) / len(results) if results else 0
                }
            }
            
            logger.info(f"Query completed successfully", 
                       retriever=retriever.name,
                       sources_found=len(results))
            
            # Log to Langfuse
            if lf_ctx and lf_ctx.get("trace"):
                lf_ctx["trace"].update(output={
                    "answer_preview": answer[:100],
                    "sources_count": len(results)
                })
            
            return response
            
        except Exception as e:
            logger.error(f"Query failed", 
                        question=question,
                        retriever_type=retriever_type,
                        error=str(e),
                        exc_info=True)
            
            # Record error metrics
            inc_counter("queries_failed", {"retriever": retriever_type})
            
            # Log to Langfuse
            if lf_ctx and lf_ctx.get("trace"):
                lf_ctx["trace"].update(output={
                    "status": "error",
                    "error": str(e)
                })
            
            raise Exception(f"Query failed: {str(e)}")