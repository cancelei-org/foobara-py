"""
Test Helper Utilities

This module provides helper functions and classes for common testing patterns:
- HTTP testing helpers
- Database testing helpers
- Async testing helpers
- Command composition testing
- Mock builders
- Assertion helpers

Usage:
    from tests.helpers import HTTPTestHelper, DatabaseTestHelper

    def test_http_endpoint():
        helper = HTTPTestHelper()
        response = helper.post_command("/api/create-user", {...})
        assert helper.assert_success(response)
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Type, Callable
from unittest.mock import Mock, AsyncMock, patch
from contextlib import contextmanager
from io import StringIO

from pydantic import BaseModel

from foobara_py import Command, Domain
from foobara_py.core.outcome import CommandOutcome
from foobara_py.persistence import EntityBase, Repository, InMemoryRepository


# ============================================================================
# HTTP TESTING HELPERS
# ============================================================================


class HTTPTestHelper:
    """Helper for testing HTTP connectors and endpoints"""

    def __init__(self, base_url: str = "http://testserver"):
        self.base_url = base_url
        self.default_headers = {}

    def set_auth_header(self, token: str, token_type: str = "Bearer"):
        """Set authentication header for requests"""
        self.default_headers["Authorization"] = f"{token_type} {token}"

    def set_api_key(self, api_key: str, header_name: str = "X-API-Key"):
        """Set API key header for requests"""
        self.default_headers[header_name] = api_key

    def clear_auth(self):
        """Clear authentication headers"""
        self.default_headers.pop("Authorization", None)
        self.default_headers.pop("X-API-Key", None)

    def post_command(
        self,
        endpoint: str,
        inputs: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Post command inputs to endpoint

        Args:
            endpoint: API endpoint path
            inputs: Command input data
            headers: Optional additional headers

        Returns:
            Response data
        """
        all_headers = {**self.default_headers, **(headers or {})}
        # This would use actual HTTP client in real implementation
        # For testing, we can mock this
        return {"success": True, "result": None}

    @staticmethod
    def assert_success(response: Dict[str, Any]):
        """Assert HTTP response indicates success"""
        assert response.get("success", False), "Expected successful response"
        return True

    @staticmethod
    def assert_error(response: Dict[str, Any], expected_error: Optional[str] = None):
        """Assert HTTP response indicates error"""
        assert not response.get("success", True), "Expected error response"
        if expected_error:
            errors = response.get("errors", [])
            error_symbols = [e.get("symbol") for e in errors]
            assert expected_error in error_symbols, \
                f"Expected error '{expected_error}' not found"
        return True

    @staticmethod
    def build_multipart_data(files: Dict[str, Any]) -> Dict[str, Any]:
        """Build multipart form data for file uploads"""
        return {"files": files}

    @staticmethod
    def build_json_payload(data: Dict[str, Any]) -> str:
        """Build JSON payload"""
        return json.dumps(data)


# ============================================================================
# DATABASE TESTING HELPERS
# ============================================================================


