from __future__ import annotations
import hashlib
import json
import os
import time
from typing import Dict, Any, Optional
from cachetools import TTLCache
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

class QueryCache:
    """LRU cache with TTL for query results."""
    
    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.hit_count = 0
        self.miss_count = 0
    
    def _create_key(self, question: str, retriever_type: str, top_k: int) -> str:
        """Create cache key from query parameters."""
        data = {"question": question.lower().strip(), "retriever": retriever_type, "top_k": top_k}
        key_data = json.dumps(data, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, question: str, retriever_type: str, top_k: int) -> Optional[Dict[str, Any]]:
        """Get cached query result."""
        key = self._create_key(question, retriever_type, top_k)
        
        if key in self.cache:
            self.hit_count += 1
            logger.debug(f"Cache HIT", key=key[:8])
            return self.cache[key]
        
        self.miss_count += 1
        logger.debug(f"Cache MISS", key=key[:8])
        return None
    
    def set(self, question: str, retriever_type: str, top_k: int, result: Dict[str, Any]) -> None:
        """Cache query result."""
        key = self._create_key(question, retriever_type, top_k)
        self.cache[key] = result
        logger.debug(f"Cached query result", key=key[:8])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        
        return {
            "size": len(self.cache),
            "maxsize": self.cache.maxsize,
            "hits": self.hit_count,
            "misses": self.miss_count,
            "hit_rate_percent": round(hit_rate, 2)
        }

# Global query cache
query_cache = QueryCache(
    maxsize=int(os.getenv("QUERY_CACHE_SIZE", "1000")),
    ttl=int(os.getenv("QUERY_CACHE_TTL", "300"))
)