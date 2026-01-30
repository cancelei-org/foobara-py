#!/usr/bin/env python3
"""
Async Command Example: Fetch API Data

Demonstrates fetching data from external APIs using AsyncCommand with:
- HTTP requests using httpx
- Error handling for network failures
- Timeout handling
- Retry logic with exponential backoff
"""

import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from foobara_py import AsyncCommand
import httpx


# Input and result models
class FetchUserInputs(BaseModel):
    user_id: int = Field(..., ge=1, description="GitHub user ID to fetch")
    timeout: float = Field(default=10.0, description="Request timeout in seconds")


class GitHubUser(BaseModel):
    """GitHub user data model"""
    login: str
    id: int
    name: Optional[str]
    email: Optional[str]
    public_repos: int
    followers: int
    following: int
    created_at: str


# Basic async command
class FetchGitHubUser(AsyncCommand[FetchUserInputs, GitHubUser]):
    """Fetch GitHub user data by username"""

    async def execute(self) -> GitHubUser:
        """
        Fetch user data from GitHub API.

        Demonstrates:
        - Async HTTP requests
        - Error handling
        - Timeout configuration
        """
        url = f"https://api.github.com/user/{self.inputs.user_id}"

        try:
            async with httpx.AsyncClient(timeout=self.inputs.timeout) as client:
                response = await client.get(
                    url,
                    headers={
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "Foobara-Python-Example"
                    }
                )

                # Handle HTTP errors
                if response.status_code == 404:
                    self.add_runtime_error(
                        "user_not_found",
                        f"GitHub user with ID {self.inputs.user_id} not found",
                        halt=True,
                        user_id=self.inputs.user_id
                    )

                if response.status_code == 403:
                    self.add_runtime_error(
                        "rate_limited",
                        "GitHub API rate limit exceeded",
                        halt=True
                    )

                response.raise_for_status()
                data = response.json()
                return GitHubUser(**data)

        except httpx.TimeoutException:
            self.add_runtime_error(
                "request_timeout",
                f"Request timed out after {self.inputs.timeout} seconds",
                halt=True,
                timeout=self.inputs.timeout
            )
        except httpx.RequestError as e:
            self.add_runtime_error(
                "network_error",
                f"Network error: {str(e)}",
                halt=True,
                error_type=type(e).__name__
            )


# Advanced: With retry logic
class FetchUserWithRetryInputs(BaseModel):
    user_id: int = Field(..., ge=1)
    max_retries: int = Field(default=3, ge=1, le=10)
    base_delay: float = Field(default=1.0, ge=0.1)


class FetchGitHubUserWithRetry(AsyncCommand[FetchUserWithRetryInputs, GitHubUser]):
    """Fetch GitHub user with automatic retry on failure"""

    async def execute(self) -> GitHubUser:
        """
        Fetch user data with exponential backoff retry.

        Demonstrates:
        - Retry logic
        - Exponential backoff
        - Transient error handling
        """
        url = f"https://api.github.com/user/{self.inputs.user_id}"

        for attempt in range(self.inputs.max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        url,
                        headers={
                            "Accept": "application/vnd.github.v3+json",
                            "User-Agent": "Foobara-Python-Example"
                        }
                    )

                    # Don't retry on 404 (permanent error)
                    if response.status_code == 404:
                        self.add_runtime_error(
                            "user_not_found",
                            f"User {self.inputs.user_id} not found",
                            halt=True
                        )

                    response.raise_for_status()
                    data = response.json()
                    return GitHubUser(**data)

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                is_last_attempt = attempt == self.inputs.max_retries - 1

                if is_last_attempt:
                    self.add_runtime_error(
                        "fetch_failed",
                        f"Failed after {self.inputs.max_retries} attempts: {str(e)}",
                        halt=True,
                        attempts=self.inputs.max_retries
                    )
                else:
                    # Exponential backoff
                    delay = self.inputs.base_delay * (2 ** attempt)
                    print(f"Attempt {attempt + 1} failed, retrying in {delay}s...")
                    await asyncio.sleep(delay)


# Multiple API calls in sequence
class FetchUserDetailsInputs(BaseModel):
    username: str = Field(..., min_length=1)


class UserDetails(BaseModel):
    user: GitHubUser
    repos_count: int
    total_stars: int


class FetchUserDetails(AsyncCommand[FetchUserDetailsInputs, UserDetails]):
    """Fetch comprehensive user details from multiple endpoints"""

    async def execute(self) -> UserDetails:
        """
        Fetch user data and repository statistics.

        Demonstrates:
        - Sequential async calls
        - Data aggregation
        - Shared HTTP client
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            # First, get user info
            user_response = await client.get(
                f"https://api.github.com/users/{self.inputs.username}",
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Foobara-Python-Example"
                }
            )

            if user_response.status_code == 404:
                self.add_runtime_error(
                    "user_not_found",
                    f"User {self.inputs.username} not found",
                    halt=True
                )

            user_response.raise_for_status()
            user_data = user_response.json()

            # Then get repositories
            repos_response = await client.get(
                f"https://api.github.com/users/{self.inputs.username}/repos",
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Foobara-Python-Example"
                }
            )
            repos_response.raise_for_status()
            repos_data = repos_response.json()

            # Calculate total stars
            total_stars = sum(repo["stargazers_count"] for repo in repos_data)

            return UserDetails(
                user=GitHubUser(**user_data),
                repos_count=len(repos_data),
                total_stars=total_stars
            )


async def main():
    """Demonstrate async command usage"""

    print("=" * 60)
    print("Async Command Example: Fetch API Data")
    print("=" * 60)

    # Example 1: Basic fetch
    print("\n1. Basic fetch (user ID 1 = mojombo):")
    outcome = await FetchGitHubUser.run(user_id=1)

    if outcome.is_success():
        user = outcome.unwrap()
        print(f"   Success! User: {user.login}")
        print(f"   Name: {user.name}")
        print(f"   Repos: {user.public_repos}, Followers: {user.followers}")
    else:
        print("   Error:")
        for error in outcome.errors:
            print(f"   - {error.symbol}: {error.message}")

    # Example 2: Handle 404 error
    print("\n2. Fetch non-existent user (ID 999999999):")
    outcome = await FetchGitHubUser.run(user_id=999999999)

    if outcome.is_failure():
        print("   Expected failure:")
        for error in outcome.errors:
            print(f"   - {error.symbol}: {error.message}")

    # Example 3: With retry logic
    print("\n3. Fetch with retry (user ID 2):")
    outcome = await FetchGitHubUserWithRetry.run(
        user_id=2,
        max_retries=3,
        base_delay=0.5
    )

    if outcome.is_success():
        user = outcome.unwrap()
        print(f"   Success! User: {user.login}")

    # Example 4: Detailed fetch (requires username)
    print("\n4. Fetch detailed user info (torvalds):")
    outcome = await FetchUserDetails.run(username="torvalds")

    if outcome.is_success():
        details = outcome.unwrap()
        print(f"   User: {details.user.login}")
        print(f"   Total repos: {details.repos_count}")
        print(f"   Total stars: {details.total_stars}")

    # Example 5: Test timeout (intentionally slow endpoint)
    print("\n5. Test timeout handling:")
    outcome = await FetchGitHubUser.run(user_id=1, timeout=0.001)  # Very short timeout

    if outcome.is_failure():
        print("   Expected timeout error:")
        for error in outcome.errors:
            print(f"   - {error.symbol}: {error.message}")

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the async examples
    asyncio.run(main())
