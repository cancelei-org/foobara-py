#!/usr/bin/env python3
"""
Async Command Example: Batch Processing

Demonstrates concurrent batch processing using AsyncCommand with:
- Parallel processing with asyncio.gather
- Rate limiting with semaphores
- Progress tracking
- Error handling for partial failures
"""

import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
from foobara_py import AsyncCommand
import httpx
from datetime import datetime


# Input and result models
class ProcessItemInputs(BaseModel):
    item_id: int
    delay: float = Field(default=0.5, description="Simulated processing delay")


class ProcessedItem(BaseModel):
    item_id: int
    status: str
    processed_at: str
    result: Optional[dict] = None
    error: Optional[str] = None


class BatchProcessInputs(BaseModel):
    item_ids: List[int] = Field(..., min_length=1, max_length=100)
    max_concurrent: int = Field(default=5, ge=1, le=20, description="Max concurrent operations")


class BatchResult(BaseModel):
    total: int
    successful: int
    failed: int
    items: List[ProcessedItem]


# Simple item processor
class ProcessItem(AsyncCommand[ProcessItemInputs, ProcessedItem]):
    """Process a single item asynchronously"""

    async def execute(self) -> ProcessedItem:
        """
        Simulate processing a single item.

        In a real application, this might:
        - Call an external API
        - Process a file
        - Update a database record
        - Send an email
        """
        try:
            # Simulate async work
            await asyncio.sleep(self.inputs.delay)

            # Simulate occasional failures
            if self.inputs.item_id % 7 == 0:
                raise ValueError(f"Item {self.inputs.item_id} failed processing")

            return ProcessedItem(
                item_id=self.inputs.item_id,
                status="success",
                processed_at=datetime.now().isoformat(),
                result={"value": self.inputs.item_id * 2}
            )
        except Exception as e:
            return ProcessedItem(
                item_id=self.inputs.item_id,
                status="failed",
                processed_at=datetime.now().isoformat(),
                error=str(e)
            )


# Batch processor with concurrency control
class ProcessBatch(AsyncCommand[BatchProcessInputs, BatchResult]):
    """Process multiple items concurrently with rate limiting"""

    async def execute(self) -> BatchResult:
        """
        Process multiple items in parallel with concurrency control.

        Demonstrates:
        - asyncio.gather for parallel execution
        - Semaphore for rate limiting
        - Error handling for partial failures
        - Result aggregation
        """
        semaphore = asyncio.Semaphore(self.inputs.max_concurrent)

        async def process_with_limit(item_id: int) -> ProcessedItem:
            """Process item with semaphore-based rate limiting"""
            async with semaphore:
                print(f"Processing item {item_id}...")
                outcome = await ProcessItem.run(item_id=item_id, delay=0.2)

                if outcome.is_success():
                    return outcome.unwrap()
                else:
                    # Handle command failure
                    return ProcessedItem(
                        item_id=item_id,
                        status="failed",
                        processed_at=datetime.now().isoformat(),
                        error="Command execution failed"
                    )

        # Process all items concurrently (but limited by semaphore)
        results = await asyncio.gather(*[
            process_with_limit(item_id) for item_id in self.inputs.item_ids
        ])

        # Aggregate results
        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")

        return BatchResult(
            total=len(results),
            successful=successful,
            failed=failed,
            items=results
        )


# Advanced: Batch processor with progress tracking
class ProcessBatchWithProgress(AsyncCommand[BatchProcessInputs, BatchResult]):
    """Process batch with real-time progress tracking"""

    async def execute(self) -> BatchResult:
        """
        Process items with progress tracking.

        Demonstrates:
        - Progress reporting
        - asyncio.as_completed for streaming results
        - Early failure detection
        """
        semaphore = asyncio.Semaphore(self.inputs.max_concurrent)
        results: List[ProcessedItem] = []
        total_items = len(self.inputs.item_ids)

        async def process_with_limit(item_id: int, index: int) -> ProcessedItem:
            async with semaphore:
                outcome = await ProcessItem.run(item_id=item_id, delay=0.2)

                if outcome.is_success():
                    result = outcome.unwrap()
                else:
                    result = ProcessedItem(
                        item_id=item_id,
                        status="failed",
                        processed_at=datetime.now().isoformat(),
                        error="Command execution failed"
                    )

                # Progress tracking
                progress = ((index + 1) / total_items) * 100
                print(f"Progress: {progress:.1f}% ({index + 1}/{total_items}) - Item {item_id}: {result.status}")

                return result

        # Create tasks
        tasks = [
            process_with_limit(item_id, idx)
            for idx, item_id in enumerate(self.inputs.item_ids)
        ]

        # Process with progress tracking
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

        # Sort results by item_id for consistent output
        results.sort(key=lambda x: x.item_id)

        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")

        return BatchResult(
            total=len(results),
            successful=successful,
            failed=failed,
            items=results
        )


# Example: Fetch multiple GitHub users concurrently
class FetchUsersInputs(BaseModel):
    user_ids: List[int] = Field(..., min_length=1, max_length=50)


class GitHubUserSummary(BaseModel):
    user_id: int
    login: Optional[str] = None
    public_repos: Optional[int] = None
    error: Optional[str] = None


