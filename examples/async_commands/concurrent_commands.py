#!/usr/bin/env python3
"""
Async Command Example: Concurrent Commands

Demonstrates running multiple async commands concurrently with:
- Command composition and orchestration
- Error propagation across commands
- Resource sharing
- Complex workflows
"""

import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
from foobara_py import AsyncCommand
import httpx
from datetime import datetime


# Data models
class UserProfileInputs(BaseModel):
    user_id: int


class UserProfile(BaseModel):
    user_id: int
    login: str
    name: Optional[str]
    bio: Optional[str]
    public_repos: int


class UserReposInputs(BaseModel):
    username: str


class Repository(BaseModel):
    name: str
    description: Optional[str]
    stars: int
    language: Optional[str]


class UserActivityInputs(BaseModel):
    username: str


class ActivitySummary(BaseModel):
    total_events: int
    event_types: List[str]
    most_recent: Optional[str]


# Individual async commands
class FetchUserProfile(AsyncCommand[UserProfileInputs, UserProfile]):
    """Fetch user profile from GitHub API"""

    async def execute(self) -> UserProfile:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.github.com/user/{self.inputs.user_id}",
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Foobara-Python-Example"
                }
            )

            if response.status_code == 404:
                self.add_runtime_error(
                    "user_not_found",
                    f"User with ID {self.inputs.user_id} not found",
                    halt=True
                )

            response.raise_for_status()
            data = response.json()

            return UserProfile(
                user_id=data["id"],
                login=data["login"],
                name=data.get("name"),
                bio=data.get("bio"),
                public_repos=data["public_repos"]
            )


class FetchUserRepos(AsyncCommand[UserReposInputs, List[Repository]]):
    """Fetch user repositories"""

    async def execute(self) -> List[Repository]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.github.com/users/{self.inputs.username}/repos",
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Foobara-Python-Example"
                },
                params={"sort": "stars", "per_page": 5}
            )

            if response.status_code == 404:
                self.add_runtime_error(
                    "user_not_found",
                    f"User {self.inputs.username} not found",
                    halt=True
                )

            response.raise_for_status()
            repos_data = response.json()

            return [
                Repository(
                    name=repo["name"],
                    description=repo.get("description"),
                    stars=repo["stargazers_count"],
                    language=repo.get("language")
                )
                for repo in repos_data
            ]


class FetchUserActivity(AsyncCommand[UserActivityInputs, ActivitySummary]):
    """Fetch user activity events"""

    async def execute(self) -> ActivitySummary:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.github.com/users/{self.inputs.username}/events",
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Foobara-Python-Example"
                }
            )

            if response.status_code == 404:
                # Graceful degradation - return empty activity
                return ActivitySummary(
                    total_events=0,
                    event_types=[],
                    most_recent=None
                )

            response.raise_for_status()
            events = response.json()

            event_types = list(set(event["type"] for event in events))
            most_recent = events[0]["created_at"] if events else None

            return ActivitySummary(
                total_events=len(events),
                event_types=event_types,
                most_recent=most_recent
            )


# Orchestration commands
class AggregateUserDataInputs(BaseModel):
    user_id: int


class UserDashboard(BaseModel):
    profile: UserProfile
    top_repos: List[Repository]
    activity: ActivitySummary
    total_stars: int


