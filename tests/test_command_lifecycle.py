"""
Tests for Command lifecycle hooks, entity loading, possible_errors, and subcommands.
"""

import pytest
from pydantic import BaseModel
from foobara_py.core.command import Command, AsyncCommand
from foobara_py.core.outcome import CommandOutcome
from foobara_py.persistence.entity import EntityBase, load
from foobara_py.persistence.repository import InMemoryRepository, RepositoryRegistry


# ==================== Test Models ====================

class CreateUserInputs(BaseModel):
    name: str
    email: str


class User(BaseModel):
    id: int
    name: str
    email: str


class UpdateUserInputs(BaseModel):
    user_id: int
    name: str


class ValidateEmailInputs(BaseModel):
    email: str


# ==================== Test Entity ====================

class UserEntity(EntityBase):
    _primary_key_field = 'id'

    id: int = None
    name: str
    email: str


# ==================== Test Commands ====================

class CreateUserWithHooks(Command[CreateUserInputs, User]):
    """Create user with lifecycle hooks"""

    _before_called = False
    _after_called = False

    def before_execute(self) -> None:
        CreateUserWithHooks._before_called = True

    def after_execute(self, result: User) -> User:
        CreateUserWithHooks._after_called = True
        return result

    def execute(self) -> User:
        return User(id=1, name=self.inputs.name, email=self.inputs.email)


class CreateUserWithBeforeError(Command[CreateUserInputs, User]):
    """Command that errors in before_execute"""

    def before_execute(self) -> None:
        self.add_runtime_error('unauthorized', 'Not authorized to create users')

    def execute(self) -> User:
        return User(id=1, name=self.inputs.name, email=self.inputs.email)


class CreateUserWithAfterTransform(Command[CreateUserInputs, User]):
    """Command that transforms result in after_execute"""

    def after_execute(self, result: User) -> User:
        # Transform: uppercase the name
        return User(id=result.id, name=result.name.upper(), email=result.email)

    def execute(self) -> User:
        return User(id=1, name=self.inputs.name, email=self.inputs.email)


class CommandWithPossibleErrors(Command[CreateUserInputs, User]):
    """Command with possible errors declared"""

    _possible_errors = [
        ('email_taken', 'Email address is already in use'),
        ('invalid_domain', 'Email domain is not allowed'),
    ]

    def execute(self) -> User:
        if self.inputs.email.endswith('@blocked.com'):
            self.add_runtime_error('invalid_domain', 'Email domain is not allowed')
            return None
        return User(id=1, name=self.inputs.name, email=self.inputs.email)


class ValidateEmail(Command[ValidateEmailInputs, bool]):
    """Subcommand for email validation"""

    def execute(self) -> bool:
        if '@' not in self.inputs.email:
            self.add_input_error(['email'], 'invalid_email', 'Invalid email format')
            return False
        return True


class CreateUserWithSubcommand(Command[CreateUserInputs, User]):
    """Command that uses subcommand"""

    def execute(self) -> User:
        # Run validation subcommand
        result = self.run_subcommand(ValidateEmail, email=self.inputs.email)
        if result is None:
            return None

        return User(id=1, name=self.inputs.name, email=self.inputs.email)


# ==================== Lifecycle Hook Tests ====================

class TestLifecycleHooks:
    def test_before_execute_called(self):
        """Test that before_execute is called before execute"""
        CreateUserWithHooks._before_called = False
        CreateUserWithHooks._after_called = False

        outcome = CreateUserWithHooks.run(name="John", email="john@example.com")

        assert outcome.is_success()
        assert CreateUserWithHooks._before_called
        assert CreateUserWithHooks._after_called

    def test_before_execute_error_stops_execution(self):
        """Test that errors in before_execute prevent execute from running"""
        outcome = CreateUserWithBeforeError.run(name="John", email="john@example.com")

        assert outcome.is_failure()
        errors = outcome.errors
        assert len(errors) == 1
        assert errors[0].symbol == 'unauthorized'

    def test_after_execute_transforms_result(self):
        """Test that after_execute can transform the result"""
        outcome = CreateUserWithAfterTransform.run(name="john", email="john@example.com")

        assert outcome.is_success()
        user = outcome.unwrap()
        assert user.name == "JOHN"  # Transformed to uppercase


# ==================== Possible Errors Tests ====================

class TestPossibleErrors:
    def test_possible_errors_class_method(self):
        """Test that possible_errors() returns declared errors"""
        errors = CommandWithPossibleErrors.possible_errors()

        assert len(errors) == 2
        assert errors[0] == {'symbol': 'email_taken', 'message': 'Email address is already in use'}
        assert errors[1] == {'symbol': 'invalid_domain', 'message': 'Email domain is not allowed'}

    def test_possible_errors_in_manifest(self):
        """Test that possible_errors appear in manifest"""
        manifest = CommandWithPossibleErrors.manifest()

        assert 'possible_errors' in manifest
        assert len(manifest['possible_errors']) == 2

    def test_possible_errors_empty_by_default(self):
        """Test that commands without _possible_errors return empty list"""
        errors = CreateUserWithHooks.possible_errors()
        assert errors == []


