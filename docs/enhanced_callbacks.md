# Enhanced Callback System

The enhanced callback system provides Ruby-level flexibility with Python performance for command lifecycle hooks.

## Overview

The enhanced callback system offers:

- **Conditional callbacks**: Filter by state transitions (from/to/transition)
- **Multiple callback types**: before, after, around, error
- **High performance**: <2μs overhead for matching, <5μs for execution
- **Pre-compiled chains**: Cache callback chains for hot paths
- **Type safety**: Full type hints and autocomplete support

## Architecture

### Core Components

1. **CallbackCondition**: Defines when a callback should execute
2. **RegisteredCallback**: A callback with its conditions and metadata
3. **EnhancedCallbackRegistry**: High-performance registry with caching
4. **EnhancedCallbackExecutor**: Executes callbacks with proper ordering

### Class Hierarchy

```
CallbackCondition (frozen dataclass)
    ├─ from_state: Optional[CommandState]
    ├─ to_state: Optional[CommandState]
    └─ transition: Optional[str]

RegisteredCallback (dataclass)
    ├─ callback: Callable
    ├─ callback_type: str
    ├─ condition: CallbackCondition
    └─ priority: int

EnhancedCallbackRegistry
    ├─ _callbacks: List[RegisteredCallback]
    ├─ _compiled_chains: Dict[Tuple, Dict]
    └─ _cache_hits/misses: int

EnhancedCallbackExecutor
    ├─ _registry: EnhancedCallbackRegistry
    └─ _command: Command
```

## Usage

### Basic Callbacks

```python
from foobara_py.core.callbacks_enhanced import (
    EnhancedCallbackRegistry,
    EnhancedCallbackExecutor
)
from foobara_py.core.state_machine import CommandState

# Create registry
registry = EnhancedCallbackRegistry()

# Register before callback
def log_before(command):
    print(f"Before executing {command.name}")

registry.register("before", log_before, transition="execute")

# Register after callback
def log_after(command):
    print(f"After executing {command.name}")

registry.register("after", log_after, transition="execute")

# Create executor
executor = EnhancedCallbackExecutor(registry, command)

# Execute with callbacks
def action():
    return "result"

result = executor.execute_transition(
    CommandState.VALIDATING,
    CommandState.EXECUTING,
    "execute",
    action
)
```

### Around Callbacks

Around callbacks wrap the execution, allowing you to:
- Measure timing
- Add logging
- Modify results
- Handle setup/teardown

```python
def timing_wrapper(command, proceed):
    start = time.time()
    result = proceed()  # Call the next callback or action
    elapsed = time.time() - start
    command.execution_time = elapsed
    return result

registry.register("around", timing_wrapper, transition="execute")
```

Multiple around callbacks nest like middleware:

```python
registry.register("around", outer_wrapper, priority=1)
registry.register("around", inner_wrapper, priority=2)

# Execution order:
# outer_wrapper start
#   inner_wrapper start
#     action
#   inner_wrapper end
# outer_wrapper end
```

### Conditional Callbacks

Filter callbacks by state transitions:

```python
# Only when transitioning FROM a specific state
registry.register(
    "before",
    callback,
    from_state=CommandState.VALIDATING
)

# Only when transitioning TO a specific state
registry.register(
    "before",
    callback,
    to_state=CommandState.EXECUTING
)

# Only on a specific transition name
registry.register(
    "before",
    callback,
    transition="execute"
)

# All conditions must match
registry.register(
    "before",
    callback,
    from_state=CommandState.VALIDATING,
    to_state=CommandState.EXECUTING,
    transition="execute"
)
```

### Error Callbacks

Handle errors during transitions:

```python
def handle_error(command, error):
    print(f"Error: {error}")
    # Cleanup, logging, etc.

registry.register("error", handle_error)

# Error callbacks receive both command and exception
def specific_error_handler(command, error):
    if isinstance(error, ValueError):
        command.add_runtime_error("validation_failed", str(error))

registry.register("error", specific_error_handler, transition="validate")
```

### Priority Ordering

Control callback execution order with priorities (lower = higher priority):

```python
registry.register("before", first_callback, priority=0)
registry.register("before", second_callback, priority=10)
registry.register("before", third_callback, priority=20)

# Executes: first_callback → second_callback → third_callback
```

## Performance Optimization

### Pre-compilation

Pre-compile callback chains for hot paths:

```python
# Pre-compile common transitions at startup
registry.precompile_common_transitions()

# Or compile specific transitions
registry.compile_chain(
    CommandState.VALIDATING,
    CommandState.EXECUTING,
    "execute"
)
```

### Cache Statistics

Monitor cache performance:

