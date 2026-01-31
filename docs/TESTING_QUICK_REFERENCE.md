# Testing Quick Reference

Quick reference for foobara-py testing patterns.

## Quick Start

```python
# Test with factory
from tests.factories import UserFactory

def test_user(user_repository):
    user = UserFactory.create(repository=user_repository)
    assert user.id is not None

# Test with helpers
from tests.helpers import AssertionHelpers

def test_command():
    outcome = MyCommand.run(value=10)
    AssertionHelpers.assert_outcome_success(outcome, expected_result=20)

# Property-based test
from hypothesis import given
from tests.property_strategies import user_data

@given(user_data())
def test_user_invariant(data):
    user = User(**data)
    assert user.username is not None
```

## Factories

### Entity Factories

```python
from tests.factories import UserFactory, ProductFactory

# Create with defaults
user = UserFactory.create()

# Override attributes
user = UserFactory.create(username="custom", email="custom@test.com")

# Build without saving
user = UserFactory.build()

# Batch creation
users = UserFactory.create_batch(10)
```

### Command Factories

```python
from tests.factories import CommandFactory

# Simple command
TestCmd = CommandFactory.create_simple_command(name="Test", domain=domain)

# With validation
ValidCmd = CommandFactory.create_command_with_validation(name="Validate")

# With entity
EntityCmd = CommandFactory.create_command_with_entity(
    name="CreateUser",
    entity_class=User,
    repository=repo
)
```

### Domain Factories

```python
from tests.factories import DomainFactory

# Basic domain
domain = DomainFactory.create(name="Sales", organization="Acme")

# With commands
domain = DomainFactory.create_with_commands(command_count=5)
```

## Fixtures

### Repository Fixtures

```python
def test_with_repository(user_repository):
    # Pre-configured repository ready to use
    user = User(username="test", email="test@test.com")
    saved = user_repository.save(user)

def test_multiple_repos(user_repository, product_repository):
    # Multiple repositories
    pass
```

### Domain Fixtures

```python
def test_with_domain(test_domain):
    # Pre-configured test domain
    @test_domain.command
    class MyCommand(Command[Inputs, Result]):
        pass

def test_multiple_domains(multiple_domains):
    # Three test domains
    domain1, domain2, domain3 = multiple_domains
```

### Data Fixtures

```python
def test_with_data(sample_users, sample_products):
    # Pre-generated sample data
    assert len(sample_users) == 5
    assert len(sample_products) == 10

def test_complete_data(complete_test_data):
    # Full dataset with relationships
    users = complete_test_data['users']
    products = complete_test_data['products']
    orders = complete_test_data['orders']
```

## Helpers

### Assertion Helpers

```python
from tests.helpers import AssertionHelpers

# Success assertions
AssertionHelpers.assert_outcome_success(outcome)
AssertionHelpers.assert_outcome_success(outcome, expected_result=10)

# Failure assertions
AssertionHelpers.assert_outcome_failure(outcome)
AssertionHelpers.assert_outcome_failure(
    outcome,
    expected_error_symbol="validation_error"
)

# Validation error assertions
AssertionHelpers.assert_validation_error(
    outcome,
    field_path=["email"],
    error_symbol="invalid_email"
)

# Entity equality
AssertionHelpers.assert_entities_equal(
    entity1,
    entity2,
    exclude_fields=["created_at"]
)
```

### Database Helper

```python
from tests.helpers import DatabaseTestHelper

helper = DatabaseTestHelper(repository)

# Seed data
users = helper.seed_data(User, [
    {'username': 'user1', 'email': 'user1@test.com'},
    {'username': 'user2', 'email': 'user2@test.com'},
])

# Assertions
helper.assert_entity_exists(User, user_id)
helper.assert_entity_not_exists(User, 99999)
helper.assert_count(User, 5)

# Clear all
helper.clear_all()
```

### HTTP Test Helper

```python
from tests.helpers import HTTPTestHelper

helper = HTTPTestHelper()

# Set authentication
helper.set_auth_header("my-token")
helper.set_api_key("my-api-key")

# Make request
response = helper.post_command("/api/users", {"username": "test"})

# Assertions
helper.assert_success(response)
helper.assert_error(response, expected_error="validation_error")
```

### Async Test Helper

```python
from tests.helpers import AsyncTestHelper

# Run async command
outcome = await AsyncTestHelper.run_async_command(AsyncCmd, value=10)

# Run in sync context
result = AsyncTestHelper.run_async_in_sync(async_function())

# Gather results
results = await AsyncTestHelper.gather_command_results(
    AsyncCmd,
    [{"value": 1}, {"value": 2}, {"value": 3}]
)
```

