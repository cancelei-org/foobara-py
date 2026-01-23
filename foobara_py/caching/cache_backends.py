"""
Cache backends for Foobara Python.

Provides pluggable cache implementations for command result caching.
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Optional


class CacheBackend(ABC):
    """
    Abstract cache backend interface.

    All cache backends must implement get, set, and delete methods.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = no expiration)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Delete value from cache.

        Args:
            key: Cache key
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values"""
        pass


class InMemoryCache(CacheBackend):
    """
    Simple in-memory cache implementation.

    Stores cached values in a dict with optional TTL support.
    Thread-safe for concurrent access.

    Usage:
        cache = InMemoryCache()
        cache.set("key", "value", ttl=60)
        value = cache.get("key")  # Returns "value"

        # After 60 seconds
        value = cache.get("key")  # Returns None
    """

    def __init__(self):
        """Initialize in-memory cache"""
        self._cache: dict[str, tuple[Any, Optional[float]]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]

            # Check if expired
            if expires_at is not None and time.time() > expires_at:
                del self._cache[key]
                return None

            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        with self._lock:
            expires_at = time.time() + ttl if ttl is not None else None
            self._cache[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """Delete value from cache"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get number of items in cache"""
        with self._lock:
            return len(self._cache)

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, (_, expires_at) in self._cache.items()
                if expires_at is not None and current_time > expires_at
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)


# Global default cache instance
_default_cache: Optional[CacheBackend] = None
_cache_lock = threading.Lock()


def get_default_cache() -> CacheBackend:
    """
    Get the default cache instance.

    Returns:
        Default cache backend (creates InMemoryCache if not set)
    """
    global _default_cache

    if _default_cache is None:
        with _cache_lock:
            if _default_cache is None:
                _default_cache = InMemoryCache()

    return _default_cache


def set_default_cache(cache: CacheBackend) -> None:
    """
    Set the default cache instance.

    Args:
        cache: Cache backend to use as default
    """
    global _default_cache

    with _cache_lock:
        _default_cache = cache
