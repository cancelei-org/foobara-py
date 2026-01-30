# Async Commands Guide

## Table of Contents

- [Introduction](#introduction)
- [When to Use Async Commands](#when-to-use-async-commands)
- [Python-Specific Advantage](#python-specific-advantage)
- [Basic Usage](#basic-usage)
- [Error Handling](#error-handling)
- [Lifecycle Hooks](#lifecycle-hooks)
- [Testing Async Commands](#testing-async-commands)
- [Performance Tips](#performance-tips)
- [Common Patterns](#common-patterns)
- [Comparison with Sync Commands](#comparison-with-sync-commands)

## Introduction

AsyncCommand is a Python-specific enhancement to the Foobara command framework that enables efficient handling of I/O-bound operations using Python's native `async`/`await` syntax. Unlike the Ruby implementation, Python's async capabilities allow for truly concurrent I/O operations without blocking threads.

### What are Async Commands?

Async commands are command objects that use asynchronous execution for their business logic. They inherit from `AsyncCommand` instead of `Command` and use `async def execute()` instead of `def execute()`.

```python
from foobara_py import AsyncCommand
from pydantic import BaseModel

class MyInputs(BaseModel):
    value: str

class MyAsyncCommand(AsyncCommand[MyInputs, str]):
    async def execute(self) -> str:
        # Async operations here
        return self.inputs.value
```

## When to Use Async Commands

Use `AsyncCommand` when your command needs to perform:

- **Network I/O**: HTTP requests, API calls, websocket communication
- **Database queries**: Using async ORMs (SQLAlchemy async, Tortoise ORM, etc.)
- **File operations**: Large file reads/writes with aiofiles
- **External service calls**: Cloud services, message queues, etc.
- **Concurrent operations**: Multiple I/O operations that can run in parallel

**Don't use async for:**
- CPU-intensive computations (use regular `Command` with multiprocessing)
- Simple in-memory operations
- Commands that only perform synchronous operations

## Python-Specific Advantage

Unlike Ruby (which uses threads or fibers for concurrency), Python's `asyncio` provides:

1. **True Concurrency for I/O**: Efficiently handle thousands of concurrent I/O operations
2. **Lower Memory Overhead**: Event loop is more efficient than thread pools
3. **Better Control**: Explicit async/await makes concurrency boundaries clear
4. **Native Ecosystem**: Rich ecosystem of async libraries (aiohttp, httpx, asyncpg, etc.)

This makes Python's async commands significantly more efficient for I/O-bound workloads than Ruby's equivalent approaches.

## Basic Usage

### Simple Async Command

```python
from foobara_py import AsyncCommand
from pydantic import BaseModel
import httpx

class FetchUserInputs(BaseModel):
    user_id: int

class UserData(BaseModel):
    id: int
    name: str
    email: str

class FetchUserData(AsyncCommand[FetchUserInputs, UserData]):
    """Fetch user data from external API"""

    async def execute(self) -> UserData:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.example.com/users/{self.inputs.user_id}"
            )
            response.raise_for_status()
            data = response.json()
            return UserData(**data)

# Usage
import asyncio

async def main():
    outcome = await FetchUserData.run(user_id=123)
    if outcome.is_success():
        user = outcome.unwrap()
        print(f"User: {user.name}")
    else:
        print(f"Errors: {outcome.errors}")

asyncio.run(main())
```

### Using the Decorator

```python
from foobara_py import async_command, AsyncCommand
from pydantic import BaseModel

@async_command(domain="Users", organization="MyApp")
class FetchUser(AsyncCommand[FetchUserInputs, UserData]):
    """Fetch user with domain configuration"""

    async def execute(self) -> UserData:
        # Implementation
        pass
```

### Simple Function-Based Commands

For simple async functions, use the `@async_simple_command` decorator:

```python
from foobara_py import async_simple_command
import httpx

@async_simple_command
async def fetch_github_user(username: str) -> dict:
    """Fetch GitHub user data"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.github.com/users/{username}")
        return response.json()

# Usage
outcome = await fetch_github_user.run(username="octocat")
user_data = outcome.unwrap()
```

## Error Handling

### Adding Errors in Async Commands

Async commands support the same error handling as sync commands:

```python
class FetchUserData(AsyncCommand[FetchUserInputs, UserData]):
    async def execute(self) -> UserData:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.example.com/users/{self.inputs.user_id}"
                )

                if response.status_code == 404:
                    self.add_runtime_error(
                        "user_not_found",
                        f"User {self.inputs.user_id} not found",
                        halt=True
                    )

                response.raise_for_status()
                data = response.json()
                return UserData(**data)

        except httpx.RequestError as e:
            self.add_runtime_error(
                "network_error",
                f"Failed to fetch user: {str(e)}",
                halt=True
            )
```

### Exception Handling

Unhandled exceptions are automatically caught and converted to errors:

```python
class FetchData(AsyncCommand[FetchInputs, dict]):
    async def execute(self) -> dict:
        # If this raises an exception, it becomes an execution_error
        async with httpx.AsyncClient() as client:
            response = await client.get(self.inputs.url)
            return response.json()

# If network fails, outcome will contain execution_error
outcome = await FetchData.run(url="https://invalid.url")
assert outcome.is_failure()
assert outcome.errors[0].symbol == "execution_error"
```

## Lifecycle Hooks

Async commands support async lifecycle hooks:

### before_execute Hook

```python
class AuthenticatedFetch(AsyncCommand[FetchInputs, dict]):
    async def before_execute(self) -> None:
        """Validate authentication before executing"""
        if not self.inputs.api_key:
            self.add_runtime_error(
                "missing_auth",
                "API key is required",
                halt=True
            )

    async def execute(self) -> dict:
        # Execute only if before_execute passes
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.inputs.url,
                headers={"Authorization": f"Bearer {self.inputs.api_key}"}
            )
            return response.json()
```

### after_execute Hook

```python
class FetchAndCache(AsyncCommand[FetchInputs, dict]):
    async def execute(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.inputs.url)
            return response.json()

    async def after_execute(self, result: dict) -> dict:
        """Cache the result after successful execution"""
        import aioredis
        redis = await aioredis.create_redis_pool('redis://localhost')

        cache_key = f"fetch:{self.inputs.url}"
        await redis.setex(cache_key, 3600, str(result))

        redis.close()
        await redis.wait_closed()

        return result
```

## Testing Async Commands

### Basic Testing with pytest

Use `pytest-asyncio` for testing async commands:

```python
import pytest
from foobara_py import AsyncCommand
from pydantic import BaseModel

class AddInputs(BaseModel):
    a: int
    b: int

class Add(AsyncCommand[AddInputs, int]):
    async def execute(self) -> int:
        return self.inputs.a + self.inputs.b

@pytest.mark.asyncio
async def test_add_success():
    outcome = await Add.run(a=5, b=3)
    assert outcome.is_success()
    assert outcome.unwrap() == 8

@pytest.mark.asyncio
async def test_add_validation_error():
    outcome = await Add.run(a="not_a_number", b=3)
    assert outcome.is_failure()
    assert len(outcome.errors) > 0
```

### Mocking Async Dependencies

```python
import pytest
from unittest.mock import AsyncMock, patch
import httpx

@pytest.mark.asyncio
async def test_fetch_user_with_mock():
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com"
    }
    mock_response.status_code = 200
    mock_response.raise_for_status = AsyncMock()

    with patch('httpx.AsyncClient.get', return_value=mock_response):
        outcome = await FetchUserData.run(user_id=1)
        assert outcome.is_success()
        user = outcome.unwrap()
        assert user.name == "Test User"
```

### Testing Error Cases

```python
@pytest.mark.asyncio
async def test_fetch_user_not_found():
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        outcome = await FetchUserData.run(user_id=999)
        assert outcome.is_failure()
        assert any(e.symbol == "user_not_found" for e in outcome.errors)
```

### Testing Concurrency

```python
@pytest.mark.asyncio
async def test_concurrent_execution():
    """Test that multiple async commands can run concurrently"""
    import asyncio

    tasks = [
        Add.run(a=1, b=1),
        Add.run(a=2, b=2),
        Add.run(a=3, b=3),
    ]

    outcomes = await asyncio.gather(*tasks)

    assert all(o.is_success() for o in outcomes)
    results = [o.unwrap() for o in outcomes]
    assert results == [2, 4, 6]
```

## Performance Tips

### 1. Connection Pooling

Reuse HTTP clients across multiple requests:

```python
class FetchMultipleUsers(AsyncCommand[UserIdsInputs, list[UserData]]):
    async def execute(self) -> list[UserData]:
        # Single client for all requests
        async with httpx.AsyncClient() as client:
            users = []
            for user_id in self.inputs.user_ids:
                response = await client.get(f"/users/{user_id}")
                users.append(UserData(**response.json()))
            return users
```

### 2. Concurrent Requests

Use `asyncio.gather` for parallel operations:

```python
class FetchMultipleUsersConcurrent(AsyncCommand[UserIdsInputs, list[UserData]]):
    async def execute(self) -> list[UserData]:
        async with httpx.AsyncClient() as client:
            async def fetch_user(user_id: int) -> UserData:
                response = await client.get(f"/users/{user_id}")
                return UserData(**response.json())

            # Fetch all users concurrently
            users = await asyncio.gather(*[
                fetch_user(uid) for uid in self.inputs.user_ids
            ])
            return list(users)
```

### 3. Timeout Handling

Always set timeouts for external operations:

```python
class FetchWithTimeout(AsyncCommand[FetchInputs, dict]):
    async def execute(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.inputs.url)
                return response.json()
        except httpx.TimeoutException:
            self.add_runtime_error(
                "request_timeout",
                "Request took too long",
                halt=True
            )
```

### 4. Rate Limiting

Implement rate limiting for API calls:

```python
import asyncio
from asyncio import Semaphore

class RateLimitedFetch(AsyncCommand[BatchFetchInputs, list[dict]]):
    async def execute(self) -> list[dict]:
        # Limit to 5 concurrent requests
        semaphore = Semaphore(5)

        async def fetch_with_limit(url: str) -> dict:
            async with semaphore:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    return response.json()

        results = await asyncio.gather(*[
            fetch_with_limit(url) for url in self.inputs.urls
        ])
        return list(results)
```

### 5. Avoid Blocking Calls

Never use blocking I/O in async commands:

```python
# BAD - blocks the event loop
class BadAsyncCommand(AsyncCommand[Inputs, str]):
    async def execute(self) -> str:
        import time
        time.sleep(1)  # Blocks entire event loop!
        return "done"

# GOOD - use asyncio.sleep
class GoodAsyncCommand(AsyncCommand[Inputs, str]):
    async def execute(self) -> str:
        await asyncio.sleep(1)  # Yields control
        return "done"

# GOOD - run blocking code in executor
class GoodBlockingCommand(AsyncCommand[Inputs, str]):
    async def execute(self) -> str:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, blocking_function)
        return result
```

## Common Patterns

### 1. Batch Processing with asyncio.gather

Process multiple items concurrently:

```python
from typing import List
import asyncio

class ProcessBatchInputs(BaseModel):
    item_ids: List[int]

class ProcessBatch(AsyncCommand[ProcessBatchInputs, List[dict]]):
    async def execute(self) -> List[dict]:
        async def process_item(item_id: int) -> dict:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"/process/{item_id}",
                    json={"action": "process"}
                )
                return response.json()

        # Process all items concurrently
        results = await asyncio.gather(*[
            process_item(item_id) for item_id in self.inputs.item_ids
        ])

        return list(results)
```

### 2. Retry Logic with Exponential Backoff

```python
import asyncio

class FetchWithRetry(AsyncCommand[FetchInputs, dict]):
    async def execute(self) -> dict:
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.inputs.url)
                    response.raise_for_status()
                    return response.json()
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    self.add_runtime_error(
                        "fetch_failed",
                        f"Failed after {max_retries} attempts: {str(e)}",
                        halt=True
                    )

                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
```

### 3. Streaming Large Results

```python
from typing import AsyncIterator

class StreamLargeDataset(AsyncCommand[QueryInputs, List[dict]]):
    async def execute(self) -> List[dict]:
        results = []

        async with httpx.AsyncClient() as client:
            async with client.stream('GET', self.inputs.url) as response:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    # Process chunk
                    results.extend(self.process_chunk(chunk))

        return results

    def process_chunk(self, chunk: bytes) -> List[dict]:
        # Process binary chunk
        return []
```

### 4. Parallel Command Execution

```python
class AggregateDataInputs(BaseModel):
    user_id: int

class AggregateUserData(AsyncCommand[AggregateDataInputs, dict]):
    async def execute(self) -> dict:
        # Run multiple async commands in parallel
        profile_task = FetchUserProfile.run(user_id=self.inputs.user_id)
        posts_task = FetchUserPosts.run(user_id=self.inputs.user_id)
        friends_task = FetchUserFriends.run(user_id=self.inputs.user_id)

        profile_outcome, posts_outcome, friends_outcome = await asyncio.gather(
            profile_task, posts_task, friends_task
        )

        # Check for errors
        if profile_outcome.is_failure():
            self.add_error(profile_outcome.errors[0])
            return None

        return {
            "profile": profile_outcome.unwrap(),
            "posts": posts_outcome.unwrap() if posts_outcome.is_success() else [],
            "friends": friends_outcome.unwrap() if friends_outcome.is_success() else []
        }
```

### 5. Timeout with Cancellation

```python
class FetchWithCancellation(AsyncCommand[FetchInputs, dict]):
    async def execute(self) -> dict:
        try:
            async with asyncio.timeout(5.0):  # Python 3.11+
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.inputs.url)
                    return response.json()
        except asyncio.TimeoutError:
            self.add_runtime_error(
                "timeout",
                "Request exceeded 5 second timeout",
                halt=True
            )
```

### 6. WebSocket Communication

```python
import websockets

class WebSocketCommandInputs(BaseModel):
    ws_url: str
    message: str

class SendWebSocketMessage(AsyncCommand[WebSocketCommandInputs, dict]):
    async def execute(self) -> dict:
        try:
            async with websockets.connect(self.inputs.ws_url) as websocket:
                await websocket.send(self.inputs.message)
                response = await websocket.recv()
                return {"response": response}
        except Exception as e:
            self.add_runtime_error(
                "websocket_error",
                f"WebSocket error: {str(e)}",
                halt=True
            )
```

## Comparison with Sync Commands

### Feature Parity

| Feature | Sync Command | Async Command |
|---------|-------------|---------------|
| Input validation | Yes | Yes |
| Error handling | Yes | Yes |
| Lifecycle hooks | Yes | Yes (async) |
| Domain dependencies | Yes | No (simplified) |
| Transactions | Yes | No (by default) |
| Entity loading | Yes | No (manual) |
| Subcommands | Yes | No (not yet) |

### When to Use Each

**Use Sync Command (`Command`) when:**
- CPU-intensive operations
- Synchronous database operations
- Need transaction support
- Need entity loading
- Need subcommand execution

**Use Async Command (`AsyncCommand`) when:**
- I/O-bound operations (network, files)
- Need concurrent execution
- Using async libraries (aiohttp, httpx, asyncpg)
- High-throughput API endpoints
- Real-time data processing

### Migration Guide

Converting a sync command to async:

```python
# Before (Sync)
class FetchUser(Command[FetchUserInputs, UserData]):
    def execute(self) -> UserData:
        import requests
        response = requests.get(f"/users/{self.inputs.user_id}")
        return UserData(**response.json())

# After (Async)
class FetchUser(AsyncCommand[FetchUserInputs, UserData]):
    async def execute(self) -> UserData:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"/users/{self.inputs.user_id}")
            return UserData(**response.json())
```

## Best Practices

1. **Always use async libraries** - Don't use blocking I/O in async commands
2. **Set timeouts** - Prevent hanging operations
3. **Handle errors explicitly** - Don't let exceptions propagate uncaught
4. **Use connection pools** - Reuse connections for better performance
5. **Limit concurrency** - Use semaphores to prevent overwhelming resources
6. **Test concurrency** - Ensure commands work correctly when run in parallel
7. **Monitor performance** - Track async command execution times
8. **Document async dependencies** - Make it clear what libraries are needed

## Examples

For complete working examples, see:

- `examples/async_commands/fetch_api_data.py` - Basic API fetching with error handling
- `examples/async_commands/batch_processing.py` - Concurrent batch processing
- `examples/async_commands/concurrent_commands.py` - Running multiple commands in parallel

## Further Reading

- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [HTTPX async client](https://www.python-httpx.org/async/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Async SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
