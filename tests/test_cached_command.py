"""Tests for cached command wrapper"""

import pytest
import time
from pydantic import BaseModel
from foobara_py import Command
from foobara_py.caching import (
    InMemoryCache,
    cached,
    cache_key,
    get_default_cache,
    set_default_cache,
    CacheStats,
)


# Track executions
execution_count = 0


def reset_execution_count():
    """Reset execution counter"""
    global execution_count
    execution_count = 0


class TestInMemoryCache:
    """Test InMemoryCache backend"""

    def setup_method(self):
        """Setup cache"""
        self.cache = InMemoryCache()

    def test_set_and_get(self):
        """Should set and get values"""
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """Should return None for nonexistent keys"""
        assert self.cache.get("nonexistent") is None

    def test_delete(self):
        """Should delete values"""
        self.cache.set("key1", "value1")
        self.cache.delete("key1")
        assert self.cache.get("key1") is None

    def test_clear(self):
        """Should clear all values"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()

        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None

    def test_ttl_expiration(self):
        """Should expire values after TTL"""
        self.cache.set("key1", "value1", ttl=1)  # 1 second TTL

        # Should exist immediately
        assert self.cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert self.cache.get("key1") is None

    def test_ttl_none(self):
        """Should not expire when TTL is None"""
        self.cache.set("key1", "value1", ttl=None)

        time.sleep(0.1)

        assert self.cache.get("key1") == "value1"

    def test_size(self):
        """Should track cache size"""
        assert self.cache.size() == 0

        self.cache.set("key1", "value1")
        assert self.cache.size() == 1

        self.cache.set("key2", "value2")
        assert self.cache.size() == 2

        self.cache.delete("key1")
        assert self.cache.size() == 1

    def test_cleanup_expired(self):
        """Should cleanup expired entries"""
        self.cache.set("key1", "value1", ttl=1)
        self.cache.set("key2", "value2", ttl=10)
        self.cache.set("key3", "value3")  # No TTL

        time.sleep(1.1)

        removed = self.cache.cleanup_expired()

        assert removed == 1  # Only key1 expired
        assert self.cache.size() == 2


class TestCachedCommandBasic:
    """Test basic cached command functionality"""

    def setup_method(self):
        """Setup"""
        reset_execution_count()
        # Reset default cache
        set_default_cache(InMemoryCache())

    def test_basic_caching(self):
        """Should cache command results"""

        class FetchDataInputs(BaseModel):
            id: int

        @cached()
        class FetchData(Command[FetchDataInputs, str]):
            def execute(self) -> str:
                global execution_count
                execution_count += 1
                return f"data_{self.inputs.id}"

        # First call - should execute
        outcome1 = FetchData.run(id=1)
        assert outcome1.is_success()
        assert outcome1.result == "data_1"
        assert execution_count == 1

        # Second call with same inputs - should use cache
        outcome2 = FetchData.run(id=1)
        assert outcome2.is_success()
        assert outcome2.result == "data_1"
        assert execution_count == 1  # Not executed again

        # Different inputs - should execute
        outcome3 = FetchData.run(id=2)
        assert outcome3.is_success()
        assert outcome3.result == "data_2"
        assert execution_count == 2

    def test_ttl_caching(self):
        """Should respect TTL"""

        class FetchDataInputs(BaseModel):
            id: int

        @cached(ttl=1)  # 1 second TTL
        class FetchData(Command[FetchDataInputs, str]):
            def execute(self) -> str:
                global execution_count
                execution_count += 1
                return f"data_{self.inputs.id}"

        # First call
        outcome1 = FetchData.run(id=1)
        assert execution_count == 1

        # Immediate second call - cached
        outcome2 = FetchData.run(id=1)
        assert execution_count == 1

        # Wait for expiration
        time.sleep(1.1)

        # After expiration - executes again
        outcome3 = FetchData.run(id=1)
        assert execution_count == 2

    def test_custom_cache_backend(self):
        """Should use custom cache backend"""
        custom_cache = InMemoryCache()

        class FetchDataInputs(BaseModel):
            id: int

        @cached(cache=custom_cache)
        class FetchData(Command[FetchDataInputs, str]):
            def execute(self) -> str:
                return f"data_{self.inputs.id}"

        # Verify using custom cache
        assert FetchData._cache is custom_cache

        FetchData.run(id=1)

        # Check custom cache has the result
        assert custom_cache.size() == 1

    def test_clear_cache(self):
        """Should clear cached results"""

        class FetchDataInputs(BaseModel):
            id: int

        @cached()
        class FetchData(Command[FetchDataInputs, str]):
            def execute(self) -> str:
                global execution_count
                execution_count += 1
                return f"data_{self.inputs.id}"

        # Cache result
        FetchData.run(id=1)
        assert execution_count == 1

        # Verify cached
        FetchData.run(id=1)
        assert execution_count == 1

        # Clear cache
        FetchData.clear_cache()

        # Should execute again
        FetchData.run(id=1)
        assert execution_count == 2


class TestCustomCacheKey:
    """Test custom cache key generation"""

    def setup_method(self):
        """Setup"""
        reset_execution_count()
        set_default_cache(InMemoryCache())

    def test_cache_key_specific_fields(self):
        """Should cache based on specific fields only"""

        class FetchDataInputs(BaseModel):
            id: int
            include_details: bool = False

        @cached(key_func=cache_key('id'))
        class FetchData(Command[FetchDataInputs, str]):
            def execute(self) -> str:
                global execution_count
                execution_count += 1
                details = " (with details)" if self.inputs.include_details else ""
                return f"data_{self.inputs.id}{details}"

        # First call
        outcome1 = FetchData.run(id=1, include_details=False)
        assert outcome1.result == "data_1"
        assert execution_count == 1

        # Same id, different include_details - should use cache (only id is in key)
        outcome2 = FetchData.run(id=1, include_details=True)
        assert outcome2.result == "data_1"  # Cached result
        assert execution_count == 1  # Not executed

        # Different id - should execute
        outcome3 = FetchData.run(id=2, include_details=False)
        assert outcome3.result == "data_2"
        assert execution_count == 2


class TestCacheFailures:
    """Test caching failure outcomes"""

    def setup_method(self):
        """Setup"""
        reset_execution_count()
        set_default_cache(InMemoryCache())

    def test_dont_cache_failures_by_default(self):
        """Should not cache failures by default"""

        class FetchDataInputs(BaseModel):
            id: int

        @cached()
        class FetchData(Command[FetchDataInputs, str]):
            def execute(self) -> str:
                global execution_count
                execution_count += 1
                if self.inputs.id == 999:
                    raise ValueError("Invalid ID")
                return f"data_{self.inputs.id}"

        # First call with error
        outcome1 = FetchData.run(id=999)
        assert outcome1.is_failure()
        assert execution_count == 1

        # Second call - should execute again (not cached)
        outcome2 = FetchData.run(id=999)
        assert outcome2.is_failure()
        assert execution_count == 2

    def test_cache_failures_when_enabled(self):
        """Should cache failures when enabled"""

        class FetchDataInputs(BaseModel):
            id: int

        @cached(cache_failures=True, ttl=60)
        class FetchData(Command[FetchDataInputs, str]):
            def execute(self) -> str:
                global execution_count
                execution_count += 1
                if self.inputs.id == 999:
                    raise ValueError("Invalid ID")
                return f"data_{self.inputs.id}"

        # First call with error
        outcome1 = FetchData.run(id=999)
        assert outcome1.is_failure()
        assert execution_count == 1

        # Second call - should use cached failure
        outcome2 = FetchData.run(id=999)
        assert outcome2.is_failure()
        assert execution_count == 1  # Not executed again


class TestRealWorldScenarios:
    """Test real-world caching scenarios"""

    def setup_method(self):
        """Setup"""
        reset_execution_count()
        set_default_cache(InMemoryCache())

    def test_api_response_caching(self):
        """Should cache API responses"""

        class FetchUserInputs(BaseModel):
            user_id: int

        class UserProfile(BaseModel):
            id: int
            name: str
            email: str

        @cached(ttl=300)  # Cache for 5 minutes
        class FetchUserProfile(Command[FetchUserInputs, UserProfile]):
            def execute(self) -> UserProfile:
                global execution_count
                execution_count += 1
                # Simulate API call
                return UserProfile(
                    id=self.inputs.user_id,
                    name=f"User {self.inputs.user_id}",
                    email=f"user{self.inputs.user_id}@example.com"
                )

        # Multiple calls for same user - should only execute once
        for _ in range(5):
            outcome = FetchUserProfile.run(user_id=1)
            assert outcome.is_success()
            assert outcome.result.id == 1

        assert execution_count == 1  # Only executed once

    def test_expensive_computation_caching(self):
        """Should cache expensive computations"""

        class ComputeInputs(BaseModel):
            n: int

        @cached()
        class ComputeFibonacci(Command[ComputeInputs, int]):
            def execute(self) -> int:
                global execution_count
                execution_count += 1
                # Simulate expensive computation
                return self._fib(self.inputs.n)

            def _fib(self, n: int) -> int:
                if n <= 1:
                    return n
                return self._fib(n - 1) + self._fib(n - 2)

        # First call
        outcome1 = ComputeFibonacci.run(n=10)
        assert outcome1.result == 55
        first_count = execution_count

        # Second call - cached
        outcome2 = ComputeFibonacci.run(n=10)
        assert outcome2.result == 55
        assert execution_count == first_count  # Not executed again

    def test_multiple_cached_commands(self):
        """Should handle multiple cached commands independently"""

        class InputsA(BaseModel):
            id: int

        class InputsB(BaseModel):
            id: int

        @cached()
        class CommandA(Command[InputsA, str]):
            def execute(self) -> str:
                return f"A_{self.inputs.id}"

        @cached()
        class CommandB(Command[InputsB, str]):
            def execute(self) -> str:
                return f"B_{self.inputs.id}"

        # Run both commands with same input
        outcome_a = CommandA.run(id=1)
        outcome_b = CommandB.run(id=1)

        assert outcome_a.result == "A_1"
        assert outcome_b.result == "B_1"

        # Results should be cached independently
        outcome_a2 = CommandA.run(id=1)
        outcome_b2 = CommandB.run(id=1)

        assert outcome_a2.result == "A_1"
        assert outcome_b2.result == "B_1"