### Command Composition Helper

```python
from tests.helpers import CommandCompositionHelper

helper = CommandCompositionHelper()

# Create tracked commands
Cmd1 = helper.create_tracked_command("First", lambda x: x + 1)
Cmd2 = helper.create_tracked_command("Second", lambda x: x * 2)

# Execute
Cmd1.run(value=5)
Cmd2.run(value=10)

# Verify
helper.assert_execution_order(["First", "Second"])
assert helper.get_execution_count("First") == 1
```

## Property-Based Testing

### Basic Strategies

```python
from hypothesis import given
from tests.property_strategies import (
    valid_email,
    valid_username,
    valid_phone,
    valid_password
)

@given(valid_email())
def test_email(email):
    assert '@' in email

@given(valid_username())
def test_username(username):
    assert 3 <= len(username) <= 30
```

### Entity Strategies

```python
from hypothesis import given
from tests.property_strategies import user_data, product_data

@given(user_data())
def test_user_creation(data):
    user = User(**data)
    assert user.username is not None

@given(product_data())
def test_product_creation(data):
    product = Product(**data)
    assert product.price >= 0
```

### Workflow Strategies

```python
from hypothesis import given
from tests.property_strategies import e2e_user_workflow

@given(e2e_user_workflow())
def test_complete_workflow(data):
    user = data['user']
    products = data['products']
    orders = data['orders']
    # Test workflow
```

## Test Markers

```python
import pytest

@pytest.mark.unit
def test_fast():
    """Fast unit test"""
    pass

@pytest.mark.integration
def test_database():
    """Integration test"""
    pass

@pytest.mark.slow
def test_expensive():
    """Slow test"""
    pass

@pytest.mark.asyncio
async def test_async():
    """Async test"""
    pass
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=foobara_py --cov-report=html

# Specific file
pytest tests/test_command.py

# Specific test
pytest tests/test_command.py::TestCommand::test_run_success

# By marker
pytest -m unit
pytest -m integration
pytest -m "not slow"

# Verbose
pytest -v

# Parallel
pytest -n auto

# Stop on first failure
pytest -x

# Show locals on failure
pytest -l

# Profile slow tests
pytest --durations=10
```

## Common Patterns

### Test Command Success

```python
def test_command_success(test_domain):
    # Arrange
    TestCmd = CommandFactory.create_simple_command(domain=test_domain)

    # Act
    outcome = TestCmd.run(value=10)

    # Assert
    AssertionHelpers.assert_outcome_success(outcome, expected_result=20)
```

### Test Command Failure

```python
def test_command_failure():
    # Arrange
    ValidateCmd = CommandFactory.create_command_with_validation()

    # Act
    outcome = ValidateCmd.run(email="invalid", age=25)

    # Assert
    AssertionHelpers.assert_outcome_failure(
        outcome,
        expected_error_symbol="invalid_email"
    )
```

### Test Entity Persistence

```python
def test_entity_persistence(user_repository):
    # Arrange
    UserFactory.entity_class = User
    user = UserFactory.create(repository=user_repository)

    # Act
    found = user_repository.find(User, user.id)

    # Assert
    assert found is not None
    assert found.username == user.username
```

### Test Integration

```python
@pytest.mark.integration
def test_workflow(user_repository, product_repository):
    # Arrange
    UserFactory.entity_class = User
    ProductFactory.entity_class = Product

    user = UserFactory.create(repository=user_repository)
    product = ProductFactory.create(repository=product_repository)

    # Act
    # ... perform workflow ...

    # Assert
    db_helper = DatabaseTestHelper(user_repository)
    db_helper.assert_entity_exists(User, user.id)
```

## Tips

1. **Use factories** for all data creation
2. **Use fixtures** for setup/teardown
3. **Use helpers** for common assertions
4. **Follow AAA** (Arrange, Act, Assert)
5. **Test behavior**, not implementation
6. **One assertion per test** (when possible)
7. **Descriptive test names**
8. **Property tests for invariants**
9. **Integration tests for workflows**
10. **Mock external dependencies**

## See Also

- [Full Testing Guide](TESTING_GUIDE.md) - Comprehensive documentation
- [Test Factories](../tests/factories.py) - Factory implementations
- [Test Helpers](../tests/helpers.py) - Helper implementations
- [Example Tests](../tests/test_factory_patterns.py) - Working examples
