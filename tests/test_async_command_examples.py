"""
Test async command examples from the documentation.

Ensures all code examples in ASYNC_COMMANDS.md actually work.
"""

import pytest
import asyncio
from pydantic import BaseModel
from foobara_py import AsyncCommand
from foobara_py.core.command import async_simple_command
from unittest.mock import AsyncMock, patch


class TestBasicAsyncCommand:
    """Test basic async command patterns"""

    @pytest.mark.asyncio
    async def test_simple_async_command(self):
        """Test basic async command structure"""
        class MyInputs(BaseModel):
            value: str

        class MyAsyncCommand(AsyncCommand[MyInputs, str]):
            async def execute(self) -> str:
                return self.inputs.value

        outcome = await MyAsyncCommand.run(value="test")
        assert outcome.is_success()
        assert outcome.unwrap() == "test"

    @pytest.mark.asyncio
    async def test_async_simple_command_decorator(self):
        """Test @async_simple_command decorator"""
        @async_simple_command
        async def double_value(value: int) -> int:
            await asyncio.sleep(0)  # Simulate async work
            return value * 2

        outcome = await double_value.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 10


class TestErrorHandling:
    """Test error handling patterns"""

    @pytest.mark.asyncio
    async def test_add_runtime_error(self):
        """Test adding runtime errors"""
        class MyInputs(BaseModel):
            value: int

        class ValidatePositive(AsyncCommand[MyInputs, int]):
            async def execute(self) -> int:
                if self.inputs.value < 0:
                    self.add_runtime_error(
                        "negative_value",
                        "Value must be positive",
                        halt=True
                    )
                return self.inputs.value

        # Test success case
        outcome = await ValidatePositive.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 5

        # Test error case
        outcome = await ValidatePositive.run(value=-1)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "negative_value"

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test automatic exception handling"""
        class FailInputs(BaseModel):
            should_fail: bool

        class FailCommand(AsyncCommand[FailInputs, str]):
            async def execute(self) -> str:
                if self.inputs.should_fail:
                    raise ValueError("Intentional failure")
                return "success"

        outcome = await FailCommand.run(should_fail=True)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "execution_error"


class TestLifecycleHooks:
    """Test lifecycle hooks"""

    @pytest.mark.asyncio
    async def test_before_execute_hook(self):
        """Test before_execute hook (using old method for async commands)"""
        execution_log = []

        class MyInputs(BaseModel):
            value: int

        class CommandWithHooks(AsyncCommand[MyInputs, int]):
            async def before_execute(self) -> None:
                execution_log.append("before")
                if self.inputs.value < 0:
                    self.add_runtime_error(
                        "invalid",
                        "Invalid value",
                        halt=True
                    )

            async def execute(self) -> int:
                execution_log.append("execute")
                return self.inputs.value

        # Test success path
        execution_log.clear()
        outcome = await CommandWithHooks.run(value=5)
        assert outcome.is_success()
        assert execution_log == ["before", "execute"]

        # Test before_execute error
        execution_log.clear()
        outcome = await CommandWithHooks.run(value=-1)
        assert outcome.is_failure()
        assert execution_log == ["before"]  # execute should not run

    @pytest.mark.asyncio
    async def test_after_execute_hook(self):
        """Test after_execute hook (using old method for async commands)"""
        class MyInputs(BaseModel):
            value: int

        class TransformResult(AsyncCommand[MyInputs, int]):
            async def execute(self) -> int:
                return self.inputs.value

            async def after_execute(self, result: int) -> int:
                # Double the result
                return result * 2

        outcome = await TransformResult.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 10  # Transformed by after_execute


class TestConcurrencyPatterns:
    """Test concurrency patterns"""

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Test running multiple commands concurrently"""
        class AddInputs(BaseModel):
            a: int
            b: int

        class Add(AsyncCommand[AddInputs, int]):
            async def execute(self) -> int:
                await asyncio.sleep(0.01)
                return self.inputs.a + self.inputs.b

        # Run multiple commands concurrently
        tasks = [
            Add.run(a=1, b=1),
            Add.run(a=2, b=2),
            Add.run(a=3, b=3),
        ]

        outcomes = await asyncio.gather(*tasks)

        assert all(o.is_success() for o in outcomes)
        results = [o.unwrap() for o in outcomes]
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_rate_limiting_with_semaphore(self):
        """Test rate limiting using semaphore"""
        execution_count = []

        class BatchInputs(BaseModel):
            items: list[int]
            max_concurrent: int

        class BatchProcess(AsyncCommand[BatchInputs, list[int]]):
            async def execute(self) -> list[int]:
                semaphore = asyncio.Semaphore(self.inputs.max_concurrent)

                async def process_item(item: int) -> int:
                    async with semaphore:
                        execution_count.append(item)
                        await asyncio.sleep(0.01)
                        return item * 2

                results = await asyncio.gather(*[
                    process_item(item) for item in self.inputs.items
                ])

                return list(results)

        execution_count.clear()
        outcome = await BatchProcess.run(
            items=[1, 2, 3, 4, 5],
            max_concurrent=2
        )

        assert outcome.is_success()
        results = outcome.unwrap()
        assert results == [2, 4, 6, 8, 10]


