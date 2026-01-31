# Callback DSL for Commands

This document describes the Ruby-like callback DSL that has been added to the Command class.

## Overview

The callback DSL provides a rich, declarative way to register callbacks that execute during command state transitions. It supports conditional execution based on:

- **Transition names** (e.g., "execute", "validate")
- **From states** (state being transitioned from)
- **To states** (state being transitioned to)
- **Priority** (execution order)

## Architecture

### Components

1. **EnhancedCallbackRegistry** (`foobara_py/core/callbacks_enhanced.py`)
   - Stores registered callbacks with their conditions
   - Pre-compiles callback chains for performance
   - Provides fast lookup by transition parameters
   - Supports LRU caching for repeated lookups

2. **CallbacksConcern** (`foobara_py/core/command/concerns/callbacks_concern.py`)
   - Mixin providing the DSL methods
   - Class methods for registering callbacks
   - Integrated into Command base class

3. **EnhancedCallbackExecutor** (`foobara_py/core/callbacks_enhanced.py`)
   - Executes callbacks during state transitions
   - Handles before/after/around/error callback types
   - Supports callback chaining and nesting

## Usage

### Basic Registration

```python
from foobara_py.core.command import Command
from pydantic import BaseModel

class CreateUserInputs(BaseModel):
    name: str
    email: str

class User(BaseModel):
    id: int
    name: str

class CreateUser(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        return User(id=1, name=self.inputs.name)

# Register callbacks
def check_permissions(cmd):
    if not cmd.inputs.can_create:
        cmd.add_error("forbidden", "Not allowed")

CreateUser.before_execute_transition(check_permissions)
```

### Callback Types

#### 1. Transition-Specific Callbacks

Register callbacks for specific transition names:

```python
# Execute transition
CreateUser.before_execute_transition(callback)
CreateUser.after_execute_transition(callback)
CreateUser.around_execute_transition(callback)

# Validate transition
CreateUser.before_validate_transition(callback)
CreateUser.after_validate_transition(callback)

# Other transitions
CreateUser.before_cast_and_validate_inputs(callback)
CreateUser.after_load_records(callback)
CreateUser.before_commit_transaction(callback)
```

#### 2. Any Transition Callbacks

Run for ALL state transitions:

```python
def log_all_transitions(cmd):
    print(f"State: {cmd.state_name}")

CreateUser.before_any_transition(log_all_transitions)
CreateUser.after_any_transition(log_all_transitions)
CreateUser.around_any_transition(log_all_transitions)
```

#### 3. From-State Callbacks

Run when transitioning FROM a specific state:

```python
from foobara_py.core.state_machine import CommandState

def on_leaving_init(cmd):
    print("Leaving initialized state")

CreateUser.before_transition_from(CommandState.INITIALIZED, on_leaving_init)

# Convenience methods
CreateUser.before_transition_from_initialized(callback)
CreateUser.before_transition_from_executing(callback)
```

#### 4. To-State Callbacks

Run when transitioning TO a specific state:

```python
def on_success(cmd):
    print(f"Success: {cmd._result}")

CreateUser.before_transition_to(CommandState.SUCCEEDED, on_success)

# Convenience methods
CreateUser.before_transition_to_succeeded(callback)
CreateUser.before_transition_to_failed(callback)
```

#### 5. Combined Conditions

Specify multiple conditions for fine-grained control:

```python
def specific_callback(cmd):
    print("Execute transition from validating state")

CreateUser.before_transition(
    specific_callback,
    from_state=CommandState.VALIDATING,
    to_state=CommandState.EXECUTING,
    transition="execute"
)
```

### Around Callbacks

Around callbacks wrap the core action and can control execution:

```python
def time_execution(cmd, proceed):
    import time
    start = time.time()

    # Call the wrapped action
    result = proceed()

    elapsed = time.time() - start
    print(f"Took {elapsed*1000:.2f}ms")
    return result

CreateUser.around_execute_transition(time_execution)
```

### Priority Control

Lower priority numbers execute earlier:

```python
CreateUser.before_execute_transition(first_callback, priority=0)   # Runs first
CreateUser.before_execute_transition(second_callback, priority=50)  # Runs second
CreateUser.before_execute_transition(third_callback, priority=100) # Runs third
```

## Available DSL Methods

### Transition-Specific

