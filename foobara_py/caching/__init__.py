"""
Caching system for Foobara Python.

Provides command result caching to avoid redundant computation.
"""

from foobara_py.caching.cache_backends import (
    CacheBackend,
    InMemoryCache,
    get_default_cache,
    set_default_cache,
)
from foobara_py.caching.cached_command import (
    CacheStats,
    cache_key,
    cached,
    generate_cache_key,
)

__all__ = [
    "CacheBackend",
    "InMemoryCache",
    "get_default_cache",
    "set_default_cache",
    "cached",
    "cache_key",
    "generate_cache_key",
    "CacheStats",
]