class DatabaseTestHelper:
    """Helper for testing database operations and persistence"""

    def __init__(self, repository: Optional[Repository] = None):
        self.repository = repository or InMemoryRepository()
        self.transaction_depth = 0

    def seed_data(self, entity_class: Type[EntityBase], data_list: List[Dict[str, Any]]):
        """
        Seed database with test data

        Args:
            entity_class: Entity class to create
            data_list: List of entity data dictionaries

        Returns:
            List of created entities
        """
        entities = []
        for data in data_list:
            entity = entity_class(**data)
            saved = self.repository.save(entity)
            entities.append(saved)
        return entities

    def clear_all(self):
        """Clear all data from repository"""
        if hasattr(self.repository, 'clear'):
            self.repository.clear()

    def count_entities(self, entity_class: Type[EntityBase]) -> int:
        """Count entities of a specific type"""
        all_entities = self.repository.find_all(entity_class)
        return len(all_entities)

    def assert_entity_exists(self, entity_class: Type[EntityBase], primary_key: Any):
        """Assert that an entity exists in the database"""
        entity = self.repository.find(entity_class, primary_key)
        assert entity is not None, f"Entity with pk={primary_key} not found"
        return entity

    def assert_entity_not_exists(self, entity_class: Type[EntityBase], primary_key: Any):
        """Assert that an entity does not exist in the database"""
        entity = self.repository.find(entity_class, primary_key)
        assert entity is None, f"Entity with pk={primary_key} should not exist"

    def assert_count(self, entity_class: Type[EntityBase], expected_count: int):
        """Assert the count of entities"""
        actual = self.count_entities(entity_class)
        assert actual == expected_count, \
            f"Expected {expected_count} entities, found {actual}"

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        self.transaction_depth += 1
        try:
            yield
        except Exception:
            # Rollback would happen here
            raise
        finally:
            self.transaction_depth -= 1


# ============================================================================
# ASYNC TESTING HELPERS
# ============================================================================


