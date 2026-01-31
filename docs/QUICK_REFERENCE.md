# Foobara-py Quick Reference

One-page cheat sheet for common patterns and code snippets.

## Table of Contents

- [Create a Command](#create-a-command)
- [Run Commands](#run-commands)
- [Input Validation](#input-validation)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Type System](#type-system)
- [Lifecycle Hooks](#lifecycle-hooks)
- [Subcommands](#subcommands)
- [Entities](#entities)
- [Connectors](#connectors)

---

## Create a Command

### Basic Command

```python
from pydantic import BaseModel
from foobara_py import Command

class MyInputs(BaseModel):
    name: str
    age: int

class MyCommand(Command[MyInputs, str]):
    def execute(self) -> str:
        return f"{self.inputs.name} is {self.inputs.age}"
```

### With Domain

```python
from foobara_py import Domain

users = Domain("Users", organization="MyApp")

@users.command
class CreateUser(Command[UserInputs, User]):
    def execute(self) -> User:
        return User(**self.inputs.model_dump())
```

### Async Command

```python
from foobara_py import AsyncCommand

class FetchData(AsyncCommand[FetchInputs, dict]):
    async def execute(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.inputs.url)
            return response.json()
```

---

## Run Commands

### Basic Execution

```python
outcome = MyCommand.run(name="John", age=30)

if outcome.is_success():
    print(outcome.result)
else:
    for error in outcome.errors:
        print(error.message)
```

### Async Execution

```python
outcome = await MyCommand.run_async(...)
```

### Get Result or Raise

```python
result = outcome.unwrap()  # Raises if failure
```

---

## Input Validation

### Field Constraints

```python
from pydantic import BaseModel, Field, EmailStr

class UserInputs(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    email: EmailStr
    age: int = Field(ge=18, le=150)
    score: float = Field(ge=0.0, le=100.0)
```

### Optional Fields

```python
class Inputs(BaseModel):
    required_field: str
    optional_field: str | None = None
    with_default: str = "default value"
```

### Nested Models

```python
class Address(BaseModel):
    street: str
    city: str

class UserInputs(BaseModel):
    name: str
    address: Address
```

---

## Error Handling

### Add Errors in Command

```python
def execute(self) -> Result:
    if not valid:
        self.add_runtime_error(
            symbol="validation_failed",
            message="Validation failed",
            suggestion="Fix the input and try again"
        )
        return None
    return result
```

### Create Errors

```python
from foobara_py.core.errors import FoobaraError

error = FoobaraError.data_error(
    symbol="invalid_email",
    path=["user", "email"],
    message="Invalid email format",
    suggestion="Use format: user@example.com"
)
```

### Error Recovery

```python
from foobara_py.core.error_recovery import ErrorRecoveryManager, RetryConfig

manager = ErrorRecoveryManager()
manager.add_retry_hook(
    RetryConfig(
        max_attempts=3,
        initial_delay=0.1,
        backoff_multiplier=2.0
    )
)
```

---

## Testing

### Basic Test

```python
def test_my_command():
    outcome = MyCommand.run(name="test", age=25)
    assert outcome.is_success()
    assert outcome.result == "test is 25"
```

### Using Factories

```python
from tests.factories import UserFactory

def test_create_user():
    user = UserFactory.create(username="test")
    assert user.username == "test"
```

### Assertion Helpers

```python
from tests.helpers import AssertionHelpers

def test_command():
    outcome = MyCommand.run(...)
    AssertionHelpers.assert_outcome_success(
        outcome,
        expected_result="expected value"
    )
```

### Property-Based Testing

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.text(), st.integers())
def test_with_random_inputs(name, age):
    outcome = MyCommand.run(name=name, age=age)
    # Test invariants
```

---

## Type System

### Built-in Types

```python
from foobara_py.types import (
    EmailType,
    URLType,
    PositiveIntegerType,
    PercentageType,
)

email = EmailType.process("  USER@EXAMPLE.COM  ")
# Returns: "user@example.com"
```

### Custom Type

```python
from foobara_py.types import (
    FoobaraType,
    StringCaster,
    MinLengthValidator,
    LowercaseTransformer
)

username_type = FoobaraType(
    name="username",
    python_type=str,
    casters=[StringCaster()],
    transformers=[LowercaseTransformer()],
    validators=[MinLengthValidator(3)]
)
```

### Use in Pydantic

```python
class Inputs(BaseModel):
    email: EmailStr  # Pydantic type
    username: str = Field(min_length=3)
```

---

## Lifecycle Hooks

### Before/After Execute

```python
class MyCommand(Command[Inputs, Result]):
    def before_execute(self) -> None:
        # Runs before execute()
        if not self.is_authorized():
            self.add_runtime_error("unauthorized", "Not authorized")

    def after_execute(self, result: Result) -> Result:
        # Runs after execute()
        self.log_result(result)
        return result

    def execute(self) -> Result:
        return do_work()
```

### Decorators

```python
from foobara_py.core.callbacks import before, after

class MyCommand(Command[Inputs, Result]):
    @before
    def log_start(self):
        print("Starting...")

    @after
    def log_end(self, result):
        print(f"Done: {result}")

    def execute(self) -> Result:
        return do_work()
```

---

## Subcommands

### Run Subcommand

```python
class ParentCommand(Command[Inputs, Result]):
    def execute(self) -> Result:
        # Run subcommand
        result = self.run_subcommand(
            ChildCommand,
            input1=value1,
            input2=value2
        )

        if result is None:
            # Subcommand failed, errors auto-propagated
            return None

        # Continue with result
        return process(result)
```

### Run Multiple Subcommands

```python
def execute(self) -> Result:
    step1 = self.run_subcommand(ValidateInput, ...)
    if step1 is None:
        return None

    step2 = self.run_subcommand(ProcessData, data=step1)
    if step2 is None:
        return None

    return step2
```

---

## Entities

### Define Entity

```python
from foobara_py.persistence import EntityBase

class User(EntityBase):
    username: str
    email: str
    age: int
```

### Repository

```python
from foobara_py.persistence import InMemoryRepository

repo = InMemoryRepository(User)

# Save
user = User(username="john", email="john@example.com", age=30)
saved = repo.save(user)

# Find
found = repo.find_by_primary_key(saved.id)

# Query
all_users = repo.find_all()
```

### Entity Loading in Command

```python
from foobara_py.persistence import load

class UpdateUser(Command[UpdateInputs, User]):
    _loads = [load(User, from_input='user_id', into='user')]

    def execute(self) -> User:
        # self.user is auto-loaded
        self.user.username = self.inputs.new_username
        return self.user
```

---

## Connectors

### HTTP Connector

```python
from foobara_py.connectors import HTTPConnector

http = HTTPConnector(name="MyAPI")
http.connect(CreateUser)  # POST /create-user

app = http.create_app()  # FastAPI app

# Run with uvicorn
# uvicorn myapp:app
```

### CLI Connector

```python
from foobara_py.connectors import CLIConnector, CommandCLIConfig

cli = CLIConnector(name="myapp")
cli.connect(CreateUser, config=CommandCLIConfig(name="create-user"))

# Run: python -m myapp create-user --username john
cli.run()
```

### MCP Connector

```python
from foobara_py.connectors import MCPConnector

connector = MCPConnector(name="MyService", version="1.0.0")
connector.connect(users_domain)

# Run as MCP server
connector.run_stdio()
```

---

## Common Patterns

### Validation Pattern

```python
class CreateResource(Command[CreateInputs, Resource]):
    def execute(self) -> Resource:
        # Validate business rules
        if not self.is_valid():
            self.add_runtime_error("invalid", "Resource is invalid")
            return None

        # Create resource
        return Resource(**self.inputs.model_dump())
```

### Transaction Pattern

```python
from foobara_py.core.transactions import transaction

class TransferMoney(Command[TransferInputs, dict]):
    @transaction
    def execute(self) -> dict:
        # All or nothing
        from_account.withdraw(self.inputs.amount)
        to_account.deposit(self.inputs.amount)
        return {"status": "completed"}
```

### Authorization Pattern

```python
class DeleteResource(Command[DeleteInputs, bool]):
    def before_execute(self) -> None:
        if not self.current_user.is_admin():
            self.add_runtime_error(
                "forbidden",
                "Only admins can delete resources"
            )

    def execute(self) -> bool:
        delete_resource(self.inputs.resource_id)
        return True
```

### Retry Pattern

```python
from foobara_py.core.error_recovery import retry

class FetchExternalData(Command[FetchInputs, dict]):
    @retry(max_attempts=3, delay=1.0)
    def execute(self) -> dict:
        return fetch_from_api(self.inputs.url)
```

---

## Configuration

### Domain Setup

```python
from foobara_py import Domain, Organization

org = Organization("MyCompany")
users = Domain("Users", organization=org)
orders = Domain("Orders", organization=org)

# Domain dependencies
orders.depends_on(users)
```

### Registry Access

```python
from foobara_py.core.registry import CommandRegistry

# Get all commands
all_commands = CommandRegistry.all_commands()

# Get by name
cmd = CommandRegistry.get_command("CreateUser")

# Get JSON schema
schema = CommandRegistry.get_json_schema("CreateUser")
```

---

## Debugging

### Enable Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("foobara_py")
```

### Capture Stack Traces

```python
error = FoobaraError.runtime_error("error", "Something failed")
error.capture_stack_trace()
```

### Inspect Outcome

```python
outcome = MyCommand.run(...)

print(f"Success: {outcome.is_success()}")
print(f"Errors: {len(outcome.errors)}")
print(f"Result: {outcome.result}")

for error in outcome.errors:
    print(f"  - {error.symbol}: {error.message}")
    print(f"    Path: {error.path}")
    print(f"    Suggestion: {error.suggestion}")
```

---

## Performance Tips

### Cache Results

```python
from foobara_py.cache import cached

class ExpensiveCommand(Command[Inputs, Result]):
    @cached(ttl=3600)
    def execute(self) -> Result:
        return expensive_operation()
```

### Batch Operations

```python
def execute(self) -> list[Result]:
    # Process in batches
    results = []
    for batch in chunk(self.inputs.items, size=100):
        results.extend(process_batch(batch))
    return results
```

### Async for I/O

```python
class FetchMany(AsyncCommand[Inputs, list]):
    async def execute(self) -> list:
        async with httpx.AsyncClient() as client:
            tasks = [client.get(url) for url in self.inputs.urls]
            responses = await asyncio.gather(*tasks)
            return [r.json() for r in responses]
```

---

## See Also

- [Full Documentation](./FEATURES.md)
- [Getting Started](./GETTING_STARTED.md)
- [Testing Guide](./TESTING_GUIDE.md)
- [Type System Guide](./TYPE_SYSTEM_GUIDE.md)
- [Error Handling Guide](./ERROR_HANDLING.md)
