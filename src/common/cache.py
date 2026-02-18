"""Query cache for expensive aggregation queries"""
import hashlib
import json
import time
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from src.common.logging import get_logger

logger = get_logger(__name__)


class QueryCache:
    """
    In-memory LRU cache for database query results
    
    Cache Strategy:
    - TTL: 5 minutes for cost aggregation queries
    - Invalidation: On new data ingestion
    - Skip: Real-time queries, user-specific data
    """
    
    def __init__(self, maxsize: int = 128, ttl: int = 300):
        """
        Initialize query cache
        
        Args:
            maxsize: Maximum number of cached items
            ttl: Time-to-live in seconds (default: 5 minutes)
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
    
    def _generate_cache_key(self, query_params: Dict[str, Any]) -> str:
        """
        Generate cache key from query parameters
        
        Args:
            query_params: Query parameters dictionary
            
        Returns:
            MD5 hash of canonical query representation
        """
        # Create canonical representation
        canonical = json.dumps(query_params, sort_keys=True)
        cache_key = hashlib.md5(canonical.encode()).hexdigest()
        
        logger.debug(f"Generated cache key: {cache_key}", extra={"params": query_params})
        return cache_key
    
    def get(self, query_params: Dict[str, Any]) -> Optional[Any]:
        """
        Get cached query result
        
        Args:
            query_params: Query parameters
            
        Returns:
            Cached result or None if not found/expired
        """
        cache_key = self._generate_cache_key(query_params)
        
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            
            # Check if expired
            if time.time() - timestamp < self.ttl:
                self._hits += 1
                logger.debug(f"Cache HIT: {cache_key}")
                return result
            else:
                # Expired, remove
                del self._cache[cache_key]
                logger.debug(f"Cache EXPIRED: {cache_key}")
        
        self._misses += 1
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    
    def set(self, query_params: Dict[str, Any], result: Any):
        """
        Cache query result
        
        Args:
            query_params: Query parameters
            result: Query result to cache
        """
        cache_key = self._generate_cache_key(query_params)
        
        # Evict oldest if at max size
        if len(self._cache) >= self.maxsize:
            # Simple FIFO eviction
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Cache EVICTED: {oldest_key}")
        
        self._cache[cache_key] = (result, time.time())
        logger.debug(f"Cache SET: {cache_key}")
    
    def invalidate(self, pattern: Optional[str] = None):
        """
        Invalidate cache entries
        
        Args:
            pattern: Optional pattern to match keys (None = clear all)
        """
        if pattern is None:
            # Clear all
            self._cache.clear()
            logger.info("Cache cleared (all entries)")
        else:
            # Clear matching keys
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            logger.info(f"Cache cleared ({len(keys_to_delete)} entries matching '{pattern}')")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "cached_items": len(self._cache),
            "maxsize": self.maxsize,
            "ttl_seconds": self.ttl,
        }


# Global cache instance
_query_cache = QueryCache(maxsize=128, ttl=300)


def get_query_cache() -> QueryCache:
    """Get global query cache instance"""
    return _query_cache


def cache_query(func):
    """
    Decorator to cache query results
    
    Usage:
        @cache_query
        def expensive_query(params):
            # Query logic
            return result
    """
    def wrapper(*args, **kwargs):
        cache = get_query_cache()
        
        # Build cache key from args/kwargs
        cache_key_params = {
            "func": func.__name__,
            "args": args,
            "kwargs": kwargs,
        }
        
        # Try to get from cache
        cached_result = cache.get(cache_key_params)
        if cached_result is not None:
            return cached_result
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Cache result
        cache.set(cache_key_params, result)
        
        return result
    
    return wrapper
