# Getting Started with Foobara-py

Welcome! This guide will get you up and running with foobara-py in just a few minutes. By the end, you'll know how to create commands, validate inputs, handle errors, and test your code.

## Table of Contents

1. [Installation](#installation)
2. [Your First Command](#your-first-command)
3. [Using the Type System](#using-the-type-system)
4. [Error Handling](#error-handling)
5. [Testing Your Commands](#testing-your-commands)
6. [Next Steps](#next-steps)

---

## Installation

### Basic Installation

```bash
pip install foobara-py
```

### With Optional Dependencies

```bash
# For MCP (AI assistant) integration
pip install foobara-py[mcp]

# For AI agent support
pip install foobara-py[agent]

# For HTTP/REST APIs
pip install foobara-py[http]

# For PostgreSQL persistence
pip install foobara-py[postgres]

# For Redis caching
pip install foobara-py[redis]

# Install everything
pip install foobara-py[all]
```

### For Development

```bash
# Clone the repository
git clone https://github.com/foobara/foobara-py.git
cd foobara-py

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests to verify
pytest
```

---

## Your First Command

Let's create a simple calculator command that adds two numbers.

### Step 1: Define Input Types

Create a Pydantic model for your inputs:

```python
from pydantic import BaseModel, Field

class AddInputs(BaseModel):
    """Inputs for the Add command"""
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")
```

### Step 2: Create the Command

```python
from foobara_py import Command, Domain

# Create a domain to organize commands
math = Domain("Math", organization="MyApp")

@math.command
class Add(Command[AddInputs, int]):
    """Add two numbers together"""

    def execute(self) -> int:
        """The business logic goes here"""
        return self.inputs.a + self.inputs.b
```

### Step 3: Run the Command

```python
# Run with keyword arguments
outcome = Add.run(a=5, b=3)

# Check if successful
if outcome.is_success():
    result = outcome.result
    print(f"Result: {result}")  # Result: 8
else:
    for error in outcome.errors:
        print(f"Error: {error.message}")
```

### Complete Example

```python
from pydantic import BaseModel, Field
from foobara_py import Command, Domain

# Define inputs
class AddInputs(BaseModel):
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")

# Create domain
math = Domain("Math", organization="MyApp")

# Create command
@math.command
class Add(Command[AddInputs, int]):
    """Add two numbers together"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b

# Use it
if __name__ == "__main__":
    outcome = Add.run(a=5, b=3)

    if outcome.is_success():
        print(f"5 + 3 = {outcome.result}")  # 5 + 3 = 8
```

That's it! You've created your first foobara-py command.

---

## Using the Type System

Foobara-py has a powerful type system that validates and transforms data automatically.

### Built-in Types

```python
from pydantic import BaseModel, EmailStr
from foobara_py.types import PositiveInt, Percentage

class CreateUserInputs(BaseModel):
    username: str  # Basic string
    email: EmailStr  # Validated email
    age: PositiveInt  # Must be > 0
    score: Percentage  # 0-100
```

### Custom Type Processing

Define types with validation and transformation pipelines:

```python
from foobara_py.types import (
    FoobaraType,
    StringCaster,
    EmailValidator,
    StripWhitespaceTransformer,
    LowercaseTransformer
)

# Create a custom email type
email_type = FoobaraType(
    name="email",
    python_type=str,
    casters=[StringCaster()],
    transformers=[
        StripWhitespaceTransformer(),
        LowercaseTransformer()
    ],
    validators=[EmailValidator()],
    description="Normalized email address"
)

# Process input
clean_email = email_type.process("  USER@EXAMPLE.COM  ")
print(clean_email)  # "user@example.com"
```

### Using Custom Types in Commands

```python
from pydantic import BaseModel
from foobara_py import Command

# Use the custom type
class SignUpInputs(BaseModel):
    # Email will be automatically normalized
    email: str

class SignUp(Command[SignUpInputs, dict]):
    def execute(self) -> dict:
        # self.inputs.email is already cleaned and validated
        return {
            "email": self.inputs.email,
            "status": "registered"
        }

# Example
outcome = SignUp.run(email="  JOHN@EXAMPLE.COM  ")
print(outcome.result)  # {"email": "john@example.com", "status": "registered"}
```

---

## Error Handling

Foobara-py uses a powerful error handling system instead of exceptions.

### Handling Validation Errors

```python
from pydantic import BaseModel, Field, EmailStr

class CreateUserInputs(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    email: EmailStr
    age: int = Field(ge=18, le=150)

class CreateUser(Command[CreateUserInputs, dict]):
    def execute(self) -> dict:
        return {
            "username": self.inputs.username,
            "email": self.inputs.email,
            "age": self.inputs.age
        }

# Invalid input
outcome = CreateUser.run(
    username="ab",  # Too short
    email="invalid",  # Not an email
    age=10  # Too young
)

if outcome.is_failure():
    for error in outcome.errors:
        print(f"Field: {error.path}")
        print(f"Error: {error.message}")
        print(f"Suggestion: {error.suggestion}")
        print("---")
```

### Adding Custom Errors

```python
class Withdraw(Command[WithdrawInputs, dict]):
    def execute(self) -> dict:
        account = get_account(self.inputs.account_id)

        # Check business rules
        if account.balance < self.inputs.amount:
            # Add an error instead of raising exception
            self.add_runtime_error(
                symbol="insufficient_balance",
                message=f"Insufficient balance: {account.balance}",
                suggestion="Reduce withdrawal amount or deposit funds"
            )
            return None  # Return None to signal failure

        # Continue with withdrawal
        account.balance -= self.inputs.amount
        return {"new_balance": account.balance}

# Use it
outcome = Withdraw.run(account_id=123, amount=1000)

if outcome.is_failure():
    for error in outcome.errors:
        print(f"Symbol: {error.symbol}")  # insufficient_balance
        print(f"Message: {error.message}")
        print(f"Suggestion: {error.suggestion}")
```

### Error Recovery

Implement retry logic and fallbacks:

```python
from foobara_py.core.error_recovery import ErrorRecoveryManager, RetryConfig

# Setup recovery manager
manager = ErrorRecoveryManager()
manager.add_retry_hook(
    RetryConfig(
        max_attempts=3,
        initial_delay=0.1,
        backoff_multiplier=2.0,
        retryable_symbols=["timeout", "connection_failed"]
    )
)

# Use in command
class FetchData(Command[FetchInputs, dict]):
    def execute(self) -> dict:
        try:
            return fetch_from_api(self.inputs.url)
        except TimeoutError:
            self.add_runtime_error(
                "timeout",
                "API request timed out",
                suggestion="Try again"
            )
            return None
```

---

## Testing Your Commands

Foobara-py provides powerful testing utilities.

### Basic Test

```python
import pytest
from tests.helpers import AssertionHelpers

def test_add_command():
    """Test the Add command"""
    # Run command
    outcome = Add.run(a=5, b=3)

    # Assert success
    AssertionHelpers.assert_outcome_success(outcome, expected_result=8)
```

### Using Factories

```python
from tests.factories import UserFactory, CommandFactory

def test_create_user():
    """Test user creation using factories"""
    # Create test data with defaults
    user_data = UserFactory.build()

    # Run command
    outcome = CreateUser.run(**user_data)

    # Verify
    assert outcome.is_success()
    assert outcome.result["username"] == user_data["username"]
```

### Testing Errors

```python
def test_validation_errors():
    """Test that validation errors are handled correctly"""
    # Invalid inputs
    outcome = CreateUser.run(
        username="a",  # Too short
        email="invalid",
        age=10
    )

    # Should fail
    assert outcome.is_failure()

    # Check specific errors
    errors = outcome.errors
    assert any(e.path == ["username"] for e in errors)
    assert any(e.path == ["email"] for e in errors)
    assert any(e.path == ["age"] for e in errors)
```

### Property-Based Testing

Find edge cases automatically:

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.integers(), st.integers())
def test_add_commutative(a, b):
    """Test that addition is commutative"""
    result1 = Add.run(a=a, b=b).result
    result2 = Add.run(a=b, b=a).result
    assert result1 == result2
```

---

## Next Steps

Congratulations! You now know the basics of foobara-py. Here's what to explore next:

### Learn More Features

1. **[Lifecycle Hooks](../README.md#lifecycle-hooks)** - Control execution flow
2. **[Subcommands](../README.md#subcommands)** - Compose commands
3. **[Entity System](../README.md#entity-loading)** - Work with persistent data
4. **[Async Commands](./ASYNC_COMMANDS.md)** - Handle async operations

### Deep Dive into Specific Topics

- **[Type System Guide](./TYPE_SYSTEM_GUIDE.md)** - Master custom types
- **[Error Handling Guide](./ERROR_HANDLING.md)** - Advanced error patterns
- **[Testing Guide](./TESTING_GUIDE.md)** - Comprehensive testing strategies

### Build Real Applications

- **[HTTP APIs](../README.md#http-connector)** - Expose commands via REST
- **[CLI Apps](../README.md#cli-connector)** - Build command-line tools
- **[MCP Integration](../README.md#mcp-connector)** - Make AI-accessible tools

### Explore Tutorials

Follow our step-by-step tutorial series:

1. [Basic Commands](./tutorials/01-basic-command.md)
2. [Input Validation](./tutorials/02-validation.md)
3. [Error Handling](./tutorials/03-error-handling.md)
4. [Testing Commands](./tutorials/04-testing.md)
5. [Subcommands](./tutorials/05-subcommands.md)
6. [Advanced Types](./tutorials/06-advanced-types.md)
7. [Performance](./tutorials/07-performance.md)

### Quick References

- **[Quick Reference](./QUICK_REFERENCE.md)** - One-page cheat sheet
- **[Feature Matrix](./FEATURE_MATRIX.md)** - Compare with alternatives
- **[Migration Guide](../MIGRATION_GUIDE.md)** - Migrate from other frameworks

### Get Help

- **[GitHub Issues](https://github.com/foobara/foobara-py/issues)** - Report bugs
- **[Discussions](https://github.com/foobara/foobara-py/discussions)** - Ask questions
- **[Examples](../examples/)** - See real code

---

## Common Patterns Cheat Sheet

### Create a Command

```python
from pydantic import BaseModel
from foobara_py import Command

class MyInputs(BaseModel):
    field: str

class MyCommand(Command[MyInputs, str]):
    def execute(self) -> str:
        return self.inputs.field.upper()
```

### Run a Command

```python
outcome = MyCommand.run(field="hello")
if outcome.is_success():
    print(outcome.result)
```

### Add Errors

```python
def execute(self) -> str:
    if not valid:
        self.add_runtime_error("invalid", "Not valid")
        return None
    return result
```

### Use Lifecycle Hooks

```python
def before_execute(self) -> None:
    # Runs before execute()
    self.log("Starting...")

def after_execute(self, result: str) -> str:
    # Runs after execute()
    self.log(f"Got result: {result}")
    return result
```

### Test a Command

```python
def test_my_command():
    outcome = MyCommand.run(field="test")
    assert outcome.is_success()
    assert outcome.result == "TEST"
```

---

## Tips for Success

1. **Start Simple**: Begin with basic commands, add complexity gradually
2. **Use Type Hints**: Enable IDE autocomplete and catch errors early
3. **Test Early**: Write tests as you build features
4. **Read Errors**: Error messages include helpful suggestions
5. **Check Examples**: Look at [examples/](../examples/) for patterns
6. **Ask Questions**: Don't hesitate to open GitHub discussions

---

## Troubleshooting

### Import Errors

```bash
# Make sure foobara-py is installed
pip install foobara-py

# For development
pip install -e ".[dev]"
```

### Type Checking Issues

```bash
# Install type stubs
pip install types-pydantic

# Run mypy
mypy your_code.py
```

### Test Failures

```bash
# Run specific test
pytest tests/test_command.py::test_name -v

# Run with output
pytest -v -s
```

---

Ready to build something awesome? Let's go!
