"""
Comprehensive tests for full Ruby Foobara parity.

Tests all new features:
- 8-state execution flow
- Lifecycle callbacks
- Subcommand execution
- Runtime path in errors
- Domain dependencies
- Transaction management
- Entity system
- MCP batch requests
"""

import pytest
import json
from pydantic import BaseModel, Field
from typing import Optional

# Import from the new implementation
from foobara_py.core.command import Command, AsyncCommand, command
from foobara_py.core.outcome import CommandOutcome
from foobara_py.core.errors import FoobaraError, ErrorCollection, Symbols
from foobara_py.core.state_machine import CommandState, Halt
from foobara_py.core.transactions import TransactionContext, transaction
from foobara_py.domain.domain import Domain, Organization, DomainDependencyError
from foobara_py.persistence.entity import EntityBase, entity, load, LoadSpec
from foobara_py.persistence.repository import InMemoryRepository, RepositoryRegistry
from foobara_py.connectors.mcp import MCPConnector


# ==================== Test Models ====================

class CreateUserInputs(BaseModel):
    name: str = Field(..., min_length=1)
    email: str
    age: Optional[int] = None


class User(BaseModel):
    id: int
    name: str
    email: str
    age: Optional[int] = None


class ValidateEmailInputs(BaseModel):
    email: str


class ValidateEmailResult(BaseModel):
    valid: bool


# ==================== Test: State Machine ====================

