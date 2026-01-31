"""
Tests for the callback DSL in CallbacksConcern.
"""

import pytest
from pydantic import BaseModel

from foobara_py.core.command import Command
from foobara_py.core.state_machine import CommandState


class SimpleInputs(BaseModel):
    value: int


class SimpleCommand(Command[SimpleInputs, int]):
    """Test command for callback DSL."""

    def execute(self) -> int:
        return self.inputs.value * 2


def test_callback_registry_initialization():
    """Test that callback registry is initialized."""
    assert SimpleCommand._enhanced_callback_registry is not None


def test_before_execute_transition():
    """Test before_execute_transition registration."""
    call_log = []

    def callback(cmd):
        call_log.append("called")

    SimpleCommand.before_execute_transition(callback)

    assert SimpleCommand._enhanced_callback_registry.has_callbacks()
    assert len(SimpleCommand._enhanced_callback_registry._callbacks) > 0


def test_after_execute_transition():
    """Test after_execute_transition registration."""
    call_log = []

    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback(cmd):
        call_log.append("called")

    TestCmd.after_execute_transition(callback)

    assert TestCmd._enhanced_callback_registry.has_callbacks()


def test_before_any_transition():
    """Test before_any_transition registration."""
    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback(cmd):
        pass

    TestCmd.before_any_transition(callback)

    reg = TestCmd._enhanced_callback_registry
    assert reg.has_callbacks()

    # Should match any transition
    callbacks = reg.get_callbacks(
        "before",
        CommandState.INITIALIZED,
        CommandState.OPENING_TRANSACTION,
        "open_transaction",
    )
    assert len(callbacks) == 1


def test_before_transition_from():
    """Test before_transition_from registration."""
    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback(cmd):
        pass

    TestCmd.before_transition_from(CommandState.INITIALIZED, callback)

    reg = TestCmd._enhanced_callback_registry
    assert reg.has_callbacks()

    # Should match transitions from INITIALIZED
    callbacks = reg.get_callbacks(
        "before",
        CommandState.INITIALIZED,
        CommandState.OPENING_TRANSACTION,
        "open_transaction",
    )
    assert len(callbacks) == 1

    # Should NOT match transitions from other states
    callbacks = reg.get_callbacks(
        "before",
        CommandState.EXECUTING,
        CommandState.COMMITTING_TRANSACTION,
        "commit_transaction",
    )
    assert len(callbacks) == 0


def test_before_transition_to():
    """Test before_transition_to registration."""
    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback(cmd):
        pass

    TestCmd.before_transition_to(CommandState.SUCCEEDED, callback)

    reg = TestCmd._enhanced_callback_registry
    assert reg.has_callbacks()

    # Should match transitions to SUCCEEDED
    callbacks = reg.get_callbacks(
        "before",
        CommandState.COMMITTING_TRANSACTION,
        CommandState.SUCCEEDED,
        "succeed",
    )
    assert len(callbacks) == 1


def test_before_transition_with_transition_name():
    """Test before_transition with transition name."""
    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback(cmd):
        pass

    TestCmd.before_transition(callback, transition="execute")

    reg = TestCmd._enhanced_callback_registry
    assert reg.has_callbacks()

    # Should match execute transitions
    callbacks = reg.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
    )
    assert len(callbacks) == 1

    # Should NOT match other transitions
    callbacks = reg.get_callbacks(
        "before",
        CommandState.INITIALIZED,
        CommandState.OPENING_TRANSACTION,
        "open_transaction",
    )
    assert len(callbacks) == 0


def test_before_transition_combined():
    """Test before_transition with multiple conditions."""
    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback(cmd):
        pass

    TestCmd.before_transition(
        callback,
        from_state=CommandState.VALIDATING,
        to_state=CommandState.EXECUTING,
        transition="execute",
    )

    reg = TestCmd._enhanced_callback_registry
    assert reg.has_callbacks()

    # Should match only this specific transition
    callbacks = reg.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
    )
    assert len(callbacks) == 1

    # Should NOT match if any condition differs
    callbacks = reg.get_callbacks(
        "before",
        CommandState.INITIALIZED,  # Different from_state
        CommandState.EXECUTING,
        "execute",
    )
    assert len(callbacks) == 0


def test_callback_priority():
    """Test callback priority ordering."""
    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback1(cmd):
        pass

    def callback2(cmd):
        pass

    def callback3(cmd):
        pass

    # Register with different priorities
    TestCmd.before_execute_transition(callback1, priority=100)
    TestCmd.before_execute_transition(callback2, priority=0)
    TestCmd.before_execute_transition(callback3, priority=50)

    reg = TestCmd._enhanced_callback_registry

    # Get callbacks and check they're sorted by priority
    callbacks = reg.get_callbacks(
        "before",
        CommandState.VALIDATING,
        CommandState.EXECUTING,
        "execute",
    )

    assert len(callbacks) == 3
    assert callbacks[0] == callback2  # priority 0 (lowest)
    assert callbacks[1] == callback3  # priority 50
    assert callbacks[2] == callback1  # priority 100


def test_convenience_methods():
    """Test convenience methods for specific states."""
    class TestCmd(Command[SimpleInputs, int]):
        def execute(self) -> int:
            return self.inputs.value * 2

    def callback(cmd):
        pass

    # Test from-state convenience methods
    TestCmd.before_transition_from_initialized(callback)
    TestCmd.after_transition_from_executing(callback)

    # Test to-state convenience methods
    TestCmd.before_transition_to_succeeded(callback)
    TestCmd.after_transition_to_failed(callback)

    reg = TestCmd._enhanced_callback_registry
    assert reg.has_callbacks()
    assert len(reg._callbacks) == 4


def test_all_dsl_methods_exist():
    """Test that all expected DSL methods exist."""
    methods = [
        # Execute transition
        "before_execute_transition",
        "after_execute_transition",
        "around_execute_transition",
        # Validate transition
        "before_validate_transition",
        "after_validate_transition",
        "around_validate_transition",
        # Other transitions
        "before_cast_and_validate_inputs",
        "after_cast_and_validate_inputs",
        "before_load_records",
        "after_load_records",
        "before_validate_records",
        "after_validate_records",
        "before_open_transaction",
        "after_open_transaction",
        "before_commit_transaction",
        "after_commit_transaction",
        # Any transition
        "before_any_transition",
        "after_any_transition",
        "around_any_transition",
        # From/to state
        "before_transition_from",
        "after_transition_from",
        "around_transition_from",
        "before_transition_to",
        "after_transition_to",
        "around_transition_to",
        # Convenience methods
        "before_transition_from_initialized",
        "after_transition_from_initialized",
        "before_transition_from_executing",
        "after_transition_from_executing",
        "before_transition_to_succeeded",
        "after_transition_to_succeeded",
        "before_transition_to_failed",
        "after_transition_to_failed",
        # Generic
        "before_transition",
        "after_transition",
        "around_transition",
    ]

    for method in methods:
        assert hasattr(SimpleCommand, method), f"Missing method: {method}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