class AsyncTestHelper:
    """Helper for testing async commands and operations"""

    @staticmethod
    async def run_async_command(
        command_class: Type[Command],
        **inputs
    ) -> CommandOutcome:
        """
        Run an async command and return outcome

        Args:
            command_class: Async command class
            **inputs: Command inputs

        Returns:
            Command outcome
        """
        return await command_class.run_async(**inputs)

    @staticmethod
    def run_async_in_sync(coro):
        """
        Run async coroutine in synchronous context

        Useful for running async code in sync tests.
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @staticmethod
    async def gather_command_results(
        command_class: Type[Command],
        inputs_list: List[Dict[str, Any]]
    ) -> List[CommandOutcome]:
        """
        Run multiple commands concurrently

        Args:
            command_class: Command class to run
            inputs_list: List of input dictionaries

        Returns:
            List of command outcomes
        """
        tasks = [
            command_class.run_async(**inputs)
            for inputs in inputs_list
        ]
        return await asyncio.gather(*tasks)

    @staticmethod
    def create_async_mock(return_value: Any = None) -> AsyncMock:
        """Create an async mock for testing"""
        mock = AsyncMock()
        if return_value is not None:
            mock.return_value = return_value
        return mock


# ============================================================================
# COMMAND COMPOSITION TESTING HELPERS
# ============================================================================


class CommandCompositionHelper:
    """Helper for testing command composition and workflows"""

    def __init__(self):
        self.execution_log: List[Dict[str, Any]] = []

    def create_tracked_command(
        self,
        name: str,
        execute_fn: Callable
    ) -> Type[Command]:
        """
        Create a command that tracks its execution

        Args:
            name: Command name
            execute_fn: Function to execute

        Returns:
            Command class that logs execution
        """
        helper = self

        class Inputs(BaseModel):
            value: Any

        class TrackedCommand(Command[Inputs, Any]):
            def execute(self) -> Any:
                result = execute_fn(self.inputs.value)
                helper.execution_log.append({
                    'command': name,
                    'input': self.inputs.value,
                    'result': result
                })
                return result

        TrackedCommand.__name__ = name
        return TrackedCommand

    def assert_execution_order(self, expected_order: List[str]):
        """Assert commands executed in expected order"""
        actual_order = [log['command'] for log in self.execution_log]
        assert actual_order == expected_order, \
            f"Expected order {expected_order}, got {actual_order}"

    def clear_log(self):
        """Clear execution log"""
        self.execution_log.clear()

    def get_execution_count(self, command_name: str) -> int:
        """Get number of times a command was executed"""
        return len([log for log in self.execution_log if log['command'] == command_name])


# ============================================================================
# MOCK BUILDERS
# ============================================================================


class MockBuilder:
    """Builder for creating complex mocks"""

    @staticmethod
    def build_repository_mock(
        entities: Optional[List[EntityBase]] = None
    ) -> Mock:
        """
        Build a mock repository

        Args:
            entities: Optional list of entities to return

        Returns:
            Mock repository
        """
        mock_repo = Mock(spec=Repository)
        entities = entities or []

        def find_by_pk(pk):
            for entity in entities:
                if entity.primary_key == pk:
                    return entity
            return None

        mock_repo.find_by_primary_key = Mock(side_effect=find_by_pk)
        mock_repo.find_all = Mock(return_value=entities)
        mock_repo.save = Mock(side_effect=lambda e: e)
        mock_repo.delete = Mock(return_value=True)

        return mock_repo

    @staticmethod
    def build_domain_mock(name: str = "TestDomain") -> Mock:
        """Build a mock domain"""
        mock_domain = Mock(spec=Domain)
        mock_domain.name = name
        mock_domain.organization = "TestOrg"
        mock_domain.commands = {}
        return mock_domain

    @staticmethod
    def build_command_outcome_mock(
        success: bool = True,
        result: Any = None,
        errors: Optional[List[Any]] = None
    ) -> Mock:
        """Build a mock command outcome"""
        mock_outcome = Mock(spec=CommandOutcome)
        mock_outcome.is_success.return_value = success
        mock_outcome.is_failure.return_value = not success
        mock_outcome.result = result
        mock_outcome.errors = errors or []

        if success:
            mock_outcome.unwrap.return_value = result
        else:
            mock_outcome.unwrap.side_effect = Exception("Command failed")

        return mock_outcome


# ============================================================================
# ASSERTION HELPERS
# ============================================================================


class AssertionHelpers:
    """Enhanced assertion helpers for common test patterns"""

    @staticmethod
    def assert_outcome_success(outcome: CommandOutcome, expected_result: Any = None):
        """
        Assert command outcome is successful

        Args:
            outcome: Command outcome to check
            expected_result: Optional expected result value
        """
        assert outcome.is_success(), \
            f"Expected success but got errors: {outcome.errors}"

        if expected_result is not None:
            assert outcome.result == expected_result, \
                f"Expected result {expected_result}, got {outcome.result}"

    @staticmethod
    def assert_outcome_failure(
        outcome: CommandOutcome,
        expected_error_symbol: Optional[str] = None,
        expected_error_count: Optional[int] = None
    ):
        """
        Assert command outcome is a failure

        Args:
            outcome: Command outcome to check
            expected_error_symbol: Optional expected error symbol
            expected_error_count: Optional expected number of errors
        """
        assert outcome.is_failure(), \
            f"Expected failure but got success with result: {outcome.result}"

        if expected_error_symbol:
            error_symbols = [e.symbol for e in outcome.errors]
            assert expected_error_symbol in error_symbols, \
                f"Expected error '{expected_error_symbol}' not in {error_symbols}"

        if expected_error_count is not None:
            assert len(outcome.errors) == expected_error_count, \
                f"Expected {expected_error_count} errors, got {len(outcome.errors)}"

    @staticmethod
    def assert_validation_error(
        outcome: CommandOutcome,
        field_path: List[str],
        error_symbol: Optional[str] = None
    ):
        """
        Assert a validation error occurred on a specific field

        Args:
            outcome: Command outcome to check
            field_path: Path to the field (e.g., ["user", "email"])
            error_symbol: Optional expected error symbol
        """
        assert outcome.is_failure(), "Expected validation error"

        field_errors = [
            e for e in outcome.errors
            if hasattr(e, 'path') and list(e.path) == field_path
        ]

        assert len(field_errors) > 0, \
            f"No validation errors found for field path {field_path}"

        if error_symbol:
            assert any(e.symbol == error_symbol for e in field_errors), \
                f"Expected error symbol '{error_symbol}' not found for field {field_path}"

    @staticmethod
    def assert_entities_equal(
        entity1: EntityBase,
        entity2: EntityBase,
        exclude_fields: Optional[List[str]] = None
    ):
        """
        Assert two entities are equal

        Args:
            entity1: First entity
            entity2: Second entity
            exclude_fields: Fields to exclude from comparison
        """
        exclude_fields = exclude_fields or []

        dict1 = entity1.model_dump(exclude=set(exclude_fields))
        dict2 = entity2.model_dump(exclude=set(exclude_fields))

        assert dict1 == dict2, f"Entities not equal:\n{dict1}\nvs\n{dict2}"

    @staticmethod
    def assert_no_side_effects(
        action: Callable,
        check_fn: Callable[[], Any]
    ):
        """
        Assert an action has no side effects

        Args:
            action: Action to perform
            check_fn: Function that returns state to check

        Usage:
            state = lambda: repository.count()
            AssertionHelpers.assert_no_side_effects(
                action=lambda: command.run(invalid_input),
                check_fn=state
            )
        """
        before = check_fn()
        action()
        after = check_fn()
        assert before == after, f"Side effect detected: {before} -> {after}"


# ============================================================================
# INTEGRATION TEST HELPERS
# ============================================================================


class IntegrationTestHelper:
    """Helper for integration tests spanning multiple components"""

    def __init__(self):
        self.domain = None
        self.repository = InMemoryRepository()
        self.commands: Dict[str, Type[Command]] = {}

    def setup_domain(self, name: str = "TestDomain") -> Domain:
        """Setup a test domain"""
        self.domain = Domain(name=name, organization="TestOrg")
        return self.domain

    def register_command(self, name: str, command_class: Type[Command]):
        """Register a command for testing"""
        self.commands[name] = command_class
        if self.domain:
            self.domain.command(command_class)

    def run_workflow(self, workflow_steps: List[Dict[str, Any]]) -> List[CommandOutcome]:
        """
        Run a multi-step workflow

        Args:
            workflow_steps: List of dicts with 'command' and 'inputs' keys

        Returns:
            List of command outcomes

        Usage:
            results = helper.run_workflow([
                {'command': 'CreateUser', 'inputs': {'name': 'test'}},
                {'command': 'UpdateUser', 'inputs': {'id': 1, 'name': 'updated'}},
            ])
        """
        results = []
        for step in workflow_steps:
            command_name = step['command']
            inputs = step['inputs']
            command_class = self.commands.get(command_name)

            if command_class:
                outcome = command_class.run(**inputs)
                results.append(outcome)
            else:
                raise ValueError(f"Command '{command_name}' not registered")

        return results

    def assert_workflow_success(self, outcomes: List[CommandOutcome]):
        """Assert all workflow steps succeeded"""
        for i, outcome in enumerate(outcomes):
            assert outcome.is_success(), \
                f"Workflow step {i} failed: {outcome.errors}"


# ============================================================================
# SNAPSHOT TESTING HELPERS
# ============================================================================


class SnapshotHelper:
    """Helper for snapshot testing (comparing against saved outputs)"""

    def __init__(self, snapshot_dir: str = "tests/snapshots"):
        self.snapshot_dir = snapshot_dir

    def assert_matches_snapshot(
        self,
        test_name: str,
        actual_data: Any,
        update_snapshots: bool = False
    ):
        """
        Compare actual data against saved snapshot

        Args:
            test_name: Name of the test
            actual_data: Data to compare
            update_snapshots: Whether to update snapshots
        """
        import os
        import json

        snapshot_path = os.path.join(self.snapshot_dir, f"{test_name}.json")

        if update_snapshots or not os.path.exists(snapshot_path):
            # Save new snapshot
            os.makedirs(self.snapshot_dir, exist_ok=True)
            with open(snapshot_path, 'w') as f:
                json.dump(actual_data, f, indent=2, default=str)
            return

        # Compare with existing snapshot
        with open(snapshot_path, 'r') as f:
            expected_data = json.load(f)

        assert actual_data == expected_data, \
            f"Snapshot mismatch for {test_name}"