class TestRetryPatterns:
    """Test retry patterns"""

    @pytest.mark.asyncio
    async def test_retry_with_backoff(self):
        """Test retry logic with exponential backoff"""
        attempt_count = []

        class RetryInputs(BaseModel):
            fail_times: int

        class RetryCommand(AsyncCommand[RetryInputs, str]):
            async def execute(self) -> str:
                max_retries = 3
                base_delay = 0.01

                for attempt in range(max_retries):
                    attempt_count.append(attempt)

                    if len(attempt_count) <= self.inputs.fail_times:
                        if attempt == max_retries - 1:
                            self.add_runtime_error(
                                "max_retries",
                                "Failed after max retries",
                                halt=True
                            )
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue

                    return "success"

        # Test success after 2 retries
        attempt_count.clear()
        outcome = await RetryCommand.run(fail_times=2)
        assert outcome.is_success()
        assert len(attempt_count) == 3  # 0, 1, 2

        # Test failure after max retries
        attempt_count.clear()
        outcome = await RetryCommand.run(fail_times=5)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "max_retries"


class TestCompositionPatterns:
    """Test command composition patterns"""

    @pytest.mark.asyncio
    async def test_command_orchestration(self):
        """Test orchestrating multiple async commands"""
        class UserIdInputs(BaseModel):
            user_id: int

        class UserData(BaseModel):
            user_id: int
            name: str

        class PostData(BaseModel):
            count: int

        class AggregateInputs(BaseModel):
            user_id: int

        class AggregateResult(BaseModel):
            user: UserData
            posts: PostData

        class FetchUser(AsyncCommand[UserIdInputs, UserData]):
            async def execute(self) -> UserData:
                await asyncio.sleep(0.01)
                return UserData(user_id=self.inputs.user_id, name=f"User{self.inputs.user_id}")

        class FetchPosts(AsyncCommand[UserIdInputs, PostData]):
            async def execute(self) -> PostData:
                await asyncio.sleep(0.01)
                return PostData(count=self.inputs.user_id * 10)

        class AggregateData(AsyncCommand[AggregateInputs, AggregateResult]):
            async def execute(self) -> AggregateResult:
                # Run commands concurrently
                user_task = FetchUser.run(user_id=self.inputs.user_id)
                posts_task = FetchPosts.run(user_id=self.inputs.user_id)

                user_outcome, posts_outcome = await asyncio.gather(
                    user_task, posts_task
                )

                # Check for errors
                if user_outcome.is_failure():
                    self.add_runtime_error("user_fetch_failed", "Failed to fetch user", halt=True)

                return AggregateResult(
                    user=user_outcome.unwrap(),
                    posts=posts_outcome.unwrap() if posts_outcome.is_success() else PostData(count=0)
                )

        outcome = await AggregateData.run(user_id=5)
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.user.name == "User5"
        assert result.posts.count == 50


class TestTimeoutHandling:
    """Test timeout handling"""

    @pytest.mark.asyncio
    async def test_timeout_with_asyncio(self):
        """Test timeout handling with asyncio"""
        class SlowInputs(BaseModel):
            delay: float

        class SlowCommand(AsyncCommand[SlowInputs, str]):
            async def execute(self) -> str:
                try:
                    # Use asyncio.wait_for for Python 3.10+ compatibility
                    await asyncio.wait_for(
                        asyncio.sleep(self.inputs.delay),
                        timeout=0.1
                    )
                    return "completed"
                except asyncio.TimeoutError:
                    self.add_runtime_error(
                        "timeout",
                        "Operation timed out",
                        halt=True
                    )

        # Should succeed
        outcome = await SlowCommand.run(delay=0.01)
        assert outcome.is_success()

        # Should timeout
        outcome = await SlowCommand.run(delay=1.0)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "timeout"


class TestBatchProcessing:
    """Test batch processing patterns"""

    @pytest.mark.asyncio
    async def test_batch_with_gather(self):
        """Test batch processing with asyncio.gather"""
        class BatchInputs(BaseModel):
            items: list[int]

        class ProcessBatch(AsyncCommand[BatchInputs, list[int]]):
            async def execute(self) -> list[int]:
                async def process_item(item: int) -> int:
                    await asyncio.sleep(0.01)
                    return item * 2

                results = await asyncio.gather(*[
                    process_item(item) for item in self.inputs.items
                ])

                return list(results)

        outcome = await ProcessBatch.run(items=[1, 2, 3, 4, 5])
        assert outcome.is_success()
        assert outcome.unwrap() == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_batch_with_partial_failures(self):
        """Test batch processing with partial failures"""
        class ItemInputs(BaseModel):
            value: int

        class ProcessItem(AsyncCommand[ItemInputs, int]):
            async def execute(self) -> int:
                if self.inputs.value < 0:
                    self.add_runtime_error("negative", "Negative value", halt=True)
                return self.inputs.value * 2

        class BatchInputs(BaseModel):
            items: list[int]

        class ProcessBatchSafe(AsyncCommand[BatchInputs, dict]):
            async def execute(self) -> dict:
                async def process_safe(value: int) -> dict:
                    outcome = await ProcessItem.run(value=value)
                    if outcome.is_success():
                        return {"value": value, "result": outcome.unwrap(), "error": None}
                    else:
                        return {"value": value, "result": None, "error": outcome.errors[0].symbol}

                results = await asyncio.gather(*[
                    process_safe(item) for item in self.inputs.items
                ])

                return {
                    "results": results,
                    "successful": sum(1 for r in results if r["error"] is None),
                    "failed": sum(1 for r in results if r["error"] is not None)
                }

        outcome = await ProcessBatchSafe.run(items=[1, -2, 3, -4, 5])
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["successful"] == 3
        assert result["failed"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
