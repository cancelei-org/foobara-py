# foobara-py

Python implementation of the Foobara command pattern with first-class MCP (Model Context Protocol) integration.

## Overview

foobara-py brings the elegance of Ruby's Foobara framework to Python, using:
- **Pydantic** for type validation and JSON Schema generation
- **Command Pattern** for encapsulating business logic
- **Outcome Pattern** for structured success/failure handling
- **MCP Integration** for exposing commands as AI-accessible tools

## Installation

```bash
pip install foobara-py

# With optional dependencies
pip install foobara-py[mcp]      # MCP integration
pip install foobara-py[agent]   # AI agent support
pip install foobara-py[http]    # FastAPI connector
pip install foobara-py[all]     # Everything
```

## Quick Start

### 1. Define Commands

```python
from pydantic import BaseModel, Field
from foobara_py import Command, Domain

# Create a domain
users = Domain("Users", organization="MyApp")

# Define input/output types
class CreateUserInputs(BaseModel):
    name: str = Field(..., description="User's name")
    email: str = Field(..., description="Email address")

class User(BaseModel):
    id: int
    name: str
    email: str

# Define command
@users.command
class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user account"""

    def execute(self) -> User:
        # Business logic here
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email
        )
```

### 2. Run Commands

```python
# Execute command
outcome = CreateUser.run(name="John", email="john@example.com")

if outcome.is_success():
    user = outcome.unwrap()
    print(f"Created: {user.name}")
else:
    for error in outcome.errors:
        print(f"Error: {error.message}")
```

### 3. Expose via MCP

```python
from foobara_py.connectors import MCPConnector

# Create MCP server
connector = MCPConnector(name="UserService", version="1.0.0")
connector.connect(users)  # Connect entire domain

# Run as MCP server
connector.run_stdio()
```

### 4. Configure in Claude/AI Client

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

## Core Concepts

### Commands

Commands encapsulate business logic with:
- **Typed inputs** (validated via Pydantic)
- **Structured outcomes** (Success/Failure, not exceptions)
- **Self-documentation** (JSON Schema for MCP tools)
- **Lifecycle hooks** (before/after execution)
- **Entity loading** (automatic entity resolution)
- **Subcommand support** (compose commands)

```python
class MyCommand(Command[InputsModel, ResultModel]):
    def execute(self) -> ResultModel:
        # Access inputs via self.inputs
        # Add errors via self.add_error()
        # Return result on success
        pass
```

### Lifecycle Hooks

Override `before_execute` and `after_execute` for cross-cutting concerns:

```python
class CreateUser(Command[CreateUserInputs, User]):
    def before_execute(self) -> None:
        """Runs before execute(). Errors here prevent execute() from running."""
        if not self.is_authorized():
            # Adding error with halt=True (default) raises Halt exception
            # execute() will NOT be called
            self.add_runtime_error('unauthorized', 'Not authorized')

    def after_execute(self, result: User) -> User:
        """Runs after execute() completes successfully."""
        # Post-processing, audit logging
        log_user_creation(result)
        return result

    def execute(self) -> User:
        return User(id=1, name=self.inputs.name, email=self.inputs.email)
```

### Entity Loading

Automatically load entities from input IDs:

```python
from foobara_py.persistence import load

class UpdateUser(Command[UpdateUserInputs, User]):
    _loads = [load(User, from_input='user_id', into='user', required=True)]

    def execute(self) -> User:
        self.user.name = self.inputs.name  # self.user is auto-loaded
        return self.user
```

### Possible Errors

Declare expected errors for documentation:

```python
class CreateUser(Command[CreateUserInputs, User]):
    _possible_errors = [
        ('email_taken', 'Email address is already in use'),
        ('invalid_domain', 'Email domain is not allowed'),
    ]

    def execute(self) -> User:
        if email_exists(self.inputs.email):
            self.add_runtime_error('email_taken', 'Email address is already in use')
            return None
        return User(...)
```

### Subcommands

Compose commands with automatic error propagation:

```python
class CreateUserWithValidation(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        # Run validation subcommand
        is_valid = self.run_subcommand(ValidateEmail, email=self.inputs.email)
        if is_valid is None:  # Subcommand failed
            return None

        return User(id=1, name=self.inputs.name, email=self.inputs.email)
```

### Outcomes

Outcomes avoid exception-based error handling:

```python
outcome = MyCommand.run(...)

# Check result
if outcome.is_success():
    result = outcome.unwrap()
elif outcome.is_failure():
    errors = outcome.errors
```

### Domains

Group related commands:

```python
billing = Domain("Billing", organization="MyApp")

@billing.command
class CreateInvoice(Command[...]):
    ...

@billing.command
class ProcessPayment(Command[...]):
    ...
```

### Error Handling

Structured errors with path tracking:

```python
from foobara_py.core import DataError

# In command execute()
self.add_error(DataError.data_error(
    symbol="invalid_format",
    path=["email"],
    message="Invalid email format"
))
```

