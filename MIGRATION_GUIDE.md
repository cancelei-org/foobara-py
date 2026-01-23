# Foobara Migration Guide

This guide helps you migrate to foobara-py from different sources:
1. [Ruby Foobara → Python](#migrating-from-ruby-foobara)
2. [foobara-py V1 → V2](#migrating-from-v1-to-v2)

Last updated: 2026-01-21

---

## Migrating from Ruby Foobara

### Quick Reference: Ruby vs Python

| Concept | Ruby | Python |
|---------|------|--------|
| **Input Definition** | `inputs do ... end` DSL | Pydantic `BaseModel` |
| **Type System** | Foobara types | Pydantic types |
| **Result Type** | `result :type` | Generic type parameter |
| **Validation** | `possible_input_error` | Pydantic validators |
| **Dependencies** | `depends_on` | `Domain.depends_on()` |
| **Subcommands** | `run_subcommand!` | `run_subcommand_bang()` |
| **Error Handling** | `add_input_error` | `add_input_error()` |
| **Entity** | `foobara_model` | `EntityBase` + `@entity` |
| **Persistence** | ActiveRecord-style | Repository pattern |

### 1. Command Definition

**Ruby:**
```ruby
class CreateUser < Foobara::Command
  inputs do
    name :string, :required
    email :string, :required
    age :integer, default: 18
  end

  result :User

  def execute
    User.create!(
      name: inputs[:name],
      email: inputs[:email],
      age: inputs[:age]
    )
  end
end
```

**Python:**
```python
from pydantic import BaseModel, Field
from foobara_py import Command

class CreateUserInputs(BaseModel):
    name: str = Field(..., description="User's name")
    email: str = Field(..., description="Email address")
    age: int = 18

class User(BaseModel):
    id: int
    name: str
    email: str
    age: int

class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user"""

    def execute(self) -> User:
        # Access inputs via self.inputs
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )
```

### 2. Input Validation

**Ruby:**
```ruby
class CreateUser < Foobara::Command
  inputs do
    email :string, :required
  end

  possible_input_error :invalid_email, path: [:email]

  def execute
    unless valid_email?(inputs[:email])
      add_input_error(:email, :invalid_email, "Invalid email format")
      halt!
    end
    # ...
  end
end
```

**Python:**
```python
from pydantic import BaseModel, field_validator, Field

class CreateUserInputs(BaseModel):
    email: str = Field(..., description="Email address")

    @field_validator('email')
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v

class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user"""

    def execute(self) -> User:
        # Email already validated by Pydantic
        # Add custom business logic validation if needed
        if email_exists(self.inputs.email):
            self.add_input_error(
                ["email"],
                "email_taken",
                "Email already in use"
            )
            return None  # Signals failure
        # ...
```

### 3. Domain Organization

**Ruby:**
```ruby
module MyApp
  module Users
    foobara_domain!

    class CreateUser < Foobara::Command
      # ...
    end
  end
end
```

**Python:**
```python
from foobara_py import Domain

users = Domain("Users", organization="MyApp")

@users.command
class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user"""
    # ...
```

### 4. Domain Dependencies

**Ruby:**
```ruby
module Billing
  foobara_domain!
  depends_on :Users

  class CreateInvoice < Foobara::Command
    def execute
      user = run_subcommand!(Users::GetUser, user_id: inputs[:user_id])
      # ...
    end
  end
end
```

**Python:**
```python
billing = Domain("Billing", organization="MyApp")
billing.depends_on("Users")  # Declare dependency

@billing.command
class CreateInvoice(Command[CreateInvoiceInputs, Invoice]):
    def execute(self) -> Invoice:
        # run_subcommand_bang automatically validates domain dependencies
        user = self.run_subcommand_bang(GetUser, user_id=self.inputs.user_id)
        # ...
```

### 5. Entities

**Ruby:**
```ruby
class User < Foobara::Model
  attributes do
    id :integer, :required
    name :string, :required
    email :string, :required
  end

  primary_key :id
end

user = User.create(name: "John", email: "john@example.com")
user.save!
```

**Python:**
```python
from foobara_py.persistence import EntityBase, entity, InMemoryRepository
from typing import Optional

@entity(primary_key='id')
class User(EntityBase):
    id: Optional[int] = None
    name: str
    email: str

# Set up repository
repo = InMemoryRepository()
RepositoryRegistry.register(User, repo)

# Create and save
user = User(name="John", email="john@example.com")
saved_user = repo.save(user)
```

### 6. Subcommands

**Ruby:**
```ruby
class OuterCommand < Foobara::Command
  def execute
    # Without error propagation
    outcome = run_subcommand(InnerCommand, value: 10)
    return unless outcome.success?
    result = outcome.result

    # With error propagation (Ruby's ! convention)
    result = run_subcommand!(InnerCommand, value: 10)

    # Process result
    result * 2
  end
end
```

**Python:**
```python
class OuterCommand(Command[OuterInputs, int]):
    def execute(self) -> int:
        # Without error propagation
        outcome = self.run_subcommand(InnerCommand, value=10)
        if outcome.is_failure():
            # Handle errors manually
            return None
        result = outcome.unwrap()

        # With error propagation (Python's _bang convention)
        result = self.run_subcommand_bang(InnerCommand, value=10)

        # Process result
        return result * 2
```

### 7. Async Commands

**Ruby:**
```ruby
# Ruby doesn't have AsyncCommand - uses threads/fibers
class FetchData < Foobara::Command
  def execute
    # Blocking I/O
    HTTP.get("https://api.example.com/data")
  end
end
```

**Python:**
```python
from foobara_py import AsyncCommand

class FetchData(AsyncCommand[FetchInputs, DataResult]):
    """Async command for I/O-bound operations"""

    async def execute(self) -> DataResult:
        # Non-blocking I/O
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com/data")
            return DataResult.parse_obj(response.json())

# Run async command
outcome = await FetchData.run(...)
```

### 8. Error Handling

**Ruby:**
```ruby
class MyCommand < Foobara::Command
  possible_errors do
    error :not_found, "Resource not found"
    error :invalid_input, "Invalid input data"
  end

  def execute
    add_runtime_error(:not_found, "User not found")
    # halt! is implicit
  end
end
```

**Python:**
```python
class MyCommand(Command[MyInputs, MyResult]):
    _possible_errors = [
        ('not_found', 'Resource not found'),
        ('invalid_input', 'Invalid input data'),
    ]

    def execute(self) -> MyResult:
        self.add_runtime_error(
            "not_found",
            "User not found",
            halt=True  # Raises Halt exception
        )
        return None  # Never reached due to halt
```

### 9. Lifecycle Hooks

**Ruby:**
```ruby
class CreateUser < Foobara::Command
  def before_execute
    log("Starting user creation")
  end

  def after_execute(result)
    log("User created: #{result.id}")
    result
  end
end
```

**Python:**
```python
from foobara_py.core.callbacks import before_execute, after_execute

class CreateUser(Command[CreateUserInputs, User]):
    @before_execute()
    def log_start(self):
        print("Starting user creation")

    @after_execute()
    def log_finish(self):
        print(f"User created: {self._result.id}")

    def execute(self) -> User:
        return User(id=1, name=self.inputs.name, email=self.inputs.email)
```

### 10. MCP Integration (Python-Specific)

Python has first-class MCP (Model Context Protocol) support for AI integration:

```python
from foobara_py.connectors.mcp import MCPConnector

# Create MCP server
connector = MCPConnector(name="UserService", version="1.0.0")

# Connect entire domain
connector.connect(users_domain)

# Or connect individual commands
connector.connect(CreateUser)

# Run as MCP server
connector.run_stdio()
```

Configure in Claude Desktop:
```json
{
  "mcpServers": {
    "user-service": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "myapp.mcp_server"]
    }
  }
}
```

### Key Differences Summary

#### Type System
- **Ruby**: Custom Foobara type system with DSL
- **Python**: Pydantic models (more Pythonic, better IDE support)

#### Validation
- **Ruby**: Inline validators and `possible_input_error` DSL
- **Python**: Pydantic `@field_validator` decorators + custom `validate()` method

#### Entities
- **Ruby**: ActiveRecord-style with auto-persistence
- **Python**: Repository pattern with explicit save/load

#### Async
- **Ruby**: Thread-based concurrency
- **Python**: async/await with `AsyncCommand`

#### Error Propagation
- **Ruby**: `run_subcommand!` with `!` suffix
- **Python**: `run_subcommand_bang()` or `run_subcommand_()` methods

---

## Migrating from V1 to V2

foobara-py V2 is a major refactoring that improves architecture, adds features, and achieves 95% Ruby parity. V1 code is deprecated but still available in `foobara_py._deprecated/`.

### Breaking Changes

#### 1. Import Paths

**V1:**
```python
from foobara_py.core.command import Command
from foobara_py.core.outcome import Outcome
```

**V2:**
```python
from foobara_py import Command
from foobara_py.core.outcome import CommandOutcome
```

#### 2. Outcome API

**V1:**
```python
outcome = MyCommand.run(**inputs)

if outcome.success:
    result = outcome.value
else:
    errors = outcome.errors
```

**V2:**
```python
outcome = MyCommand.run(**inputs)

if outcome.is_success():
    result = outcome.unwrap()
elif outcome.is_failure():
    errors = outcome.errors
```

#### 3. Error Handling

**V1:**
```python
class MyCommand(Command):
    def execute(self):
        if error_condition:
            self.errors.add("error_symbol", "Error message")
            return None
```

**V2:**
```python
class MyCommand(Command[MyInputs, MyResult]):
    def execute(self) -> MyResult:
        if error_condition:
            self.add_runtime_error(
                "error_symbol",
                "Error message",
                halt=True  # Automatically raises Halt
            )
            return None  # Never reached
```

#### 4. Domain Registration

**V1:**
```python
domain = Domain("Users")

class CreateUser(Command):
    _domain = domain  # Direct assignment
```

**V2:**
```python
domain = Domain("Users")

@domain.command  # Decorator-based registration
class CreateUser(Command[CreateUserInputs, User]):
    pass
```

#### 5. ErrorCollection API

**V1:**
```python
errors = ErrorCollection()
errors.add_error(error)        # Old method
errors.add_errors(err1, err2)  # Old method
```

**V2:**
```python
errors = ErrorCollection()
errors.add(error)         # New method
errors.add_all(err1, err2)  # New method

# Backward compatibility aliases still work:
errors.add_error(error)        # Works but deprecated
errors.add_errors(err1, err2)  # Works but deprecated
```

#### 6. Command State Machine

**V1:**
```python
# Simple state tracking
command.state  # "running", "success", "failed"
```

**V2:**
```python
# Full 8-state lifecycle
from foobara_py.core.state_machine import CommandState

command.state  # CommandState.EXECUTING, etc.
```

#### 7. Generic Type Parameters

**V1:**
```python
class MyCommand(Command):
    # No type parameters
    pass
```

**V2:**
```python
class MyCommand(Command[MyInputsModel, MyResultType]):
    """Fully typed with generics"""
    pass
```

### Migration Checklist

#### Phase 1: Update Imports
- [ ] Replace `from foobara_py.core.command import Command` with `from foobara_py import Command`
- [ ] Update `Outcome` to `CommandOutcome`
- [ ] Update domain import paths if using V1 paths

#### Phase 2: Update Command Definitions
- [ ] Add generic type parameters: `Command[InputT, ResultT]`
- [ ] Create Pydantic input models
- [ ] Add return type annotations to `execute()` methods
- [ ] Convert domain assignment to decorator pattern

#### Phase 3: Update Outcome Usage
- [ ] Replace `outcome.success` with `outcome.is_success()`
- [ ] Replace `outcome.value` with `outcome.unwrap()`
- [ ] Update error checking to use `outcome.is_failure()`

#### Phase 4: Update Error Handling
- [ ] Replace direct error collection manipulation with `add_runtime_error()`
- [ ] Add `halt=True` parameter for critical errors
- [ ] Update `add_input_error()` calls to use path arrays

#### Phase 5: Test Thoroughly
- [ ] Run full test suite
- [ ] Check for deprecation warnings
- [ ] Verify command execution
- [ ] Validate error handling
- [ ] Test domain dependencies

### Automatic Migration

We provide backward compatibility aliases for common V1 patterns:

```python
# These V1 patterns still work in V2:
from foobara_py import SimpleCommand  # V1-style command
errors.add_error(error)  # V1 ErrorCollection method
from foobara_py.connectors.mcp import JsonRpcError  # V1 alias
```

However, we recommend migrating to V2 APIs as V1 support will be removed in v0.4.0.

### Migration Example

**Before (V1):**
```python
from foobara_py.core.command import Command
from foobara_py.core.outcome import Outcome

class CreateUser(Command):
    def execute(self):
        if not self.inputs.get("email"):
            self.errors.add_error("missing_email", "Email is required")
            return None

        return {"id": 1, "email": self.inputs["email"]}

outcome = CreateUser.run(email="test@example.com")
if outcome.success:
    user = outcome.value
```

**After (V2):**
```python
from pydantic import BaseModel, Field
from foobara_py import Command

class CreateUserInputs(BaseModel):
    email: str = Field(..., description="User email")

class User(BaseModel):
    id: int
    email: str

class CreateUser(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        # Email validation automatic via Pydantic
        # self.inputs is guaranteed to have email
        return User(id=1, email=self.inputs.email)

outcome = CreateUser.run(email="test@example.com")
if outcome.is_success():
    user = outcome.unwrap()
```

### Getting Help

- **Documentation**: See README.md and inline code documentation
- **Examples**: See `tests/test_full_parity.py` for comprehensive examples
- **Issues**: https://github.com/foobara/foobara-py/issues
- **Ruby Comparison**: See `PARITY_CHECKLIST.md` for feature comparisons

### Deprecation Timeline

- **v0.2.x** (current): V1 deprecated but available in `foobara_py._deprecated/`
- **v0.3.x**: Deprecation warnings for V1 usage
- **v0.4.0**: V1 code removed

Migrate to V2 APIs as soon as possible to prepare for v0.4.0.

---

## Common Migration Patterns

### Pattern 1: Simple Command

**Ruby / V1:**
```ruby
class Add < Foobara::Command
  inputs do
    a :integer
    b :integer
  end

  result :integer

  def execute
    inputs[:a] + inputs[:b]
  end
end
```

**V2:**
```python
from pydantic import BaseModel
from foobara_py import Command

class AddInputs(BaseModel):
    a: int
    b: int

class Add(Command[AddInputs, int]):
    def execute(self) -> int:
        return self.inputs.a + self.inputs.b
```

### Pattern 2: Command with Validation

**Ruby:**
```ruby
class CreateUser < Foobara::Command
  inputs do
    email :string, :required
  end

  possible_input_error :invalid_email

  def execute
    unless valid_email?(inputs[:email])
      add_input_error(:email, :invalid_email)
      halt!
    end

    User.create!(email: inputs[:email])
  end
end
```

**V2:**
```python
from pydantic import BaseModel, field_validator

class CreateUserInputs(BaseModel):
    email: str

    @field_validator('email')
    def validate_email(cls, v):
        if not is_valid_email(v):
            raise ValueError("Invalid email format")
        return v

class CreateUser(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        # Email already validated
        return create_user(self.inputs.email)
```

### Pattern 3: Subcommand Execution

**Ruby:**
```ruby
class OuterCommand < Foobara::Command
  def execute
    inner_result = run_subcommand!(InnerCommand, value: 10)
    process(inner_result)
  end
end
```

**V2:**
```python
class OuterCommand(Command[OuterInputs, OuterResult]):
    def execute(self) -> OuterResult:
        inner_result = self.run_subcommand_bang(InnerCommand, value=10)
        return process(inner_result)
```

### Pattern 4: Entity CRUD

**Ruby:**
```ruby
user = User.find(1)
user.name = "New Name"
user.save!
```

**V2:**
```python
from foobara_py.persistence import RepositoryRegistry

repo = RepositoryRegistry.get_repository(User)
user = repo.find(User, 1)
user.name = "New Name"
repo.save(user)
```

### Pattern 5: Error Propagation

**Ruby:**
```ruby
outcome = MyCommand.run(value: 10)
if outcome.success?
  result = outcome.result
else
  outcome.errors.each { |error| puts error.message }
end
```

**V2:**
```python
outcome = MyCommand.run(value=10)
if outcome.is_success():
    result = outcome.unwrap()
else:
    for error in outcome.errors:
        print(error.message)
```

---

## Best Practices for Migration

### 1. Incremental Migration
Don't try to migrate everything at once. Start with:
1. Core command definitions
2. Domain organization
3. Error handling
4. Entity system
5. Advanced features

### 2. Use Type Hints
V2 is fully typed. Leverage this:
```python
from typing import Optional

class MyCommand(Command[MyInputs, MyResult]):
    def execute(self) -> MyResult:
        # Type hints help catch errors early
        result: Optional[MyResult] = None
        # ...
        return result
```

### 3. Leverage Pydantic
Pydantic provides powerful validation:
```python
from pydantic import BaseModel, Field, field_validator

class UserInputs(BaseModel):
    email: str = Field(..., pattern=r"^.+@.+\..+$")
    age: int = Field(ge=0, le=150)

    @field_validator('email')
    def normalize_email(cls, v):
        return v.lower().strip()
```

### 4. Test Everything
Write tests for your migrated code:
```python
def test_create_user():
    outcome = CreateUser.run(email="test@example.com")
    assert outcome.is_success()
    user = outcome.unwrap()
    assert user.email == "test@example.com"
```

### 5. Use Domain Dependencies
Explicitly declare domain dependencies:
```python
billing = Domain("Billing")
billing.depends_on("Users")
billing.depends_on("Products")

# Now billing commands can call users and products commands
```

---

## FAQ

### Q: Do I need to rewrite everything from scratch?
A: No. V1 code still works with backward compatibility. Migrate incrementally.

### Q: Will my Ruby Foobara manifests work?
A: Mostly yes. foobara-py generates compatible manifests. Some Python-specific features (like AsyncCommand) don't have Ruby equivalents.

### Q: Can I mix V1 and V2 code?
A: Yes, during migration. But aim to fully migrate to V2 for best results.

### Q: What about performance?
A: V2 is generally faster due to better architecture and Pydantic's performance.

### Q: How do I handle async in Ruby migrations?
A: Ruby uses threads/fibers. In Python, use `AsyncCommand` for I/O-bound operations.

### Q: Are there automated migration tools?
A: Not yet. But we provide backward compatibility and this guide to ease migration.

---

## Next Steps

1. Read the [PARITY_CHECKLIST.md](./PARITY_CHECKLIST.md) to understand feature coverage
2. Review [tests/test_full_parity.py](./tests/test_full_parity.py) for comprehensive examples
3. Check the [README.md](./README.md) for quick start guide
4. Run your existing tests to identify migration issues
5. Join the community for help and discussions

Happy migrating! 🚀
