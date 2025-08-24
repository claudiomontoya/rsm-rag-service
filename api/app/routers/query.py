from __future__ import annotations
import asyncio
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Query as QueryParam
from fastapi.responses import StreamingResponse
from app.models.schemas import QueryRequest, QueryResponse, Source
from app.services.query_service import query_documents, RetrieverFactory
from app.utils.sse import create_sse_message, create_sse_heartbeat, create_sse_close

router = APIRouter(prefix="/query", tags=["query"])

@router.post("", response_model=QueryResponse)
async def query_documents_endpoint(
    request: QueryRequest,
    retriever: Optional[str] = QueryParam(default="dense", description="Retriever type: dense, bm25, hybrid"),
    top_k: int = QueryParam(default=5, ge=1, le=20, description="Number of results to return")
) -> QueryResponse:
    """Query documents using specified retriever."""
    try:
        result = await query_documents(
            question=request.question,
            retriever_type=retriever,
            top_k=top_k
        )
        sources = [
            Source(
                page=source.get("page"),
                text=source["text"],
                score=source.get("score")
            )
            for source in result["sources"]
        ]
        
        return QueryResponse(
            answer=result["answer"],
            sources=sources,
            retriever_used=result["retriever_used"],
            metadata=result.get("metadata")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream")
async def stream_query(
    q: str = QueryParam(..., description="Question to ask"),
    retriever: Optional[str] = QueryParam(default="dense", description="Retriever type"),
    top_k: int = QueryParam(default=5, ge=1, le=20, description="Number of results")
):
    """Stream query results via Server-Sent Events."""
    
    async def event_generator():
        """Generate SSE events for query process."""
        try:
            yield create_sse_message({
                "type": "search_start",
                "question": q,
                "retriever": retriever,
                "top_k": top_k,
                "timestamp": time.time()
            })
            retriever_obj = RetrieverFactory.create_retriever(retriever)
            
            yield create_sse_message({
                "type": "search_progress",
                "message": f"Searching using {retriever_obj.name} retriever...",
                "timestamp": time.time()
            })
            
            results = await retriever_obj.search(q, top_k=top_k)
            
            yield create_sse_message({
                "type": "search_results",
                "results_count": len(results),
                "retriever_used": retriever_obj.name,
                "timestamp": time.time()
            })
            
            for i, result in enumerate(results):
                yield create_sse_message({
                    "type": "search_result",
                    "index": i + 1,
                    "page": result.get("page"),
                    "text_preview": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
                    "score": result.get("score"),
                    "timestamp": time.time()
                })
                
                await asyncio.sleep(0.1)
            
            yield create_sse_message({
                "type": "generation_start",
                "message": "Generating answer...",
                "timestamp": time.time()
            })
            
            answer_parts = [
                f"Based on {len(results)} sources using {retriever_obj.name} search:\n\n",
                f"Question: {q}\n\n",
                "Answer: "
            ]
            
            if results:
                best_source = results[0]
                answer_text = best_source["text"][:300] + "..." if len(best_source["text"]) > 300 else best_source["text"]
                answer_parts.append(answer_text)
            else:
                answer_parts.append("I couldn't find relevant information to answer your question.")
            
            for part in answer_parts:
                yield create_sse_message({
                    "type": "generation_chunk",
                    "chunk": part,
                    "timestamp": time.time()
                })
                await asyncio.sleep(0.2)
            
            yield create_sse_message({
                "type": "generation_complete",
                "total_sources": len(results),
                "timestamp": time.time()
            })
            
        except Exception as e:
            yield create_sse_message({
                "type": "error",
                "error": str(e),
                "timestamp": time.time()
            })
        finally:
            yield create_sse_close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

@router.get("/retrievers")
async def list_retrievers():
    """List available retrievers."""
    return {
        "retrievers": [
            {
                "name": "dense",
                "description": "Dense vector similarity using OpenAI embeddings",
                "type": "semantic"
            },
            {
                "name": "bm25", 
                "description": "BM25 keyword-based search",
                "type": "lexical"
            },
            {
                "name": "hybrid",
                "description": "Combination of dense and BM25 search",
                "type": "hybrid"
            }
        ]
    }