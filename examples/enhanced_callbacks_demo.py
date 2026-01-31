"""
Enhanced Callback System Demo

Demonstrates Ruby-level flexibility with Python performance.
Shows how to use conditional callbacks with state transitions.
"""

import time
from typing import Any

from foobara_py.core.callbacks_enhanced import (
    EnhancedCallbackExecutor,
    EnhancedCallbackRegistry,
)
from foobara_py.core.state_machine import CommandState


class DemoCommand:
    """Demo command showing callback usage."""

    def __init__(self, name: str):
        self.name = name
        self.log = []
        self.start_time = None
        self.permissions_checked = False
        self.data_validated = False

    def add_log(self, message: str):
        """Add to execution log."""
        timestamp = time.time() - self.start_time if self.start_time else 0
        self.log.append(f"[{timestamp:.3f}s] {message}")

    def get_log(self) -> str:
        """Get formatted log."""
        return "\n".join(self.log)


def setup_logging_callbacks(registry: EnhancedCallbackRegistry):
    """Setup logging callbacks for all transitions."""

    def log_transition_start(cmd: DemoCommand):
        cmd.add_log(f"Starting transition")

    def log_transition_end(cmd: DemoCommand):
        cmd.add_log(f"Completed transition")

    # Log all transitions
    registry.register("before", log_transition_start, priority=0)
    registry.register("after", log_transition_end, priority=100)


def setup_timing_callbacks(registry: EnhancedCallbackRegistry):
    """Setup timing callbacks using around pattern."""

    def time_execution(cmd: DemoCommand, proceed):
        start = time.time()
        cmd.add_log("Starting timer")
        result = proceed()
        elapsed = time.time() - start
        cmd.add_log(f"Timer: {elapsed*1000:.2f}ms")
        return result

    # Time only the execute transition
    registry.register("around", time_execution, transition="execute", priority=1)


def setup_permission_callbacks(registry: EnhancedCallbackRegistry):
    """Setup permission checking before validation."""

    def check_permissions(cmd: DemoCommand):
        cmd.add_log("Checking permissions...")
        # Simulate permission check
        time.sleep(0.001)
        cmd.permissions_checked = True
        cmd.add_log("Permissions OK")

    # Check permissions before validating
    registry.register(
        "before",
        check_permissions,
        from_state=CommandState.CASTING_AND_VALIDATING_INPUTS,
        to_state=CommandState.LOADING_RECORDS,
        priority=5
    )


def setup_validation_callbacks(registry: EnhancedCallbackRegistry):
    """Setup validation callbacks."""

    def validate_data(cmd: DemoCommand):
        cmd.add_log("Validating data...")
        time.sleep(0.001)
        cmd.data_validated = True
        cmd.add_log("Data valid")

    # Validate when entering validation state
    registry.register(
        "before",
        validate_data,
        to_state=CommandState.VALIDATING,
        priority=10
    )


def setup_error_callbacks(registry: EnhancedCallbackRegistry):
    """Setup error handling callbacks."""

    def handle_error(cmd: DemoCommand, error: Exception):
        cmd.add_log(f"ERROR: {type(error).__name__}: {error}")

    # Handle errors on any transition
    registry.register("error", handle_error)


def demo_basic_callbacks():
    """Demo basic before/after callbacks."""
    print("\n=== Demo 1: Basic Before/After Callbacks ===\n")

    registry = EnhancedCallbackRegistry()
    cmd = DemoCommand("basic_demo")
    cmd.start_time = time.time()

    def before_cb(command: DemoCommand):
        command.add_log("Before callback executed")

    def after_cb(command: DemoCommand):
        command.add_log("After callback executed")

    registry.register("before", before_cb, transition="execute")
    registry.register("after", after_cb, transition="execute")

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("Core action executed")
        return "success"

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    print(cmd.get_log())
    print(f"\nResult: {result}")


def demo_around_callbacks():
    """Demo around callbacks for wrapping behavior."""
    print("\n=== Demo 2: Around Callbacks (Wrapping) ===\n")

    registry = EnhancedCallbackRegistry()
    cmd = DemoCommand("around_demo")
    cmd.start_time = time.time()

    def timing_wrapper(command: DemoCommand, proceed):
        command.add_log("Timer: Starting")
        start = time.time()
        result = proceed()
        elapsed = time.time() - start
        command.add_log(f"Timer: Took {elapsed*1000:.2f}ms")
        return result

    def logging_wrapper(command: DemoCommand, proceed):
        command.add_log("Logger: Enter")
        result = proceed()
        command.add_log("Logger: Exit")
        return result

    # Register with priorities - timing wraps logging
    registry.register("around", timing_wrapper, transition="execute", priority=1)
    registry.register("around", logging_wrapper, transition="execute", priority=2)

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("Core action running...")
        time.sleep(0.01)  # Simulate work
        return "completed"

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    print(cmd.get_log())
    print(f"\nResult: {result}")