class AggregateUserData(AsyncCommand[AggregateUserDataInputs, UserDashboard]):
    """
    Aggregate data from multiple sources concurrently.

    Demonstrates:
    - Running multiple commands in parallel
    - Handling partial failures
    - Data composition
    """

    async def execute(self) -> UserDashboard:
        # Run all commands concurrently
        profile_task = FetchUserProfile.run(user_id=self.inputs.user_id)

        # Start all tasks in parallel
        profile_outcome = await profile_task

        # Check if profile fetch failed
        if profile_outcome.is_failure():
            for error in profile_outcome.errors:
                self.add_error(error)
            raise asyncio.CancelledError("Profile fetch failed")

        profile = profile_outcome.unwrap()

        # Now fetch repos and activity using the username
        repos_task = FetchUserRepos.run(username=profile.login)
        activity_task = FetchUserActivity.run(username=profile.login)

        repos_outcome, activity_outcome = await asyncio.gather(
            repos_task, activity_task
        )

        # Handle repos (required)
        if repos_outcome.is_failure():
            for error in repos_outcome.errors:
                self.add_error(error)
            raise asyncio.CancelledError("Repos fetch failed")

        repos = repos_outcome.unwrap()

        # Handle activity (optional - use default if failed)
        if activity_outcome.is_success():
            activity = activity_outcome.unwrap()
        else:
            activity = ActivitySummary(
                total_events=0,
                event_types=[],
                most_recent=None
            )

        # Calculate total stars
        total_stars = sum(repo.stars for repo in repos)

        return UserDashboard(
            profile=profile,
            top_repos=repos,
            activity=activity,
            total_stars=total_stars
        )


# Advanced: Fan-out/fan-in pattern
class CompareUsersInputs(BaseModel):
    user_ids: List[int] = Field(..., min_length=2, max_length=10)


class UserComparison(BaseModel):
    users: List[UserProfile]
    total_repos: int
    most_active: Optional[str]


class CompareMultipleUsers(AsyncCommand[CompareUsersInputs, UserComparison]):
    """
    Compare multiple users (fan-out/fan-in pattern).

    Demonstrates:
    - Fan-out: Spawn multiple concurrent commands
    - Fan-in: Aggregate results
    - Error handling with partial results
    """

    async def execute(self) -> UserComparison:
        # Fan-out: Fetch all user profiles concurrently
        tasks = [
            FetchUserProfile.run(user_id=user_id)
            for user_id in self.inputs.user_ids
        ]

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        # Fan-in: Collect successful results
        profiles = []
        for idx, outcome in enumerate(outcomes):
            if isinstance(outcome, Exception):
                print(f"User {self.inputs.user_ids[idx]} failed: {outcome}")
                continue

            if outcome.is_success():
                profiles.append(outcome.unwrap())
            else:
                print(f"User {self.inputs.user_ids[idx]} failed with errors")

        if not profiles:
            self.add_runtime_error(
                "no_users_found",
                "Failed to fetch any user profiles",
                halt=True
            )

        # Analyze results
        total_repos = sum(p.public_repos for p in profiles)
        most_active = max(profiles, key=lambda p: p.public_repos).login if profiles else None

        return UserComparison(
            users=profiles,
            total_repos=total_repos,
            most_active=most_active
        )


# Complex workflow with dependencies
class UserReportInputs(BaseModel):
    user_id: int
    include_analysis: bool = True


class UserReport(BaseModel):
    profile: UserProfile
    repos: List[Repository]
    stats: dict
    generated_at: str


class GenerateUserReport(AsyncCommand[UserReportInputs, UserReport]):
    """
    Generate comprehensive user report with dependent operations.

    Demonstrates:
    - Sequential dependencies (profile -> repos)
    - Conditional execution
    - Complex data aggregation
    """

    async def execute(self) -> UserReport:
        # Step 1: Fetch profile (required first)
        profile_outcome = await FetchUserProfile.run(user_id=self.inputs.user_id)

        if profile_outcome.is_failure():
            for error in profile_outcome.errors:
                self.add_error(error)
            self.halt()

        profile = profile_outcome.unwrap()

        # Step 2: Fetch repos (depends on profile for username)
        repos_outcome = await FetchUserRepos.run(username=profile.login)

        repos = []
        if repos_outcome.is_success():
            repos = repos_outcome.unwrap()

        # Step 3: Optional analysis
        stats = {}
        if self.inputs.include_analysis and repos:
            # Analyze repositories
            languages = [repo.language for repo in repos if repo.language]
            language_counts = {}
            for lang in languages:
                language_counts[lang] = language_counts.get(lang, 0) + 1

            stats = {
                "total_stars": sum(repo.stars for repo in repos),
                "avg_stars": sum(repo.stars for repo in repos) / len(repos) if repos else 0,
                "languages": language_counts,
                "has_descriptions": sum(1 for repo in repos if repo.description),
            }

        return UserReport(
            profile=profile,
            repos=repos,
            stats=stats,
            generated_at=datetime.now().isoformat()
        )


