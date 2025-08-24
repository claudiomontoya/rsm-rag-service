from __future__ import annotations
import time
import functools
from typing import Callable, Any, Dict, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from app.obs.metrics import record_duration, inc_counter
from app.obs.langfuse import trace_with_langfuse
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

def traced(
    operation_name: Optional[str] = None,
    include_args: bool = False,
    include_result: bool = False,
    langfuse_trace: bool = False
):
    """Decorator to add OpenTelemetry tracing to functions."""
    
    def decorator(func: Callable) -> Callable:
        tracer = trace.get_tracer(__name__)
        span_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add arguments if requested
                if include_args:
                    try:
                        span.set_attribute("function.args", str(args))
                        span.set_attribute("function.kwargs", str(kwargs))
                    except Exception:
                        pass  # Skip if args are not serializable
                
                # Start timing
                start_time = time.time()
                
                try:
                    # Execute function
                    if langfuse_trace:
                        with trace_with_langfuse(span_name, {"args": str(args)}) as lf_ctx:
                            result = await func(*args, **kwargs)
                    else:
                        result = await func(*args, **kwargs)
                    
                    # Record success
                    span.set_status(Status(StatusCode.OK))
                    
                    # Add result if requested
                    if include_result:
                        try:
                            span.set_attribute("function.result", str(result)[:500])
                        except Exception:
                            pass
                    
                    return result
                    
                except Exception as e:
                    # Record error
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    
                    # Log error
                    logger.error(
                        f"Function {func.__name__} failed",
                        error=str(e),
                        function=func.__name__
                    )
                    
                    raise
                    
                finally:
                    # Record metrics
                    duration_ms = (time.time() - start_time) * 1000
                    record_duration(
                        "function_duration_ms",
                        duration_ms,
                        {"function": func.__name__, "module": func.__module__}
                    )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add arguments if requested
                if include_args:
                    try:
                        span.set_attribute("function.args", str(args))
                        span.set_attribute("function.kwargs", str(kwargs))
                    except Exception:
                        pass
                
                start_time = time.time()
                
                try:
                    # Execute function
                    if langfuse_trace:
                        with trace_with_langfuse(span_name, {"args": str(args)}) as lf_ctx:
                            result = func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    span.set_status(Status(StatusCode.OK))
                    
                    if include_result:
                        try:
                            span.set_attribute("function.result", str(result)[:500])
                        except Exception:
                            pass
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    
                    logger.error(
                        f"Function {func.__name__} failed",
                        error=str(e),
                        function=func.__name__
                    )
                    
                    raise
                    
                finally:
                    duration_ms = (time.time() - start_time) * 1000
                    record_duration(
                        "function_duration_ms",
                        duration_ms,
                        {"function": func.__name__, "module": func.__module__}
                    )
        
        # Return appropriate wrapper based on function type
        if functools.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def timed(metric_name: Optional[str] = None, labels: Optional[Dict[str, str]] = None):
    """Decorator to time function execution and record metrics."""
    
    def decorator(func: Callable) -> Callable:
        name = metric_name or f"{func.__name__}_duration_ms"
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration_ms = (time.time() - start_time) * 1000
                record_duration(name, duration_ms, labels)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.time() - start_time) * 1000
                record_duration(name, duration_ms, labels)
        
        return async_wrapper if functools.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def monitor_errors(metric_name: str = "function_errors_total"):
    """Decorator to monitor function errors."""
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                inc_counter(metric_name, {
                    "function": func.__name__,
                    "error_type": type(e).__name__
                })
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                inc_counter(metric_name, {
                    "function": func.__name__,
                    "error_type": type(e).__name__
                })
                raise
        
        return async_wrapper if functools.iscoroutinefunction(func) else sync_wrapper
    
    return decorator