def demo_conditional_callbacks():
    """Demo conditional callbacks based on state transitions."""
    print("\n=== Demo 3: Conditional Callbacks ===\n")

    registry = EnhancedCallbackRegistry()
    cmd = DemoCommand("conditional_demo")
    cmd.start_time = time.time()

    # Only execute on specific from_state
    def on_validate_complete(command: DemoCommand):
        command.add_log("Validation complete, ready to execute")

    # Only execute on specific to_state
    def on_enter_executing(command: DemoCommand):
        command.add_log("Entering execution phase")

    # Only execute on specific transition
    def on_execute_transition(command: DemoCommand):
        command.add_log("Execute transition detected")

    # All conditions must match
    def on_exact_transition(command: DemoCommand):
        command.add_log("Exact transition: VALIDATING -> EXECUTING via 'execute'")

    registry.register(
        "before",
        on_validate_complete,
        from_state=CommandState.VALIDATING
    )
    registry.register(
        "before",
        on_enter_executing,
        to_state=CommandState.EXECUTING
    )
    registry.register(
        "before",
        on_execute_transition,
        transition="execute"
    )
    registry.register(
        "before",
        on_exact_transition,
        from_state=CommandState.VALIDATING,
        to_state=CommandState.EXECUTING,
        transition="execute"
    )

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("Executing action")
        return "done"

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    print(cmd.get_log())
    print(f"\nResult: {result}")


def demo_error_callbacks():
    """Demo error callbacks."""
    print("\n=== Demo 4: Error Callbacks ===\n")

    registry = EnhancedCallbackRegistry()
    cmd = DemoCommand("error_demo")
    cmd.start_time = time.time()

    errors_logged = []

    def log_error(command: DemoCommand, error: Exception):
        command.add_log(f"Error handler caught: {type(error).__name__}")
        errors_logged.append(error)

    def cleanup_on_error(command: DemoCommand, error: Exception):
        command.add_log("Cleanup: Rolling back changes")

    registry.register("error", log_error, transition="execute", priority=1)
    registry.register("error", cleanup_on_error, transition="execute", priority=2)

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("About to fail...")
        raise ValueError("Something went wrong!")

    try:
        executor.execute_transition(
            CommandState.VALIDATING,
            CommandState.EXECUTING,
            "execute",
            action
        )
    except ValueError as e:
        cmd.add_log(f"Exception propagated: {e}")

    print(cmd.get_log())
    print(f"\nErrors logged: {len(errors_logged)}")


def demo_full_lifecycle():
    """Demo full command lifecycle with multiple callbacks."""
    print("\n=== Demo 5: Full Command Lifecycle ===\n")

    registry = EnhancedCallbackRegistry()
    cmd = DemoCommand("full_lifecycle_demo")
    cmd.start_time = time.time()

    # Setup all callback types
    setup_logging_callbacks(registry)
    setup_timing_callbacks(registry)
    setup_permission_callbacks(registry)
    setup_validation_callbacks(registry)
    setup_error_callbacks(registry)

    # Pre-compile common transitions for performance
    registry.precompile_common_transitions()

    executor = EnhancedCallbackExecutor(registry, cmd)

    # Simulate multiple state transitions
    transitions = [
        (CommandState.CASTING_AND_VALIDATING_INPUTS, CommandState.LOADING_RECORDS, "load_records"),
        (CommandState.VALIDATING_RECORDS, CommandState.VALIDATING, "validate"),
        (CommandState.VALIDATING, CommandState.EXECUTING, "execute"),
    ]

    for from_state, to_state, transition in transitions:
        cmd.add_log(f"\n--- Transition: {transition} ---")

        def action():
            cmd.add_log(f"Core: {transition}")
            time.sleep(0.001)  # Simulate work
            return f"{transition}_result"

        result = executor.execute_transition(from_state, to_state, transition, action)
        cmd.add_log(f"Result: {result}")

    print(cmd.get_log())

    # Show cache statistics
    print("\n--- Cache Statistics ---")
    stats = registry.get_cache_stats()
    print(f"Cache hits: {stats['hits']}")
    print(f"Cache misses: {stats['misses']}")
    print(f"Hit rate: {stats['hit_rate']:.1f}%")
    print(f"Compiled chains: {stats['compiled_chains']}")


def demo_performance():
    """Demo performance optimization features."""
    print("\n=== Demo 6: Performance Optimization ===\n")

    registry = EnhancedCallbackRegistry()
    cmd = DemoCommand("performance_demo")

    # Register some callbacks
    def cb1(c):
        c.value = 1

    def cb2(c):
        c.value = 2

    registry.register("before", cb1, transition="execute")
    registry.register("after", cb2, transition="execute")

    # Pre-compile for hot path
    print("Pre-compiling common transitions...")
    start = time.time()
    registry.precompile_common_transitions()
    compile_time = time.time() - start
    print(f"Compilation took: {compile_time*1000:.2f}ms")

    executor = EnhancedCallbackExecutor(registry, cmd)

    # Benchmark execution with compiled chain
    iterations = 10000

    def action():
        return "result"

    print(f"\nRunning {iterations} iterations...")
    start = time.time()

    for _ in range(iterations):
        executor.execute_transition(
            CommandState.VALIDATING,
            CommandState.EXECUTING,
            "execute",
            action
        )

    elapsed = time.time() - start
    per_iteration = (elapsed / iterations) * 1000000  # microseconds

    print(f"Total time: {elapsed*1000:.2f}ms")
    print(f"Per iteration: {per_iteration:.2f}μs")
    print(f"Throughput: {iterations/elapsed:.0f} ops/sec")

    # Show cache effectiveness
    stats = registry.get_cache_stats()
    print(f"\nCache hit rate: {stats['hit_rate']:.1f}%")


if __name__ == "__main__":
    print("=" * 70)
    print("Enhanced Callback System - Demo")
    print("=" * 70)

    demo_basic_callbacks()
    demo_around_callbacks()
    demo_conditional_callbacks()
    demo_error_callbacks()
    demo_full_lifecycle()
    demo_performance()

    print("\n" + "=" * 70)
    print("All demos completed!")
    print("=" * 70)