# Resource pooling example
class SharedHttpClient:
    """Shared HTTP client for multiple commands"""

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()


async def main():
    """Demonstrate concurrent command patterns"""

    print("=" * 60)
    print("Async Command Example: Concurrent Commands")
    print("=" * 60)

    # Example 1: Aggregate user data
    print("\n1. Aggregate user data from multiple sources (user ID 1):")
    outcome = await AggregateUserData.run(user_id=1)

    if outcome.is_success():
        dashboard = outcome.unwrap()
        print(f"   User: {dashboard.profile.login}")
        print(f"   Bio: {dashboard.profile.bio or 'N/A'}")
        print(f"   Total stars: {dashboard.total_stars}")
        print(f"   Top repos: {len(dashboard.top_repos)}")
        print(f"   Recent events: {dashboard.activity.total_events}")

    # Example 2: Compare multiple users
    print("\n2. Compare multiple users (IDs 1, 2, 3):")
    outcome = await CompareMultipleUsers.run(user_ids=[1, 2, 3])

    if outcome.is_success():
        comparison = outcome.unwrap()
        print(f"   Compared {len(comparison.users)} users")
        print(f"   Total repos: {comparison.total_repos}")
        print(f"   Most active: {comparison.most_active}")
        for user in comparison.users:
            print(f"   - {user.login}: {user.public_repos} repos")

    # Example 3: Generate detailed report
    print("\n3. Generate user report (user ID 2):")
    outcome = await GenerateUserReport.run(user_id=2, include_analysis=True)

    if outcome.is_success():
        report = outcome.unwrap()
        print(f"   Report for: {report.profile.login}")
        print(f"   Total repos: {len(report.repos)}")
        if report.stats:
            print(f"   Total stars: {report.stats.get('total_stars', 0)}")
            print(f"   Avg stars: {report.stats.get('avg_stars', 0):.1f}")
            print(f"   Languages: {', '.join(report.stats.get('languages', {}).keys())}")

    # Example 4: Concurrent independent commands
    print("\n4. Run multiple independent commands concurrently:")
    start_time = datetime.now()

    tasks = [
        FetchUserProfile.run(user_id=1),
        FetchUserProfile.run(user_id=2),
        FetchUserProfile.run(user_id=3),
    ]

    outcomes = await asyncio.gather(*tasks)

    duration = (datetime.now() - start_time).total_seconds()
    successful = sum(1 for o in outcomes if o.is_success())

    print(f"   Fetched {successful}/{len(tasks)} profiles in {duration:.2f}s")

    # Example 5: Handle partial failures
    print("\n5. Handle partial failures (mix of valid and invalid user IDs):")
    outcome = await CompareMultipleUsers.run(user_ids=[1, 999999999, 2])

    if outcome.is_success():
        comparison = outcome.unwrap()
        print(f"   Successfully fetched {len(comparison.users)} out of 3 users")
        print(f"   Users: {[u.login for u in comparison.users]}")

    # Example 6: Sequential vs concurrent performance
    print("\n6. Performance comparison:")

    # Sequential
    start = datetime.now()
    await FetchUserProfile.run(user_id=1)
    await FetchUserProfile.run(user_id=2)
    await FetchUserProfile.run(user_id=3)
    sequential_time = (datetime.now() - start).total_seconds()

    # Concurrent
    start = datetime.now()
    await asyncio.gather(
        FetchUserProfile.run(user_id=1),
        FetchUserProfile.run(user_id=2),
        FetchUserProfile.run(user_id=3),
    )
    concurrent_time = (datetime.now() - start).total_seconds()

    print(f"   Sequential: {sequential_time:.2f}s")
    print(f"   Concurrent: {concurrent_time:.2f}s")
    print(f"   Speedup: {sequential_time / concurrent_time:.2f}x")

    print("\n" + "=" * 60)
    print("Concurrent command examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
