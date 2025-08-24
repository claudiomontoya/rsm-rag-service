from __future__ import annotations
from contextlib import contextmanager
from typing import Optional, Dict, Any
import time
from app.config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

_langfuse_client = None

def get_langfuse_client():
    """Get Langfuse client instance."""
    global _langfuse_client
    
    if _langfuse_client is not None:
        return _langfuse_client
    
    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        print("⚠️  Langfuse not configured (missing API keys)")
        _langfuse_client = None
        return None
    
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST
        )
        print(f"🔗 Langfuse client initialized: {LANGFUSE_HOST}")
        return _langfuse_client
    except ImportError:
        print("⚠️  Langfuse package not installed")
        _langfuse_client = None
        return None
    except Exception as e:
        print(f"⚠️  Langfuse initialization failed: {e}")
        _langfuse_client = None
        return None

def create_trace(name: str, input_data: Optional[Dict[str, Any]] = None):
    """Create a new Langfuse trace."""
    client = get_langfuse_client()
    if not client:
        return None
    
    try:
        return client.trace(
            name=name,
            input=input_data or {},
            timestamp=time.time()
        )
    except Exception as e:
        print(f"⚠️  Failed to create Langfuse trace: {e}")
        return None

@contextmanager
def trace_with_langfuse(name: str, input_data: Optional[Dict[str, Any]] = None, **span_kwargs):
    """Context manager for Langfuse tracing."""
    trace = create_trace(name, input_data)
    
    if not trace:
        yield None
        return
    
    span = None
    try:
        span = trace.span(
            name=name,
            input=input_data or {},
            **span_kwargs
        )
        yield {"trace": trace, "span": span}
    except Exception as e:
        print(f"⚠️  Langfuse span error: {e}")
        yield None
    finally:
        if span:
            try:
                span.end()
            except Exception:
                pass
        if trace:
            try:
                trace.update()
            except Exception:
                pass

def log_llm_call(trace, model: str, input_text: str, output_text: str, usage: Optional[Dict] = None):
    """Log an LLM call to Langfuse."""
    if not trace:
        return
    
    try:
        trace.generation(
            name="llm_generation",
            model=model,
            input={"messages": [{"role": "user", "content": input_text}]},
            output={"content": output_text},
            usage=usage or {}
        )
    except Exception as e:
        print(f"⚠️  Failed to log LLM call: {e}")

def log_retrieval(trace, query: str, results: list, retriever_type: str):
    """Log retrieval operation to Langfuse."""
    if not trace:
        return
    
    try:
        trace.span(
            name="retrieval",
            input={"query": query, "retriever": retriever_type},
            output={
                "results_count": len(results),
                "results": [{"text": r.get("text", "")[:100] + "..." for r in results[:3]}]
            }
        )
    except Exception as e:
        print(f"⚠️  Failed to log retrieval: {e}")