class TestStateMachine:
    """Test 8-state execution flow"""

    def test_successful_execution_transitions(self):
        """Test state transitions for successful execution"""

        class SimpleCommand(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        cmd = SimpleCommand(name="John", email="john@example.com")

        assert cmd.state == CommandState.INITIALIZED

        outcome = cmd.run_instance()

        assert outcome.is_success()
        assert cmd.state == CommandState.SUCCEEDED

    def test_failed_validation_transitions(self):
        """Test state transitions when validation fails"""

        class StrictCommand(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        cmd = StrictCommand(name="", email="test@example.com")  # Empty name
        outcome = cmd.run_instance()

        assert outcome.is_failure()
        assert cmd.state == CommandState.FAILED

    def test_halt_during_execution(self):
        """Test Halt exception handling"""

        class HaltingCommand(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                self.add_runtime_error("stopped", "Halted execution", halt=True)
                return User(id=1, name="", email="")  # Never reached

        outcome = HaltingCommand.run(name="John", email="john@example.com")

        assert outcome.is_failure()
        assert len(outcome.errors) == 1
        assert outcome.errors[0].symbol == "stopped"


# ==================== Test: Callbacks ====================

class TestCallbacks:
    """Test lifecycle callbacks"""

    def test_before_validate_callback(self):
        """Test before_validate callback"""
        callback_called = []

        class CallbackCommand(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                callback_called.append("execute")
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        # Register callback using DSL
        def log_before_validate(cmd):
            callback_called.append("before_validate")

        CallbackCommand.before_validate_transition(log_before_validate)

        outcome = CallbackCommand.run(name="John", email="john@example.com")

        assert outcome.is_success()
        assert "before_validate" in callback_called
        assert callback_called.index("before_validate") < callback_called.index("execute")

    def test_after_execute_callback(self):
        """Test after_execute callback"""
        callback_called = []

        class CallbackCommand(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                callback_called.append("execute")
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        # Register callback using DSL
        def log_after_execute(cmd):
            callback_called.append("after_execute")

        CallbackCommand.after_execute_transition(log_after_execute)

        outcome = CallbackCommand.run(name="John", email="john@example.com")

        assert outcome.is_success()
        assert "execute" in callback_called
        assert "after_execute" in callback_called


# ==================== Test: Subcommands ====================

class TestSubcommands:
    """Test subcommand execution and error propagation"""

    def test_successful_subcommand(self):
        """Test successful subcommand execution"""

        class InnerCommand(Command[ValidateEmailInputs, ValidateEmailResult]):
            def execute(self) -> ValidateEmailResult:
                return ValidateEmailResult(valid=True)

        class OuterCommand(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                result = self.run_subcommand_bang(
                    InnerCommand,
                    email=self.inputs.email
                )
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        outcome = OuterCommand.run(name="John", email="john@example.com")
        assert outcome.is_success()

    def test_subcommand_error_propagation(self):
        """Test that subcommand errors propagate with runtime_path"""

        class FailingInnerCommand(Command[ValidateEmailInputs, ValidateEmailResult]):
            def execute(self) -> ValidateEmailResult:
                self.add_runtime_error("invalid_email", "Email is invalid")
                return None

        class OuterCommand(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                self.run_subcommand_bang(
                    FailingInnerCommand,
                    email=self.inputs.email
                )
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        outcome = OuterCommand.run(name="John", email="invalid")

        assert outcome.is_failure()
        assert len(outcome.errors) == 1
        error = outcome.errors[0]
        # Error should have runtime_path with subcommand name
        assert len(error.runtime_path) > 0


# ==================== Test: Runtime Path in Errors ====================

class TestRuntimePath:
    """Test runtime_path in error keys"""

    def test_error_key_with_runtime_path(self):
        """Test composite error key with runtime path"""
        error = FoobaraError(
            category='data',
            symbol='invalid_format',
            path=('user', 'email'),
            message='Invalid email',
            runtime_path=('create_user', 'validate_email')
        )

        key = error.key()
        assert 'create_user' in key
        assert 'validate_email' in key
        assert 'data' in key
        assert 'invalid_format' in key

    def test_error_with_path_prefix(self):
        """Test adding runtime path prefix"""
        error = FoobaraError.data_error(
            'required',
            ['name'],
            'Name is required'
        )

        prefixed = error.with_runtime_path_prefix('outer_command')
        assert 'outer_command' in prefixed.key()


# ==================== Test: Domain Dependencies ====================

class TestDomainDependencies:
    """Test domain dependency validation"""

    def test_domain_can_call_from_dependency(self):
        """Test that domain can call commands from dependencies"""
        users = Domain("Users", organization="Test")
        auth = Domain("Auth", organization="Test")

        users.depends_on("Auth")

        assert users.can_call_from("Auth")
        assert users.can_call_from("Users")  # Same domain
        assert users.can_call_from("Global")  # Global always allowed

    def test_domain_cannot_call_from_non_dependency(self):
        """Test that domain cannot call commands from non-dependencies"""
        users = Domain("UsersNoDep", organization="Test")

        assert not users.can_call_from("Billing")


# ==================== Test: Entity System ====================

class TestEntitySystem:
    """Test entity and repository system"""

    def test_entity_primary_key(self):
        """Test entity primary key handling"""

        @entity(primary_key='id')
        class TestUser(EntityBase):
            id: int
            name: str

        user = TestUser(id=1, name="John")
        assert user.primary_key == 1
        assert user.is_new

    def test_in_memory_repository(self):
        """Test in-memory repository operations"""

        class RepoUser(EntityBase):
            id: Optional[int] = None
            name: str

        repo = InMemoryRepository()

        # Save
        user = RepoUser(name="John")
        saved = repo.save(user)
        assert saved.id is not None
        assert saved.is_persisted

        # Find
        found = repo.find(RepoUser, saved.id)
        assert found is not None
        assert found.name == "John"

        # Delete
        deleted = repo.delete(saved)
        assert deleted
        assert repo.find(RepoUser, saved.id) is None


# ==================== Test: MCP Connector ====================

class TestMCPConnector:
    """Test MCP connector with batch requests"""

    def setup_method(self):
        """Set up test connector"""
        self.connector = MCPConnector(
            name="TestServer",
            version="1.0.0"
        )

        # Create and register a simple command
        class AddNumbersInputs(BaseModel):
            a: int
            b: int

        class AddNumbers(Command[AddNumbersInputs, int]):
            """Add two numbers"""
            _domain = "Math"
            _organization = "Test"

            def execute(self) -> int:
                return self.inputs.a + self.inputs.b

        self.connector._registry.register(AddNumbers)
        self.AddNumbers = AddNumbers

    def test_single_request(self):
        """Test single JSON-RPC request"""
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        })

        response = self.connector.run(request)
        data = json.loads(response)

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "tools" in data["result"]

    def test_batch_request(self):
        """Test batch JSON-RPC requests"""
        request = json.dumps([
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ])

        response = self.connector.run(request)
        data = json.loads(response)

        assert isinstance(data, list)
        assert len(data) == 2

    def test_notification_no_response(self):
        """Test that notifications return no response"""
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/test",
            "params": {}
        })

        response = self.connector.run(request)
        assert response is None

    def test_tools_call(self):
        """Test tools/call execution"""
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::Math::AddNumbers",
                "arguments": {"a": 5, "b": 3}
            }
        })

        response = self.connector.run(request)
        data = json.loads(response)

        assert data["id"] == 1
        assert "result" in data
        content = data["result"]["content"][0]["text"]
        assert json.loads(content) == 8

    def test_initialize_handshake(self):
        """Test initialize handshake"""
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test"}
            }
        })

        response = self.connector.run(request)
        data = json.loads(response)

        assert "result" in data
        assert data["result"]["protocolVersion"] == "2024-11-05"
        assert data["result"]["serverInfo"]["name"] == "TestServer"


