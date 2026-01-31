"""
Tests for the enhanced callback system.

Demonstrates Ruby-level flexibility with Python performance.
"""

import pytest

from foobara_py.core.callbacks_enhanced import (
    CallbackCondition,
    EnhancedCallbackExecutor,
    EnhancedCallbackRegistry,
    RegisteredCallback,
)
from foobara_py.core.state_machine import CommandState


class MockCommand:
    """Mock command for testing."""

    def __init__(self):
        self.log = []
        self.value = 0

    def add_log(self, message):
        self.log.append(message)


def test_callback_condition_matches():
    """Test callback condition matching logic."""
    # Match all transitions
    condition = CallbackCondition()
    assert condition.matches(
        CommandState.INITIALIZED,
        CommandState.OPENING_TRANSACTION,
        "open_transaction"
    )

    # Match specific from_state
    condition = CallbackCondition(from_state=CommandState.VALIDATING)
    assert condition.matches(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )
    assert not condition.matches(
        CommandState.INITIALIZED,
        CommandState.EXECUTING,
        "execute"
    )

    # Match specific to_state
    condition = CallbackCondition(to_state=CommandState.EXECUTING)
    assert condition.matches(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )
    assert not condition.matches(
        CommandState.VALIDATING,
        CommandState.SUCCEEDED,
        "succeed"
    )

    # Match specific transition
    condition = CallbackCondition(transition="execute")
    assert condition.matches(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )
    assert not condition.matches(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "validate"
    )

    # Match all conditions
    condition = CallbackCondition(
        from_state=CommandState.VALIDATING,
        to_state=CommandState.EXECUTING,
        transition="execute"
    )
    assert condition.matches(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )
    assert not condition.matches(
        CommandState.VALIDATING,
        CommandState.SUCCEEDED,
        "execute"
    )


def test_registered_callback_sorting():
    """Test callbacks sort by priority."""
    cb1 = RegisteredCallback(
        callback=lambda: None,
        callback_type="before",
        condition=CallbackCondition(),
        priority=10
    )
    cb2 = RegisteredCallback(
        callback=lambda: None,
        callback_type="before",
        condition=CallbackCondition(),
        priority=5
    )
    cb3 = RegisteredCallback(
        callback=lambda: None,
        callback_type="before",
        condition=CallbackCondition(),
        priority=20
    )

    callbacks = [cb1, cb2, cb3]
    callbacks.sort()

    assert callbacks[0].priority == 5
    assert callbacks[1].priority == 10
    assert callbacks[2].priority == 20


def test_registry_register_and_get():
    """Test registering and retrieving callbacks."""
    registry = EnhancedCallbackRegistry()

    def before_callback(cmd):
        cmd.add_log("before")

    registry.register(
        "before",
        before_callback,
        transition="execute"
    )

    # Get matching callbacks
    callbacks = registry.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )
    assert len(callbacks) == 1
    assert callbacks[0] == before_callback

    # Get non-matching callbacks
    callbacks = registry.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "validate"
    )
    assert len(callbacks) == 0


def test_registry_compile_chain():
    """Test pre-compiling callback chains."""
    registry = EnhancedCallbackRegistry()

    def before_cb(cmd):
        cmd.add_log("before")

    def after_cb(cmd):
        cmd.add_log("after")

    def around_cb(cmd, proceed):
        cmd.add_log("around_start")
        result = proceed()
        cmd.add_log("around_end")
        return result

    registry.register("before", before_cb, transition="execute")
    registry.register("after", after_cb, transition="execute")
    registry.register("around", around_cb, transition="execute")

    # Compile the chain
    chain = registry.compile_chain(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )

    assert "before" in chain
    assert "after" in chain
    assert "around" in chain
    assert len(chain["before"]) == 1
    assert len(chain["after"]) == 1
    assert len(chain["around"]) == 1

    # Second call should use cache
    chain2 = registry.compile_chain(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )
    assert chain is chain2


def test_registry_priority_ordering():
    """Test callbacks execute in priority order."""
    registry = EnhancedCallbackRegistry()

    def cb1(cmd):
        cmd.add_log("priority_10")

    def cb2(cmd):
        cmd.add_log("priority_5")

    def cb3(cmd):
        cmd.add_log("priority_15")

    registry.register("before", cb1, priority=10, transition="execute")
    registry.register("before", cb2, priority=5, transition="execute")
    registry.register("before", cb3, priority=15, transition="execute")

    callbacks = registry.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )

    # Execute callbacks and check order
    cmd = MockCommand()
    for callback in callbacks:
        callback(cmd)

    assert cmd.log == ["priority_5", "priority_10", "priority_15"]