class FetchMultipleGitHubUsers(AsyncCommand[FetchUsersInputs, List[GitHubUserSummary]]):
    """Fetch multiple GitHub users concurrently"""

    async def execute(self) -> List[GitHubUserSummary]:
        """
        Fetch multiple users in parallel.

        Demonstrates:
        - Real-world batch API calls
        - Shared HTTP client
        - Graceful error handling
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            async def fetch_user(user_id: int) -> GitHubUserSummary:
                try:
                    response = await client.get(
                        f"https://api.github.com/user/{user_id}",
                        headers={
                            "Accept": "application/vnd.github.v3+json",
                            "User-Agent": "Foobara-Python-Example"
                        }
                    )

                    if response.status_code == 404:
                        return GitHubUserSummary(
                            user_id=user_id,
                            error="User not found"
                        )

                    response.raise_for_status()
                    data = response.json()

                    return GitHubUserSummary(
                        user_id=user_id,
                        login=data.get("login"),
                        public_repos=data.get("public_repos")
                    )

                except Exception as e:
                    return GitHubUserSummary(
                        user_id=user_id,
                        error=str(e)
                    )

            # Fetch all users concurrently
            users = await asyncio.gather(*[
                fetch_user(user_id) for user_id in self.inputs.user_ids
            ])

            return list(users)


# Example: Pipeline processing
class PipelineInputs(BaseModel):
    data_items: List[str]


class PipelineResult(BaseModel):
    processed_items: List[dict]
    duration_seconds: float


class ProcessDataPipeline(AsyncCommand[PipelineInputs, PipelineResult]):
    """
    Multi-stage async pipeline processing.

    Demonstrates:
    - Chained async operations
    - Multiple processing stages
    - Performance measurement
    """

    async def execute(self) -> PipelineResult:
        start_time = datetime.now()

        # Stage 1: Parse and validate
        async def stage1_parse(item: str) -> dict:
            await asyncio.sleep(0.1)  # Simulate parsing
            return {"raw": item, "parsed": item.upper()}

        # Stage 2: Enrich data
        async def stage2_enrich(data: dict) -> dict:
            await asyncio.sleep(0.1)  # Simulate enrichment
            data["enriched"] = len(data["raw"])
            return data

        # Stage 3: Transform
        async def stage3_transform(data: dict) -> dict:
            await asyncio.sleep(0.1)  # Simulate transformation
            data["transformed"] = data["parsed"][::-1]  # Reverse
            return data

        # Process through pipeline
        results = []
        for item in self.inputs.data_items:
            data = await stage1_parse(item)
            data = await stage2_enrich(data)
            data = await stage3_transform(data)
            results.append(data)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return PipelineResult(
            processed_items=results,
            duration_seconds=duration
        )


async def main():
    """Demonstrate batch processing examples"""

    print("=" * 60)
    print("Async Command Example: Batch Processing")
    print("=" * 60)

    # Example 1: Basic batch processing
    print("\n1. Process batch of 10 items (max 3 concurrent):")
    item_ids = list(range(1, 11))
    outcome = await ProcessBatch.run(item_ids=item_ids, max_concurrent=3)

    if outcome.is_success():
        result = outcome.unwrap()
        print(f"   Total: {result.total}")
        print(f"   Successful: {result.successful}")
        print(f"   Failed: {result.failed}")

        # Show failed items
        failed_items = [item for item in result.items if item.status == "failed"]
        if failed_items:
            print(f"   Failed items: {[item.item_id for item in failed_items]}")

    # Example 2: With progress tracking
    print("\n2. Process batch with progress tracking:")
    outcome = await ProcessBatchWithProgress.run(
        item_ids=list(range(1, 16)),
        max_concurrent=5
    )

    if outcome.is_success():
        result = outcome.unwrap()
        print(f"\n   Completed: {result.successful}/{result.total} successful")

    # Example 3: Fetch real GitHub users
    print("\n3. Fetch multiple GitHub users (IDs 1-5):")
    outcome = await FetchMultipleGitHubUsers.run(user_ids=[1, 2, 3, 4, 5])

    if outcome.is_success():
        users = outcome.unwrap()
        print(f"   Fetched {len(users)} users:")
        for user in users:
            if user.login:
                print(f"   - {user.login}: {user.public_repos} repos")
            else:
                print(f"   - User {user.user_id}: {user.error}")

    # Example 4: Pipeline processing
    print("\n4. Pipeline processing:")
    data = ["hello", "world", "async", "commands"]
    outcome = await ProcessDataPipeline.run(data_items=data)

    if outcome.is_success():
        result = outcome.unwrap()
        print(f"   Processed {len(result.processed_items)} items in {result.duration_seconds:.2f}s")
        for item in result.processed_items[:2]:  # Show first 2
            print(f"   - {item['raw']} -> {item['transformed']}")

    # Example 5: Performance comparison - sequential vs concurrent
    print("\n5. Performance comparison:")

    # Sequential
    start = datetime.now()
    for i in range(1, 6):
        await ProcessItem.run(item_id=i, delay=0.1)
    sequential_time = (datetime.now() - start).total_seconds()

    # Concurrent
    start = datetime.now()
    await ProcessBatch.run(item_ids=list(range(1, 6)), max_concurrent=5)
    concurrent_time = (datetime.now() - start).total_seconds()

    print(f"   Sequential: {sequential_time:.2f}s")
    print(f"   Concurrent: {concurrent_time:.2f}s")
    print(f"   Speedup: {sequential_time / concurrent_time:.2f}x")

    print("\n" + "=" * 60)
    print("Batch processing examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