# ==================== Test: Transactions ====================

class TestTransactions:
    """Test transaction management"""

    def test_transaction_context(self):
        """Test transaction context manager"""
        entered = []
        exited = []

        class MockHandler:
            def begin(self):
                entered.append(True)

            def commit(self):
                exited.append("commit")

            def rollback(self):
                exited.append("rollback")

        with transaction(MockHandler()):
            assert len(entered) == 1

        assert "commit" in exited

    def test_transaction_rollback_on_error(self):
        """Test transaction rollback on exception"""
        rolled_back = []

        class MockHandler:
            def begin(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                rolled_back.append(True)

        with pytest.raises(ValueError):
            with transaction(MockHandler()):
                raise ValueError("Test error")

        assert len(rolled_back) == 1


# ==================== Test: Error Collection ====================

class TestErrorCollection:
    """Test error collection operations"""

    def test_error_collection_queries(self):
        """Test error collection query methods"""
        errors = ErrorCollection()

        errors.add(FoobaraError.data_error("required", ["name"], "Name required"))
        errors.add(FoobaraError.data_error("invalid", ["email"], "Email invalid"))
        errors.add(FoobaraError.runtime_error("failed", "Operation failed"))

        assert errors.has_errors()
        assert len(errors) == 3

        # Query by category
        data_errors = errors.by_category("data")
        assert len(data_errors) == 2

        runtime_errors = errors.runtime_errors()
        assert len(runtime_errors) == 1

        # Query by path
        email_errors = errors.at_path("email")
        assert len(email_errors) == 1

        # Query by symbol
        required_errors = errors.with_symbol("required")
        assert len(required_errors) == 1

    def test_error_collection_serialization(self):
        """Test error collection serialization"""
        errors = ErrorCollection()
        errors.add(FoobaraError.data_error("required", ["name"], "Name required"))

        as_dict = errors.to_dict()
        assert len(as_dict) == 1

        as_list = errors.to_list()
        assert len(as_list) == 1
        assert as_list[0]["symbol"] == "required"


# ==================== Test: Full Integration ====================

class TestFullIntegration:
    """Test full integration scenario"""

    def test_complete_command_flow(self):
        """Test complete command flow with all features"""
        # Set up domain
        org = Organization("IntegrationTest")
        users = org.domain("Users")
        users.depends_on("Global")

        # Create command with callbacks
        executed_phases = []

        @users.command
        class CreateUserIntegration(Command[CreateUserInputs, User]):
            """Create a user with full validation"""

            def validate(self):
                executed_phases.append("validate")
                if self.inputs.name == "admin":
                    self.add_input_error(
                        ["name"],
                        "reserved",
                        "Name 'admin' is reserved"
                    )

            def execute(self) -> User:
                executed_phases.append("execute")
                return User(
                    id=1,
                    name=self.inputs.name,
                    email=self.inputs.email,
                    age=self.inputs.age
                )

        # Register callbacks using DSL
        def log_start(cmd):
            executed_phases.append("before_validate")

        def log_end(cmd):
            executed_phases.append("after_execute")

        CreateUserIntegration.before_validate_transition(log_start)
        CreateUserIntegration.after_execute_transition(log_end)

        # Test successful execution
        outcome = CreateUserIntegration.run(
            name="John",
            email="john@example.com",
            age=30
        )

        assert outcome.is_success()
        user = outcome.unwrap()
        assert user.name == "John"
        assert "before_validate" in executed_phases
        assert "validate" in executed_phases
        assert "execute" in executed_phases
        assert "after_execute" in executed_phases

        # Test validation failure
        executed_phases.clear()
        outcome = CreateUserIntegration.run(
            name="admin",
            email="admin@example.com"
        )

        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "reserved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
