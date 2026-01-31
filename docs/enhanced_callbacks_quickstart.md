# Enhanced Callbacks - Quick Start Guide

## 5-Minute Quick Start

### Basic Setup

```python
from foobara_py.core.callbacks_enhanced import (
    EnhancedCallbackRegistry,
    EnhancedCallbackExecutor
)
from foobara_py.core.state_machine import CommandState

# 1. Create registry
registry = EnhancedCallbackRegistry()

# 2. Register callbacks
def before_execute(command):
    print("About to execute")

registry.register("before", before_execute, transition="execute")

# 3. Create executor
executor = EnhancedCallbackExecutor(registry, command)

# 4. Execute with callbacks
result = executor.execute_transition(
    CommandState.VALIDATING,
    CommandState.EXECUTING,
    "execute",
    lambda: command.do_work()
)
```

## Callback Types

### Before Callbacks
Run before the action:

```python
def setup(command):
    command.prepare()

registry.register("before", setup, transition="execute")
```

### After Callbacks
Run after the action:

```python
def cleanup(command):
    command.finalize()

registry.register("after", cleanup, transition="execute")
```

### Around Callbacks
Wrap the action:

```python
def with_timing(command, proceed):
    start = time.time()
    result = proceed()  # Must call proceed()
    command.elapsed = time.time() - start
    return result

registry.register("around", with_timing, transition="execute")
```

### Error Callbacks
Handle exceptions:

```python
def handle_error(command, error):
    print(f"Error: {error}")
    command.rollback()

registry.register("error", handle_error)
```

## Conditional Matching

### Match by From State
```python
registry.register(
    "before",
    callback,
    from_state=CommandState.VALIDATING
)
```

### Match by To State
```python
registry.register(
    "before",
    callback,
    to_state=CommandState.EXECUTING
)
```

### Match by Transition
```python
registry.register(
    "before",
    callback,
    transition="execute"
)
```

### Match All Conditions
```python
registry.register(
    "before",
    callback,
    from_state=CommandState.VALIDATING,
    to_state=CommandState.EXECUTING,
    transition="execute"
)
```

## Priority Control

Lower priority number = runs earlier:

```python
registry.register("before", first_callback, priority=0)   # Runs 1st
registry.register("before", second_callback, priority=10)  # Runs 2nd
registry.register("before", third_callback, priority=20)   # Runs 3rd
```

## Common Patterns

### Timing/Profiling
```python
def with_timing(command, proceed):
    start = time.time()
    result = proceed()
    print(f"Took {time.time() - start:.2f}s")
    return result

registry.register("around", with_timing, transition="execute")
```

### Logging
```python
def log_before(command):
    logger.info(f"Executing {command.name}")

def log_after(command):
    logger.info(f"Completed {command.name}")

registry.register("before", log_before)
registry.register("after", log_after)
```

### Permission Checking
```python
def check_permissions(command):
    if not command.user.can_execute(command):
        raise PermissionError("Not authorized")

registry.register("before", check_permissions, priority=0)
```

### Transaction Management
```python
def with_transaction(command, proceed):
    command.begin_transaction()
    try:
        result = proceed()
        command.commit_transaction()
        return result
    except Exception:
        command.rollback_transaction()
        raise

registry.register("around", with_transaction)
```

### Caching
```python
def with_cache(command, proceed):
    key = command.cache_key()
    cached = cache.get(key)
    if cached:
        return cached

    result = proceed()
    cache.set(key, result)
    return result

registry.register("around", with_cache)
```

## Performance Optimization

### Pre-compile Common Transitions
```python
# Do this once after registering all callbacks
registry.precompile_common_transitions()
```

### Check Cache Performance
```python
stats = registry.get_cache_stats()
print(f"Hit rate: {stats['hit_rate']:.1f}%")
print(f"Compiled chains: {stats['compiled_chains']}")
```

## Complete Example

```python
from foobara_py.core.callbacks_enhanced import (
    EnhancedCallbackRegistry,
    EnhancedCallbackExecutor
)
from foobara_py.core.state_machine import CommandState
import time

class MyCommand:
    def __init__(self, name):
        self.name = name
        self.user = None
        self.execution_time = 0

    def can_execute(self):
        return self.user is not None

    def do_work(self):
        # Main logic here
        return "success"

# Setup registry
registry = EnhancedCallbackRegistry()

# Permission check
def check_permissions(command):
    if not command.can_execute():
        raise PermissionError("Not authorized")

# Timing
def with_timing(command, proceed):
    start = time.time()
    result = proceed()
    command.execution_time = time.time() - start
    return result

# Logging
def log_start(command):
    print(f"Starting {command.name}")

def log_end(command):
    print(f"Completed {command.name} in {command.execution_time:.2f}s")

# Error handling
def handle_error(command, error):
    print(f"Error in {command.name}: {error}")

# Register callbacks
registry.register("before", check_permissions, priority=0, transition="execute")
registry.register("before", log_start, priority=10, transition="execute")
registry.register("around", with_timing, transition="execute")
registry.register("after", log_end, transition="execute")
registry.register("error", handle_error)

# Pre-compile for performance
registry.precompile_common_transitions()

# Use it
command = MyCommand("test_command")
command.user = "admin"

executor = EnhancedCallbackExecutor(registry, command)
result = executor.execute_transition(
    CommandState.VALIDATING,
    CommandState.EXECUTING,
    "execute",
    lambda: command.do_work()
)

print(f"Result: {result}")
```

## Cheat Sheet

| What | Code |
|------|------|
| Register before | `registry.register("before", cb)` |
| Register after | `registry.register("after", cb)` |
| Register around | `registry.register("around", cb)` |
| Register error | `registry.register("error", cb)` |
| Set priority | `registry.register("before", cb, priority=0)` |
| Match transition | `registry.register("before", cb, transition="execute")` |
| Match from state | `registry.register("before", cb, from_state=State.X)` |
| Match to state | `registry.register("before", cb, to_state=State.X)` |
| Pre-compile | `registry.precompile_common_transitions()` |
| Cache stats | `registry.get_cache_stats()` |
| Execute | `executor.execute_transition(from, to, name, action)` |

## Around Callback Template

```python
def my_wrapper(command, proceed):
    # Setup code here
    # ...

    result = proceed()  # MUST call this

    # Teardown code here
    # ...

    return result  # MUST return this
```

## Error Callback Template

```python
def handle_error(command, error):
    # Both command and error are available
    print(f"Error: {error}")

    # Do cleanup, logging, etc.
    # ...

    # Don't need to return anything
    # Exception will be re-raised automatically
```

## Debugging Tips

### Check if callbacks registered
```python
print(f"Has callbacks: {registry.has_callbacks()}")
```

### Get callbacks for transition
```python
callbacks = registry.get_callbacks(
    "before",
    CommandState.VALIDATING,
    CommandState.EXECUTING,
    "execute"
)
print(f"Found {len(callbacks)} callbacks")
```

### Clear cache
```python
registry.clear_cache()
```

### Monitor performance
```python
stats = registry.get_cache_stats()
if stats['hit_rate'] < 80:
    print("Warning: Low cache hit rate")
    print(f"Consider pre-compiling: registry.precompile_common_transitions()")
```

## Next Steps

- Read full documentation: `docs/enhanced_callbacks.md`
- Run examples: `python examples/enhanced_callbacks_demo.py`
- Run tests: `pytest tests/test_callbacks_enhanced.py`
