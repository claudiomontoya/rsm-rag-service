from __future__ import annotations
from typing import Dict, Any, Optional
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.hybrid_retriever import HybridRetriever

class RetrieverFactory:
    """Factory for creating different retriever types."""
    
    @staticmethod
    def create_retriever(retriever_type: str = "dense"):
        """Create retriever by type."""
        retriever_type = retriever_type.lower()
        
        if retriever_type == "dense":
            return DenseRetriever()
        elif retriever_type == "bm25":
            return BM25Retriever()
        elif retriever_type == "hybrid":
            return HybridRetriever()
        else:
            raise ValueError(f"Unknown retriever type: {retriever_type}")

def _generate_answer(question: str, sources: list, retriever_name: str) -> str:
    """Generate answer based on sources (enhanced from v0.1)."""
    if not sources:
        return "I couldn't find relevant information to answer your question."
    
    # Simple answer generation (will be enhanced with LLM in v0.3)
    context_parts = []
    for i, source in enumerate(sources[:3], 1):
        text_preview = source["text"][:200] + "..." if len(source["text"]) > 200 else source["text"]
        score_info = f" (score: {source.get('score', 0):.2f})" if source.get('score') else ""
        context_parts.append(f"[{i}] {text_preview}{score_info}")
    
    context = " ".join(context_parts)
    
    return f"Based on the retrieved information using {retriever_name} search:\n\n{context}\n\nTo answer your question '{question}': {context[:300]}..."

async def query_documents(question: str, retriever_type: str = "dense", top_k: int = 5) -> Dict[str, Any]:
    """Query documents using specified retriever."""
    try:
        retriever = RetrieverFactory.create_retriever(retriever_type)
        results = await retriever.search(question, top_k=top_k)
        
        # Generate answer
        answer = _generate_answer(question, results, retriever.name)
        
        return {
            "answer": answer,
            "sources": results,
            "retriever_used": retriever.name,
            "metadata": {
                "total_sources": len(results),
                "query_method": retriever_type
            }
        }
        
    except Exception as e:
        raise Exception(f"Query failed: {str(e)}")