## Connectors

### MCP Connector

Expose commands as MCP tools for AI assistants:

```python
from foobara_py.connectors import MCPConnector

connector = MCPConnector(name="MyService", version="1.0.0")
connector.connect(CreateUser)  # Single command
connector.connect(users_domain)  # Entire domain

connector.run_stdio()  # Run as stdio server
```

### MCP Resources

Expose read-only data via MCP resources:

```python
from foobara_py.connectors.mcp import MCPResource

# Static resource with custom loader
connector.add_resource(MCPResource(
    uri="foobara://config",
    name="Config",
    description="Application configuration",
    loader=lambda params: {"env": "production", "debug": False}
))

# Entity-backed resource with URI template
connector.add_entity_resource(User)  # Creates foobara://user/{id}

# Custom templated resource
connector.add_resource(MCPResource(
    uri="foobara://items/{category}/{id}",
    name="Item",
    description="Item by category and ID",
    loader=lambda params: load_item(params['category'], params['id'])
))
```

### CLI Connector

Generate CLI apps with Typer:

```python
from foobara_py.connectors import CLIConnector

cli = CLIConnector(name="myapp")
cli.connect(CreateUser, config=CommandCLIConfig(name="create-user"))
cli.run()  # python -m myapp create-user --name John --email john@example.com
```

### HTTP Connector

Expose commands via FastAPI:

```python
from foobara_py.connectors import HTTPConnector

http = HTTPConnector(name="MyAPI")
http.connect(CreateUser)  # POST /create-user

app = http.create_app()  # Returns FastAPI app
```

## Architecture

```
foobara_py/
├── core/
│   ├── command.py      # Command & AsyncCommand base classes
│   ├── outcome.py      # Success/Failure types
│   ├── errors.py       # Error types (DataError, InputError, etc.)
│   └── registry.py     # Command registry with JSON Schema generation
├── domain/
│   └── domain.py       # Domain/Organization grouping
├── connectors/
│   ├── mcp.py          # MCP connector with resources support
│   ├── http.py         # FastAPI HTTP connector
│   └── cli.py          # Typer CLI connector
├── persistence/
│   ├── entity.py       # EntityBase with dirty tracking
│   └── repository.py   # Repository pattern + transactions
└── types/
    └── base.py         # Custom type annotations
```

## Comparison with Ruby Foobara

| Concept | Ruby Foobara | foobara-py |
|---------|--------------|------------|
| Input Definition | `inputs do` DSL | Pydantic `BaseModel` |
| Type Validation | Processors | `@field_validator` |
| Result Handling | `Outcome` | `CommandOutcome` |
| Domains | Module nesting | `Domain` class |
| Lifecycle Hooks | `before/after` | `before_execute/after_execute` |
| Entity Loading | `depends_on` | `_loads` with `LoadSpec` |
| Possible Errors | `possible_error` | `_possible_errors` |
| MCP Integration | `foobara-mcp-connector` | Built-in `MCPConnector` |

## Migration Guides

Migrating to foobara-py? We have comprehensive guides:

- **[Ruby Foobara → Python](./MIGRATION_GUIDE.md#migrating-from-ruby-foobara)** - Complete guide for Ruby users
- **[V1 → V2](./MIGRATION_GUIDE.md#migrating-from-v1-to-v2)** - Upgrading from foobara-py V1

See [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) for detailed examples and patterns.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test file
pytest tests/test_command.py

# Run with verbose output
pytest -v
```

### Test Coverage

foobara-py uses pytest-cov for comprehensive test coverage reporting.

```bash
# Run tests with coverage report
pytest

# View detailed HTML coverage report
open htmlcov/index.html  # Opens coverage report in browser

# Generate coverage report without running tests
coverage report

# View missing lines for specific module
coverage report -m foobara_py/core/command.py
```

**Coverage Configuration** (pyproject.toml):
- Minimum threshold: 75% overall coverage
- Branch coverage enabled
- Reports: HTML (htmlcov/), JSON (coverage.json), terminal
- Excluded: `_deprecated/*`, `generators/templates/*`, `tests/*`

**Current Coverage**: 71.79% (982 tests passing)

Coverage gaps are tracked and addressed in the 95% Ruby parity roadmap.

## Status

**Beta** - Core functionality complete, ~80% Ruby parity.

### Implemented Features
- Command pattern with sync/async support
- Pydantic-based input validation
- Outcome pattern (Success/Failure)
- Lifecycle hooks (before_execute, after_execute)
- Entity loading with LoadSpec
- Subcommand support with error propagation
- Possible errors declaration
- MCP connector with tools and resources
- HTTP connector (FastAPI)
- CLI connector (Typer)
- Entity persistence with transactions
- 982 tests passing

### Remaining
- MCP prompts support
- Additional database drivers
- Performance benchmarks
- PyPI publication

## License

MPL-2.0 (matching Foobara Ruby)
