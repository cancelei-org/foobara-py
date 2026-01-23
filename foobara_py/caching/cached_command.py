"""
Cached command wrapper for Foobara Python.

Provides result caching for commands to avoid redundant computation.
"""

import hashlib
import json
from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar

from foobara_py.caching.cache_backends import CacheBackend, get_default_cache

T = TypeVar("T")


def generate_cache_key(command_class: Type, inputs_dict: dict) -> str:
    """
    Generate cache key from command class and raw inputs.

    Creates a hash from command class name and input data.

    Args:
        command_class: Command class
        inputs_dict: Raw input dictionary

    Returns:
        Cache key string (MD5 hash)
    """
    command_name = command_class.__name__

    # Serialize inputs to JSON for hashing
    inputs_json = json.dumps(inputs_dict, sort_keys=True)

    # Create hash
    data = f"{command_name}:{inputs_json}"
    return hashlib.md5(data.encode()).hexdigest()


def cached(
    ttl: Optional[int] = None,
    cache: Optional[CacheBackend] = None,
    key_func: Optional[Callable[[Any], str]] = None,
    cache_failures: bool = False,
) -> Callable:
    """
    Decorator to cache command results.

    Caches successful command results to avoid redundant computation.
    By default, only successful outcomes are cached.

    Args:
        ttl: Time-to-live in seconds (None = no expiration)
        cache: Cache backend to use (uses default if None)
        key_func: Custom function to generate cache key (uses generate_cache_key if None)
        cache_failures: Whether to cache failure outcomes (default: False)

    Returns:
        Decorator function

    Usage:
        from foobara_py import Command, cached

        @cached(ttl=300)  # Cache for 5 minutes
        class FetchUserProfile(Command[FetchUserInputs, UserProfile]):
            def execute(self) -> UserProfile:
                # Expensive operation
                return fetch_from_api(self.inputs.user_id)

        # First call - executes command
        outcome1 = FetchUserProfile.run(user_id=1)

        # Second call with same inputs - returns cached result
        outcome2 = FetchUserProfile.run(user_id=1)
    """

    # Get cache backend
    cache_backend = cache or get_default_cache()

    # Get key generation function
    key_generator = key_func or generate_cache_key

    def decorator(command_class: Type) -> Type:
        """Decorator that wraps the command class"""

        # Store original run method
        original_run = command_class.run

        @wraps(original_run)
        def cached_run(cls, **inputs):
            """Wrapped run method with caching"""
            # Generate cache key from raw inputs
            if key_func:
                # Custom key function receives command class and inputs
                cache_key = key_func(cls, inputs)
            else:
                cache_key = key_generator(cls, inputs)

            # Check cache
            cached_result = cache_backend.get(cache_key)
            if cached_result is not None:
                # Return cached outcome
                from foobara_py.core.outcome import CommandOutcome, Success

                # If the cached result is already an outcome (e.g., cached failure), return it directly
                if isinstance(cached_result, CommandOutcome):
                    return cached_result
                return Success(result=cached_result)

            # Run command
            outcome = original_run(**inputs)

            # Cache result if successful (or if caching failures)
            if outcome.is_success():
                cache_backend.set(cache_key, outcome.result, ttl)
            elif cache_failures:
                # Cache the entire outcome for failures
                cache_backend.set(cache_key, outcome, ttl)

            return outcome

        # Replace run method
        command_class.run = classmethod(cached_run)

        # Add cache management methods
        command_class._cache = cache_backend

        @classmethod
        def clear_cache(cls):
            """Clear all cached results for this command"""
            # Note: This clears entire cache, not just this command's entries
            # For more granular control, use a namespaced cache backend
            cache_backend.clear()

        command_class.clear_cache = clear_cache

        return command_class

    return decorator


def cache_key(*fields: str) -> Callable:
    """
    Create a custom cache key generator based on specific input fields.

    Args:
        *fields: Field names to include in cache key

    Returns:
        Key generator function

    Usage:
        @cached(key_func=cache_key('user_id', 'date'))
        class FetchUserActivity(Command):
            ...
    """

    def key_generator(command_class: Type, inputs_dict: dict) -> str:
        """Generate cache key from specific fields"""
        command_name = command_class.__name__

        # Extract specified fields
        values = {}
        for field in fields:
            if field in inputs_dict:
                values[field] = inputs_dict[field]

        # Create hash
        values_json = json.dumps(values, sort_keys=True)
        data = f"{command_name}:{values_json}"
        return hashlib.md5(data.encode()).hexdigest()

    return key_generator


class CacheStats:
    """
    Track cache statistics for monitoring.

    Usage:
        stats = CacheStats()

        @cached(ttl=60)
        class MyCommand(Command):
            ...

        # Access stats
        print(f"Hits: {stats.hits}, Misses: {stats.misses}")
        print(f"Hit rate: {stats.hit_rate():.2%}")
    """

    def __init__(self):
        """Initialize cache stats"""
        self.hits: int = 0
        self.misses: int = 0
        self.sets: int = 0

    def record_hit(self) -> None:
        """Record cache hit"""
        self.hits += 1

    def record_miss(self) -> None:
        """Record cache miss"""
        self.misses += 1

    def record_set(self) -> None:
        """Record cache set"""
        self.sets += 1

    def hit_rate(self) -> float:
        """
        Calculate cache hit rate.

        Returns:
            Hit rate as float (0.0 to 1.0)
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def reset(self) -> None:
        """Reset all stats"""
        self.hits = 0
        self.misses = 0
        self.sets = 0

    def __repr__(self) -> str:
        """String representation"""
        return f"CacheStats(hits={self.hits}, misses={self.misses}, sets={self.sets}, hit_rate={self.hit_rate():.2%})"