- `before_execute_transition(callback, priority=0)`
- `after_execute_transition(callback, priority=0)`
- `around_execute_transition(callback, priority=0)`
- `before_validate_transition(callback, priority=0)`
- `after_validate_transition(callback, priority=0)`
- `around_validate_transition(callback, priority=0)`
- `before_cast_and_validate_inputs(callback, priority=0)`
- `after_cast_and_validate_inputs(callback, priority=0)`
- `around_cast_and_validate_inputs(callback, priority=0)`
- `before_load_records(callback, priority=0)`
- `after_load_records(callback, priority=0)`
- `before_validate_records(callback, priority=0)`
- `after_validate_records(callback, priority=0)`
- `before_open_transaction(callback, priority=0)`
- `after_open_transaction(callback, priority=0)`
- `before_commit_transaction(callback, priority=0)`
- `after_commit_transaction(callback, priority=0)`

### Any Transition

- `before_any_transition(callback, priority=0)`
- `after_any_transition(callback, priority=0)`
- `around_any_transition(callback, priority=0)`

### From/To State

- `before_transition_from(state, callback, priority=0)`
- `after_transition_from(state, callback, priority=0)`
- `around_transition_from(state, callback, priority=0)`
- `before_transition_to(state, callback, priority=0)`
- `after_transition_to(state, callback, priority=0)`
- `around_transition_to(state, callback, priority=0)`

### Convenience Methods

- `before_transition_from_initialized(callback, priority=0)`
- `after_transition_from_initialized(callback, priority=0)`
- `before_transition_from_executing(callback, priority=0)`
- `after_transition_from_executing(callback, priority=0)`
- `before_transition_to_succeeded(callback, priority=0)`
- `after_transition_to_succeeded(callback, priority=0)`
- `before_transition_to_failed(callback, priority=0)`
- `after_transition_to_failed(callback, priority=0)`
- `before_transition_from_initialized_to_executing(callback, priority=0)`
- `after_transition_from_initialized_to_executing(callback, priority=0)`

### Generic

- `before_transition(callback, from_state=None, to_state=None, transition=None, priority=0)`
- `after_transition(callback, from_state=None, to_state=None, transition=None, priority=0)`
- `around_transition(callback, from_state=None, to_state=None, transition=None, priority=0)`

## Implementation Details

### Callback Matching

Callbacks are matched against transitions using the `CallbackCondition` class:

```python
@dataclass(frozen=True, slots=True)
class CallbackCondition:
    from_state: Optional[CommandState] = None
    to_state: Optional[CommandState] = None
    transition: Optional[str] = None

    def matches(self, from_state, to_state, transition) -> bool:
        # Returns True if all non-None conditions match
        ...
```

### Performance Optimizations

1. **Pre-compiled chains**: Callback chains are compiled at class definition time
2. **LRU caching**: Repeated lookups are cached for fast retrieval
3. **Fast-path optimization**: Zero overhead when no callbacks are registered
4. **Priority sorting**: Callbacks are sorted once at registration time

### Registry Inheritance

Callback registries are merged during class inheritance:

```python
class BaseCommand(Command):
    pass

BaseCommand.before_execute_transition(base_callback)

class DerivedCommand(BaseCommand):
    pass

DerivedCommand.before_execute_transition(derived_callback)

# DerivedCommand has both base_callback and derived_callback
```

## Examples

See `examples/callback_dsl_example.py` for a comprehensive demonstration of all callback types and patterns.

## Testing

Run tests with:

```bash
pytest tests/test_callback_dsl.py -v
```

## Naming Conventions

Note the use of `_transition` suffix for callback registration methods:

- ✅ `before_execute_transition(callback)` - Registers callback for execute transition
- ❌ `before_execute(callback)` - Reserved for instance method (lifecycle hook)

This avoids conflicts with the instance methods `before_execute()` and `after_execute()` in ExecutionConcern, which are lifecycle hooks that can be overridden in subclasses.

## Migration Guide

If you were using the old decorator-based callback system:

### Before

```python
from foobara_py.core.callbacks import before, CallbackPhase

class MyCommand(Command):
    @before(CallbackPhase.EXECUTE)
    def check_permissions(self):
        ...
```

### After

```python
class MyCommand(Command):
    pass

def check_permissions(cmd):
    ...

MyCommand.before_execute_transition(check_permissions)
```

Both patterns are supported and can coexist.