# ==================== Subcommand Tests ====================

class TestSubcommands:
    def test_subcommand_success(self):
        """Test that subcommand result is returned on success"""
        outcome = CreateUserWithSubcommand.run(name="John", email="john@example.com")

        assert outcome.is_success()
        user = outcome.unwrap()
        assert user.name == "John"

    def test_subcommand_errors_propagated(self):
        """Test that subcommand errors are propagated to parent"""
        outcome = CreateUserWithSubcommand.run(name="John", email="invalid-email")

        assert outcome.is_failure()
        errors = outcome.errors
        assert len(errors) == 1
        assert 'subcommand' in errors[0].context
        assert errors[0].context['subcommand'] == 'ValidateEmail'


# ==================== Entity Loading Tests ====================

class TestEntityLoading:
    @pytest.fixture(autouse=True)
    def setup_repository(self):
        """Setup in-memory repository for tests"""
        repo = InMemoryRepository()
        RepositoryRegistry.set_default(repo)

        # Create test user
        user = UserEntity(id=1, name="Test User", email="test@example.com")
        repo.save(user)

        yield

        RepositoryRegistry.clear()

    def test_entity_loaded_successfully(self):
        """Test that entity is loaded and accessible"""
        class UpdateUser(Command[UpdateUserInputs, UserEntity]):
            _loads = [load(UserEntity, from_input='user_id', into='user')]

            def execute(self) -> UserEntity:
                self.user.name = self.inputs.name
                return self.user

        outcome = UpdateUser.run(user_id=1, name="Updated Name")

        assert outcome.is_success()
        user = outcome.unwrap()
        assert user.name == "Updated Name"

    def test_entity_not_found_error(self):
        """Test error when required entity not found"""
        class UpdateUser(Command[UpdateUserInputs, UserEntity]):
            _loads = [load(UserEntity, from_input='user_id', into='user', required=True)]

            def execute(self) -> UserEntity:
                self.user.name = self.inputs.name
                return self.user

        outcome = UpdateUser.run(user_id=999, name="Updated Name")

        assert outcome.is_failure()
        errors = outcome.errors
        assert len(errors) == 1
        assert errors[0].symbol == 'not_found'

    def test_optional_entity_not_found(self):
        """Test that optional entity allows None"""
        class UpdateUserOptional(Command[UpdateUserInputs, str]):
            _loads = [load(UserEntity, from_input='user_id', into='user', required=False)]

            def execute(self) -> str:
                if hasattr(self, 'user') and self.user:
                    return self.user.name
                return "Not found"

        outcome = UpdateUserOptional.run(user_id=999, name="Test")

        assert outcome.is_success()
        assert outcome.unwrap() == "Not found"


# ==================== Async Command Tests ====================

class AsyncCreateUserInputs(BaseModel):
    name: str
    email: str


class AsyncUser(BaseModel):
    id: int
    name: str


class AsyncCommandWithHooks(AsyncCommand[AsyncCreateUserInputs, AsyncUser]):
    """Async command with lifecycle hooks"""

    _before_called = False
    _after_called = False

    async def before_execute(self) -> None:
        AsyncCommandWithHooks._before_called = True

    async def after_execute(self, result: AsyncUser) -> AsyncUser:
        AsyncCommandWithHooks._after_called = True
        return result

    async def execute(self) -> AsyncUser:
        return AsyncUser(id=1, name=self.inputs.name)


class TestAsyncLifecycleHooks:
    @pytest.mark.asyncio
    async def test_async_hooks_called(self):
        """Test that async lifecycle hooks are called"""
        AsyncCommandWithHooks._before_called = False
        AsyncCommandWithHooks._after_called = False

        outcome = await AsyncCommandWithHooks.run(name="John", email="john@example.com")

        assert outcome.is_success()
        assert AsyncCommandWithHooks._before_called
        assert AsyncCommandWithHooks._after_called

    @pytest.mark.asyncio
    async def test_async_possible_errors(self):
        """Test possible_errors on async commands"""
        class AsyncWithErrors(AsyncCommand[AsyncCreateUserInputs, AsyncUser]):
            _possible_errors = [('test_error', 'Test error message')]

            async def execute(self) -> AsyncUser:
                return AsyncUser(id=1, name=self.inputs.name)

        errors = AsyncWithErrors.possible_errors()
        assert len(errors) == 1
        assert errors[0]['symbol'] == 'test_error'
