# Testing Guide for Foobara-py

This guide covers testing best practices, patterns, and utilities for foobara-py, inspired by Ruby's testing ecosystem (RSpec, factory_bot, etc.).

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Organization](#test-organization)
3. [Using Factories](#using-factories)
4. [Fixtures and Helpers](#fixtures-and-helpers)
5. [Property-Based Testing](#property-based-testing)
6. [Testing Patterns](#testing-patterns)
7. [Integration Testing](#integration-testing)
8. [Async Testing](#async-testing)
9. [Coverage Guidelines](#coverage-guidelines)

## Quick Start

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=foobara_py --cov-report=html

# Run specific test file
pytest tests/test_command.py

# Run specific test
pytest tests/test_command.py::TestCommand::test_run_success

# Run tests by marker
pytest -m unit  # Fast unit tests
pytest -m integration  # Integration tests
pytest -m slow  # Slow tests
```

### Writing Your First Test

```python
from foobara_py import Command
from pydantic import BaseModel
from tests.factories import CommandFactory
from tests.helpers import AssertionHelpers

def test_simple_command(test_domain):
    """Test a simple command execution"""
    # Create command using factory
    AddCommand = CommandFactory.create_simple_command(
        name="Add",
        domain=test_domain
    )

    # Run command
    outcome = AddCommand.run(value=5)

    # Assert success
    AssertionHelpers.assert_outcome_success(outcome, expected_result=10)
```

## Test Organization

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── factories.py             # Test factories (like factory_bot)
├── helpers.py               # Test helpers
├── property_strategies.py   # Hypothesis strategies
├── snapshots/               # Snapshot testing data
├── unit/                    # Unit tests
│   ├── test_command.py
│   ├── test_domain.py
│   └── test_entity.py
├── integration/             # Integration tests
│   ├── test_http_connector.py
│   └── test_persistence.py
└── e2e/                     # End-to-end tests
    └── test_workflows.py
```

### Test File Naming

- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Test Markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_fast_operation():
    """Fast unit test with no I/O"""
    pass

@pytest.mark.integration
def test_database_operation():
    """Test requiring database"""
    pass

@pytest.mark.slow
def test_expensive_operation():
    """Test that takes >1 second"""
    pass

@pytest.mark.asyncio
async def test_async_command():
    """Async test"""
    pass
```

## Using Factories

Factories provide a clean way to create test data with sensible defaults.

### Basic Factory Usage

```python
from tests.factories import UserFactory, ProductFactory

# Create with defaults
user = UserFactory.create()
# Result: User(id=1, username="user1", email="user1@test.com", ...)

# Override specific attributes
user = UserFactory.create(username="custom_user", email="custom@test.com")

# Build without saving (no repository interaction)
user = UserFactory.build(username="temp_user")

# Create multiple instances
users = UserFactory.create_batch(5)
# Result: [User1, User2, User3, User4, User5]
```

### Creating Custom Factories

```python
from tests.factories import EntityFactory
from decimal import Decimal

class InvoiceFactory(EntityFactory):
    """Factory for Invoice entities"""

    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        seq = cls._get_sequence('invoice')
        return {
            'id': None,
            'invoice_number': f"INV-{seq:05d}",
            'amount': Decimal('100.00'),
            'status': 'pending',
            'created_at': datetime.now(),
        }

# Usage
invoice = InvoiceFactory.create()
invoice = InvoiceFactory.create(amount=Decimal('500.00'))
```

### Command Factories

```python
from tests.factories import CommandFactory

# Create simple command
TestCmd = CommandFactory.create_simple_command(
    name="TestCommand",
    domain=my_domain
)

# Create command with validation
ValidatedCmd = CommandFactory.create_command_with_validation(
    name="ValidateEmail"
)

# Create async command
AsyncCmd = CommandFactory.create_async_command(
    name="AsyncOperation"
)

# Create command that works with entities
EntityCmd = CommandFactory.create_command_with_entity(
    name="CreateUser",
    entity_class=User,
    repository=user_repository
)
```

### Domain Factories

```python
from tests.factories import DomainFactory

# Create domain
domain = DomainFactory.create(name="Orders", organization="MyOrg")

# Create domain with commands
domain = DomainFactory.create_with_commands(command_count=5)
```

## Fixtures and Helpers

### Available Fixtures

Fixtures are automatically available in all tests via `conftest.py`.

#### Registry Fixtures

```python
def test_with_clean_registries(clean_registries):
    """Registries automatically cleaned before and after test"""
    # Your test code
    pass
```

#### Repository Fixtures

```python
def test_user_repository(user_repository):
    """Pre-configured user repository"""
    user = User(username="test", email="test@test.com")
    saved = user_repository.save(user)
    assert saved.id is not None

def test_with_multiple_repos(user_repository, product_repository):
    """Use multiple repositories"""
    user = UserFactory.create(repository=user_repository)
    product = ProductFactory.create(repository=product_repository)
```

#### Domain Fixtures

```python
def test_domain_commands(test_domain):
    """Pre-configured test domain"""
    @test_domain.command
    class MyCommand(Command[Inputs, Result]):
        def execute(self) -> Result:
            return result

def test_multiple_domains(multiple_domains):
    """Three test domains"""
    domain1, domain2, domain3 = multiple_domains
```

#### File System Fixtures

```python
def test_temp_directory(temp_dir):
    """Temporary directory, auto-cleaned after test"""
    file_path = temp_dir / "test.txt"
    file_path.write_text("test")
    assert file_path.exists()
```

#### Mock Data Fixtures

```python
def test_with_sample_data(sample_users, sample_products, sample_orders):
    """Pre-generated mock data"""
    assert len(sample_users) == 5
    assert len(sample_products) == 10
    assert len(sample_orders) == 20

def test_complete_dataset(complete_test_data):
    """Complete dataset with relationships"""
    users = complete_test_data['users']
    products = complete_test_data['products']
    orders = complete_test_data['orders']
```

### Using Test Helpers

```python
from tests.helpers import (
    HTTPTestHelper,
    DatabaseTestHelper,
    AsyncTestHelper,
    AssertionHelpers,
)

def test_http_endpoint():
    helper = HTTPTestHelper()
    helper.set_auth_header("my-token")
    response = helper.post_command("/api/users", {...})
    helper.assert_success(response)

def test_database_operations(in_memory_repository):
    helper = DatabaseTestHelper(in_memory_repository)
    helper.seed_data(User, [
        {'username': 'user1', 'email': 'user1@test.com'},
        {'username': 'user2', 'email': 'user2@test.com'},
    ])
    helper.assert_count(User, 2)

def test_command_assertions():
    outcome = MyCommand.run(value=10)
    AssertionHelpers.assert_outcome_success(outcome, expected_result=20)

    outcome = BadCommand.run(invalid_data="bad")
    AssertionHelpers.assert_outcome_failure(
        outcome,
        expected_error_symbol="validation_error"
    )
```

## Property-Based Testing

Property-based testing uses Hypothesis to generate hundreds of test cases automatically.

### Basic Property Tests

```python
from hypothesis import given
from tests.property_strategies import user_data, valid_email

@given(user_data())
def test_user_creation_with_any_data(data):
    """Test user creation with randomly generated data"""
    user = User(**data)
    assert user.username is not None
    assert '@' in user.email

@given(valid_email())
def test_email_validation(email):
    """Test email validation with various formats"""
    assert '@' in email
    assert '.' in email
```

### Using Custom Strategies

```python
from hypothesis import given
from tests.property_strategies import (
    entity_instance,
    command_inputs,
    e2e_user_workflow
)

@given(entity_instance(User))
def test_user_serialization(user):
    """Test user serialization with any valid user"""
    serialized = user.model_dump()
    deserialized = User(**serialized)
    assert deserialized.username == user.username

@given(command_inputs(CreateUserCommand))
def test_command_with_generated_inputs(inputs):
    """Test command with randomly generated inputs"""
    outcome = CreateUserCommand.run(**inputs)
    # Test invariants that should always hold
    if outcome.is_success():
        assert outcome.result.id is not None
```

### Testing Invariants

Property-based testing is excellent for testing invariants:

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.integers(), st.integers())
def test_command_idempotency(a, b):
    """Running command twice should give same result"""
    result1 = AddCommand.run(a=a, b=b).result
    result2 = AddCommand.run(a=a, b=b).result
    assert result1 == result2

@given(user_data())
def test_serialization_roundtrip(data):
    """Serialization should be lossless"""
    user = User(**data)
    serialized = user.model_dump()
    deserialized = User(**serialized)
    assert deserialized.model_dump() == user.model_dump()
```

## Testing Patterns

### Testing Commands

```python
class TestCreateUserCommand:
    """Test suite for CreateUser command"""

    def test_successful_creation(self, user_repository):
        """Test successful user creation"""
        outcome = CreateUser.run(
            username="newuser",
            email="new@test.com",
            password="secret123"
        )

        assert outcome.is_success()
        assert outcome.result.id is not None
        assert outcome.result.username == "newuser"

    def test_validation_error(self):
        """Test validation errors"""
        outcome = CreateUser.run(
            username="ab",  # Too short
            email="invalid",  # Invalid email
            password="123"  # Too short
        )

        assert outcome.is_failure()
        AssertionHelpers.assert_validation_error(
            outcome,
            field_path=["email"],
            error_symbol="invalid_email"
        )

    def test_duplicate_username(self, user_repository):
        """Test duplicate username handling"""
        # Create first user
        UserFactory.create(username="duplicate", repository=user_repository)

        # Try to create duplicate
        outcome = CreateUser.run(
            username="duplicate",
            email="new@test.com",
            password="secret123"
        )

        assert outcome.is_failure()
```

### Testing Entities

```python
class TestUserEntity:
    """Test suite for User entity"""

    def test_entity_creation(self):
        """Test entity creation with valid data"""
        user = User(
            username="testuser",
            email="test@test.com",
            password_hash="hashed"
        )
        assert user.username == "testuser"
        assert user.is_active is True  # Default value

    def test_primary_key(self):
        """Test primary key access"""
        user = User(id=123, username="test", email="test@test.com")
        assert user.primary_key == 123

    def test_entity_persistence(self, user_repository):
        """Test entity persistence"""
        user = UserFactory.build(username="persist")
        assert not user.is_persisted

        saved = user_repository.save(user)
        assert saved.is_persisted
        assert saved.id is not None
```

### Testing Domains

```python
class TestDomain:
    """Test suite for domain functionality"""

    def test_domain_creation(self):
        """Test domain creation"""
        domain = Domain("Orders", organization="Shop")
        assert domain.name == "Orders"
        assert domain.full_name() == "Shop::Orders"

    def test_command_registration(self, test_domain):
        """Test command registration with domain"""
        @test_domain.command
        class MyCommand(Command[Inputs, Result]):
            def execute(self) -> Result:
                return result

        assert MyCommand._domain == test_domain.name
        assert MyCommand in test_domain.commands.values()
```

## Integration Testing

Integration tests verify that multiple components work together correctly.

### Database Integration

```python
@pytest.mark.integration
@pytest.mark.persistence
class TestUserPersistence:
    """Integration tests for user persistence"""

    def test_create_and_retrieve(self, user_repository):
        """Test creating and retrieving user from database"""
        # Create user
        user = UserFactory.create(
            username="integration_test",
            repository=user_repository
        )

        # Retrieve user
        found = user_repository.find_by_primary_key(user.id)
        assert found is not None
        assert found.username == "integration_test"

    def test_update_user(self, user_repository):
        """Test updating user in database"""
        user = UserFactory.create(repository=user_repository)
        original_id = user.id

        # Update
        user.username = "updated"
        updated = user_repository.save(user)

        assert updated.id == original_id
        assert updated.username == "updated"
```

### HTTP Integration

```python
@pytest.mark.integration
@pytest.mark.connectors
class TestHTTPConnector:
    """Integration tests for HTTP connector"""

    def test_command_via_http(self, fastapi_test_client, test_domain):
        """Test executing command via HTTP"""
        from foobara_py.connectors.http import HTTPConnector

        # Setup HTTP connector
        connector = HTTPConnector(test_domain)
        app = connector.create_app()

        # Make request
        response = fastapi_test_client.post(
            "/api/commands/MyCommand",
            json={"inputs": {"value": 10}}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
```

### Multi-Component Integration

```python
@pytest.mark.integration
class TestE2EWorkflow:
    """End-to-end workflow tests"""

    def test_user_order_workflow(
        self,
        user_repository,
        product_repository,
        order_repository
    ):
        """Test complete user order workflow"""
        # Create user
        user = UserFactory.create(repository=user_repository)

        # Create product
        product = ProductFactory.create(
            stock=100,
            repository=product_repository
        )

        # Create order
        order = OrderFactory.create(
            user_id=user.id,
            product_id=product.id,
            quantity=5,
            repository=order_repository
        )

        # Verify workflow
        assert order.user_id == user.id
        assert order.product_id == product.id

        # Verify all persisted
        assert user_repository.find_by_primary_key(user.id) is not None
        assert product_repository.find_by_primary_key(product.id) is not None
        assert order_repository.find_by_primary_key(order.id) is not None
```

## Async Testing

### Basic Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_command():
    """Test async command execution"""
    outcome = await AsyncCommand.run_async(value=10)
    assert outcome.is_success()
    assert outcome.result == 20

@pytest.mark.asyncio
async def test_concurrent_commands():
    """Test running multiple async commands concurrently"""
    from tests.helpers import AsyncTestHelper

    results = await AsyncTestHelper.gather_command_results(
        AsyncCommand,
        [
            {"value": 1},
            {"value": 2},
            {"value": 3},
        ]
    )

    assert len(results) == 3
    assert all(r.is_success() for r in results)
```

## Coverage Guidelines

### Target Coverage

- Overall: 85%+
- Core modules (command, domain, entity): 95%+
- Connectors: 80%+
- Generators: 75%+

### Checking Coverage

```bash
# Generate coverage report
pytest --cov=foobara_py --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Coverage for specific module
pytest --cov=foobara_py.core.command --cov-report=term-missing
```

### What to Test

**High Priority:**
- Command execution (success and failure paths)
- Input validation
- Entity persistence
- Domain registration
- Error handling
- Transaction behavior

**Medium Priority:**
- Serialization/deserialization
- Type transformations
- Authorization rules
- Connector functionality

**Lower Priority:**
- Utility functions
- Simple getters/setters
- Obvious delegations

### What NOT to Test

- Third-party library code
- Generated code
- Trivial property access
- Simple delegations with no logic

## Best Practices

1. **One assertion per test (when possible)**
   - Makes failures clearer
   - Easier to debug

2. **Use descriptive test names**
   ```python
   # Good
   def test_create_user_with_invalid_email_returns_validation_error():
       pass

   # Bad
   def test_user():
       pass
   ```

3. **Follow AAA pattern**
   ```python
   def test_something():
       # Arrange
       user = UserFactory.create()

       # Act
       outcome = UpdateUser.run(id=user.id, name="New Name")

       # Assert
       assert outcome.is_success()
   ```

4. **Use factories for data creation**
   - Don't manually create test data
   - Use factories for consistency

5. **Clean up after tests**
   - Use fixtures with cleanup
   - Leverage `conftest.py` auto-cleanup

6. **Test behavior, not implementation**
   - Focus on outcomes
   - Don't test internal details

7. **Use property-based testing for invariants**
   - Great for finding edge cases
   - Validates mathematical properties

## Troubleshooting

### Tests Running Slow

```bash
# Run only fast tests
pytest -m "not slow"

# Run in parallel
pytest -n auto

# Profile slow tests
pytest --durations=10
```

### Registry Pollution

```python
# Ensure clean_registries fixture is used
def test_something(clean_registries):
    # Test code
    pass
```

### Import Errors

```bash
# Install test dependencies
pip install -e ".[dev]"
```

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Factory Boy](https://factoryboy.readthedocs.io/) - Ruby factory_bot equivalent
- [Testing Best Practices](https://testdriven.io/blog/testing-best-practices/)