```python
stats = registry.get_cache_stats()
print(f"Hit rate: {stats['hit_rate']:.1f}%")
print(f"Compiled chains: {stats['compiled_chains']}")
```

### Fast Path

The system automatically optimizes when no callbacks are registered:

```python
if not registry.has_callbacks():
    # Direct execution, no overhead
    return action()
```

## Performance Characteristics

Based on benchmarks:

- **Callback matching**: <2μs with compiled chains
- **Callback execution**: <5μs overhead per callback
- **Throughput**: >800,000 operations/second
- **Memory**: Minimal (uses `__slots__`)

### Optimization Techniques

1. **`__slots__`**: All classes use slots for memory efficiency
2. **Frozen dataclasses**: CallbackCondition is immutable and hashable
3. **Pre-compilation**: Cache callback chains at class definition time
4. **Priority sorting**: Callbacks sorted once at registration
5. **Fast-path**: Zero overhead when no callbacks registered

## Advanced Patterns

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

registry.register("around", with_transaction, transition="execute")
```

### Permission Checking

```python
def check_permissions(command):
    if not command.current_user.can_execute(command):
        raise PermissionError("Not authorized")

registry.register(
    "before",
    check_permissions,
    to_state=CommandState.EXECUTING,
    priority=0  # Run first
)
```

### Audit Logging

```python
def audit_log(command):
    log_entry = {
        "user": command.current_user.id,
        "command": command.__class__.__name__,
        "timestamp": time.time(),
        "result": command.result
    }
    audit.log(log_entry)

registry.register("after", audit_log, transition="execute")
```

### Caching

```python
def with_cache(command, proceed):
    cache_key = command.cache_key()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = proceed()
    cache.set(cache_key, result)
    return result

registry.register("around", with_cache, transition="execute")
```

## Integration with Command Classes

```python
class MyCommand(Command):
    def __init__(self):
        super().__init__()
        self._callback_registry = EnhancedCallbackRegistry()
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Setup callbacks for this command."""
        self._callback_registry.register(
            "before",
            self._check_permissions,
            to_state=CommandState.EXECUTING
        )
        self._callback_registry.register(
            "around",
            self._with_timing,
            transition="execute"
        )

        # Pre-compile for performance
        self._callback_registry.precompile_common_transitions()

    def _check_permissions(self):
        if not self.can_execute():
            raise PermissionError("Not authorized")

    def _with_timing(self, proceed):
        start = time.time()
        result = proceed()
        self.execution_time = time.time() - start
        return result

    def execute(self):
        executor = EnhancedCallbackExecutor(
            self._callback_registry,
            self
        )

        return executor.execute_transition(
            CommandState.VALIDATING,
            CommandState.EXECUTING,
            "execute",
            lambda: self._do_execute()
        )
```

## Comparison with Basic Callbacks

| Feature | Basic Callbacks | Enhanced Callbacks |
|---------|----------------|-------------------|
| Conditional matching | Phase only | State transitions + phase |
| Performance | ~10μs overhead | <2μs overhead |
| Pre-compilation | Manual | Automatic |
| Error handling | Limited | Full error callbacks |
| Around callbacks | Yes | Yes, with nesting |
| Type safety | Partial | Full type hints |
| Cache statistics | No | Yes |

## Best Practices

1. **Use pre-compilation**: Call `precompile_common_transitions()` after registration
2. **Set appropriate priorities**: Lower numbers run first
3. **Keep callbacks focused**: Each callback should do one thing
4. **Use conditions wisely**: More specific = better performance
5. **Monitor cache stats**: Check hit rate in production

## Debugging

### Enable logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Registry will log cache hits/misses
```

### Inspect registered callbacks

```python
# Check if callbacks are registered
print(f"Has callbacks: {registry.has_callbacks()}")

# Get cache statistics
stats = registry.get_cache_stats()
print(f"Cache stats: {stats}")

# Get callbacks for a transition
callbacks = registry.get_callbacks(
    "before",
    CommandState.VALIDATING,
    CommandState.EXECUTING,
    "execute"
)
print(f"Found {len(callbacks)} callbacks")
```

### Profile performance

```python
import time

def profile_transition():
    start = time.time()

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    elapsed = time.time() - start
    print(f"Transition took {elapsed*1000:.2f}ms")

    return result
```

## Future Enhancements

Potential improvements:

- Async callback support
- Callback groups/namespaces
- Conditional compilation based on usage patterns
- Callback dependency resolution
- Hot-reloading of callbacks

## See Also

- `state_machine.py` - Command state machine
- `callbacks.py` - Basic callback system
- `command/base.py` - Command base class
- Examples in `examples/enhanced_callbacks_demo.py`
