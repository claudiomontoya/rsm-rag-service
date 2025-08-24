from __future__ import annotations
import asyncio
import time
import random
from typing import Any, Callable, TypeVar, Optional, Union
from functools import wraps
import httpx
from app.obs.logging_setup import get_logger
from app.config import MAX_RETRIES

logger = get_logger(__name__)
T = TypeVar('T')

class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = MAX_RETRIES,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on_exceptions: tuple = (httpx.HTTPError, httpx.TimeoutException, ConnectionError)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on_exceptions = retry_on_exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add up to 20% jitter
            jitter_amount = delay * 0.2 * random.random()
            delay += jitter_amount
        
        return delay

def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None
):
    """
    Decorator for retry with exponential backoff.
    
    Args:
        config: RetryConfig instance, uses default if None
        operation_name: Name for logging, uses function name if None
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation_name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    if attempt > 0:
                        delay = config.calculate_delay(attempt - 1)
                        logger.info(f"Retrying {op_name}", 
                                   attempt=attempt,
                                   delay_seconds=round(delay, 2))
                        await asyncio.sleep(delay)
                    
                    result = await func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"Retry successful for {op_name}", 
                                   attempt=attempt,
                                   total_attempts=attempt + 1)
                    
                    return result
                    
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {op_name}", 
                                     error=str(e),
                                     will_retry=True)
                    else:
                        logger.error(f"All {config.max_retries + 1} attempts failed for {op_name}", 
                                   error=str(e))
                except Exception as e:
                    # Don't retry on unexpected exceptions
                    logger.error(f"Non-retryable error in {op_name}", 
                               error=str(e))
                    raise
            
            # If we get here, all retries failed
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    if attempt > 0:
                        delay = config.calculate_delay(attempt - 1)
                        logger.info(f"Retrying {op_name}", 
                                   attempt=attempt,
                                   delay_seconds=round(delay, 2))
                        time.sleep(delay)
                    
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"Retry successful for {op_name}", 
                                   attempt=attempt,
                                   total_attempts=attempt + 1)
                    
                    return result
                    
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {op_name}", 
                                     error=str(e),
                                     will_retry=True)
                    else:
                        logger.error(f"All {config.max_retries + 1} attempts failed for {op_name}", 
                                   error=str(e))
                except Exception as e:
                    # Don't retry on unexpected exceptions
                    logger.error(f"Non-retryable error in {op_name}", 
                               error=str(e))
                    raise
            
            # If we get here, all retries failed
            raise last_exception
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Predefined retry configurations
DEFAULT_HTTP_RETRY = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    retry_on_exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError)
)

AGGRESSIVE_HTTP_RETRY = RetryConfig(
    max_retries=5,
    base_delay=0.5,
    max_delay=60.0,
    retry_on_exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError)
)

MODEL_LOADING_RETRY = RetryConfig(
    max_retries=2,
    base_delay=2.0,
    max_delay=120.0,
    retry_on_exceptions=(ImportError, OSError, ConnectionError)
)

# Convenience functions
async def retry_async_operation(
    operation: Callable[[], T],
    config: Optional[RetryConfig] = None,
    operation_name: str = "async_operation"
) -> T:
    """Retry an async operation with backoff."""
    
    @retry_with_backoff(config, operation_name)
    async def wrapper():
        return await operation()
    
    return await wrapper()

def retry_sync_operation(
    operation: Callable[[], T],
    config: Optional[RetryConfig] = None,
    operation_name: str = "sync_operation"
) -> T:
    """Retry a sync operation with backoff."""
    
    @retry_with_backoff(config, operation_name)
    def wrapper():
        return operation()
    
    return wrapper()