def test_executor_before_after_callbacks():
    """Test executor runs before and after callbacks."""
    registry = EnhancedCallbackRegistry()
    cmd = MockCommand()

    def before_cb(command):
        command.add_log("before")

    def after_cb(command):
        command.add_log("after")

    registry.register("before", before_cb, transition="execute")
    registry.register("after", after_cb, transition="execute")

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("action")
        return "result"

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    assert result == "result"
    assert cmd.log == ["before", "action", "after"]


def test_executor_around_callbacks():
    """Test executor properly nests around callbacks."""
    registry = EnhancedCallbackRegistry()
    cmd = MockCommand()

    def around1(command, proceed):
        command.add_log("around1_start")
        result = proceed()
        command.add_log("around1_end")
        return result

    def around2(command, proceed):
        command.add_log("around2_start")
        result = proceed()
        command.add_log("around2_end")
        return result

    # Register with different priorities
    registry.register("around", around1, priority=5, transition="execute")
    registry.register("around", around2, priority=10, transition="execute")

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("action")
        return "result"

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    assert result == "result"
    # around1 (priority 5) wraps around2 (priority 10)
    assert cmd.log == [
        "around1_start",
        "around2_start",
        "action",
        "around2_end",
        "around1_end"
    ]


def test_executor_error_callbacks():
    """Test error callbacks are called on exception."""
    registry = EnhancedCallbackRegistry()
    cmd = MockCommand()

    errors_caught = []

    def error_cb(command, error):
        errors_caught.append(error)
        command.add_log("error_handled")

    registry.register("error", error_cb, transition="execute")

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        raise ValueError("test error")

    with pytest.raises(ValueError) as exc_info:
        executor.execute_transition(
            CommandState.VALIDATING,
            CommandState.EXECUTING,
            "execute",
            action
        )

    assert str(exc_info.value) == "test error"
    assert len(errors_caught) == 1
    assert cmd.log == ["error_handled"]


def test_executor_fast_path_no_callbacks():
    """Test fast path when no callbacks registered."""
    registry = EnhancedCallbackRegistry()
    cmd = MockCommand()
    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("action")
        return "result"

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    assert result == "result"
    assert cmd.log == ["action"]


def test_registry_cache_stats():
    """Test cache statistics tracking."""
    registry = EnhancedCallbackRegistry()

    def cb(cmd):
        pass

    registry.register("before", cb, transition="execute")

    # First call - cache miss
    registry.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )

    # Compile chain
    registry.compile_chain(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )

    # Second call - cache hit
    registry.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute"
    )

    stats = registry.get_cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["total"] == 2
    assert stats["compiled_chains"] == 1


def test_registry_precompile_common_transitions():
    """Test pre-compiling common transitions."""
    registry = EnhancedCallbackRegistry()

    def cb(cmd):
        pass

    registry.register("before", cb)

    # Pre-compile common transitions
    registry.precompile_common_transitions()

    stats = registry.get_cache_stats()
    # Should have compiled chains for common transitions
    assert stats["compiled_chains"] > 0


def test_conditional_callbacks_complex():
    """Test complex conditional callback scenarios."""
    registry = EnhancedCallbackRegistry()
    cmd = MockCommand()

    # Callback 1: Only on execute transition
    def cb_execute_only(command):
        command.add_log("execute_only")

    # Callback 2: Only when entering EXECUTING state
    def cb_to_executing(command):
        command.add_log("to_executing")

    # Callback 3: Always
    def cb_always(command):
        command.add_log("always")

    registry.register("before", cb_execute_only, transition="execute")
    registry.register("before", cb_to_executing, to_state=CommandState.EXECUTING)
    registry.register("before", cb_always)

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        return "result"

    # Execute transition
    executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    # All three should have fired
    assert "execute_only" in cmd.log
    assert "to_executing" in cmd.log
    assert "always" in cmd.log
    assert len(cmd.log) == 3


def test_executor_around_modifies_result():
    """Test around callbacks can modify the result."""
    registry = EnhancedCallbackRegistry()
    cmd = MockCommand()

    def around_double(command, proceed):
        result = proceed()
        return result * 2

    registry.register("around", around_double, transition="execute")

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        return 5

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    assert result == 10


def test_multiple_callback_types():
    """Test all callback types working together."""
    registry = EnhancedCallbackRegistry()
    cmd = MockCommand()

    def before_cb(command):
        command.add_log("before")

    def around_cb(command, proceed):
        command.add_log("around_start")
        result = proceed()
        command.add_log("around_end")
        return result

    def after_cb(command):
        command.add_log("after")

    registry.register("before", before_cb, transition="execute")
    registry.register("around", around_cb, transition="execute")
    registry.register("after", after_cb, transition="execute")

    executor = EnhancedCallbackExecutor(registry, cmd)

    def action():
        cmd.add_log("action")
        return "result"

    result = executor.execute_transition(
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
        action
    )

    assert result == "result"
    assert cmd.log == [
        "before",
        "around_start",
        "action",
        "around_end",
        "after"
    ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
