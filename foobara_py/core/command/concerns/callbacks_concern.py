"""
CallbacksConcern - Ruby-like callback DSL for Commands.

Provides a rich DSL for registering callbacks with various conditions:

Registration styles:
    1. Any transition callbacks:
       - before_any_transition(callback)
       - after_any_transition(callback)
       - around_any_transition(callback)

    2. From-state callbacks:
       - before_transition_from_initialized(callback)
       - after_transition_from_executing(callback)

    3. To-state callbacks:
       - before_transition_to_succeeded(callback)
       - after_transition_to_failed(callback)

    4. Transition-specific callbacks:
       - before_execute(callback)
       - after_validate(callback)
       - around_cast_and_validate_inputs(callback)

    5. Combined callbacks:
       - before_transition_from_initialized_to_executing(callback)
       - after_execute_transition(callback)

    6. Generic callback with all conditions:
       - before_transition(callback, from_state=..., to_state=..., transition=...)

All methods support chaining and decorator usage.

Example:
    class MyCommand(Command):
        @classmethod
        def setup_callbacks(cls):
            cls.before_execute(cls.check_permissions)
            cls.after_execute(cls.log_result)
            cls.before_transition_from_initialized(cls.setup_context)

        @staticmethod
        def check_permissions(cmd):
            if not cmd.inputs.user.can_edit:
                cmd.add_error("not_allowed", "Permission denied")

        @staticmethod
        def log_result(cmd):
            logger.info(f"Result: {cmd.result}")
"""

from typing import Callable, ClassVar, Optional

from foobara_py.core.callbacks_enhanced import EnhancedCallbackRegistry
from foobara_py.core.state_machine import CommandState


class CallbacksConcern:
    """
    Mixin providing Ruby-like callback DSL for Commands.

    Provides class methods for registering callbacks with various conditions.
    Callbacks are stored in a class-level EnhancedCallbackRegistry.
    """

    # Class-level registry (initialized in metaclass or __init_subclass__)
    _enhanced_callback_registry: ClassVar[Optional["EnhancedCallbackRegistry"]] = None

    @classmethod
    def _ensure_callback_registry(cls) -> EnhancedCallbackRegistry:
        """
        Ensure callback registry exists for this class.

        Creates registry on first use if not already initialized by metaclass.

        Returns:
            The callback registry for this class
        """
        if cls._enhanced_callback_registry is None:
            cls._enhanced_callback_registry = EnhancedCallbackRegistry()
        return cls._enhanced_callback_registry

    # ==========================================
    # Any transition callbacks
    # ==========================================

    @classmethod
    def before_any_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for any state transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("before", callback, priority=priority)

    @classmethod
    def after_any_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for any state transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("after", callback, priority=priority)

    @classmethod
    def around_any_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register around callback for any state transition.

        Args:
            callback: Callable accepting (command, proceed) and calling proceed()
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("around", callback, priority=priority)

    # ==========================================
    # From-state callbacks
    # ==========================================

    @classmethod
    def before_transition_from(cls, state: CommandState, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for transitions from specific state.

        Args:
            state: State to transition from
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("before", callback, from_state=state, priority=priority)

    @classmethod
    def after_transition_from(cls, state: CommandState, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for transitions from specific state.

        Args:
            state: State to transition from
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("after", callback, from_state=state, priority=priority)

    @classmethod
    def around_transition_from(cls, state: CommandState, callback: Callable, priority: int = 0) -> None:
        """
        Register around callback for transitions from specific state.

        Args:
            state: State to transition from
            callback: Callable accepting (command, proceed) and calling proceed()
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("around", callback, from_state=state, priority=priority)

    # Convenience methods for specific from-states
    @classmethod
    def before_transition_from_initialized(cls, callback: Callable, priority: int = 0) -> None:
        """Before callback for transitions from INITIALIZED state."""
        cls.before_transition_from(CommandState.INITIALIZED, callback, priority)

    @classmethod
    def before_transition_from_executing(cls, callback: Callable, priority: int = 0) -> None:
        """Before callback for transitions from EXECUTING state."""
        cls.before_transition_from(CommandState.EXECUTING, callback, priority)

    @classmethod
    def after_transition_from_initialized(cls, callback: Callable, priority: int = 0) -> None:
        """After callback for transitions from INITIALIZED state."""
        cls.after_transition_from(CommandState.INITIALIZED, callback, priority)

    @classmethod
    def after_transition_from_executing(cls, callback: Callable, priority: int = 0) -> None:
        """After callback for transitions from EXECUTING state."""
        cls.after_transition_from(CommandState.EXECUTING, callback, priority)

    # ==========================================
    # To-state callbacks
    # ==========================================

    @classmethod
    def before_transition_to(cls, state: CommandState, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for transitions to specific state.

        Args:
            state: State to transition to
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("before", callback, to_state=state, priority=priority)

    @classmethod
    def after_transition_to(cls, state: CommandState, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for transitions to specific state.

        Args:
            state: State to transition to
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("after", callback, to_state=state, priority=priority)

    @classmethod
    def around_transition_to(cls, state: CommandState, callback: Callable, priority: int = 0) -> None:
        """
        Register around callback for transitions to specific state.

        Args:
            state: State to transition to
            callback: Callable accepting (command, proceed) and calling proceed()
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("around", callback, to_state=state, priority=priority)

    # Convenience methods for specific to-states
    @classmethod
    def before_transition_to_succeeded(cls, callback: Callable, priority: int = 0) -> None:
        """Before callback for transitions to SUCCEEDED state."""
        cls.before_transition_to(CommandState.SUCCEEDED, callback, priority)

    @classmethod
    def before_transition_to_failed(cls, callback: Callable, priority: int = 0) -> None:
        """Before callback for transitions to FAILED state."""
        cls.before_transition_to(CommandState.FAILED, callback, priority)

    @classmethod
    def after_transition_to_succeeded(cls, callback: Callable, priority: int = 0) -> None:
        """After callback for transitions to SUCCEEDED state."""
        cls.after_transition_to(CommandState.SUCCEEDED, callback, priority)

    @classmethod
    def after_transition_to_failed(cls, callback: Callable, priority: int = 0) -> None:
        """After callback for transitions to FAILED state."""
        cls.after_transition_to(CommandState.FAILED, callback, priority)

    # ==========================================
    # Transition-specific callbacks
    # Note: These use the _transition suffix to avoid conflicts with
    # instance methods in ExecutionConcern and ValidationConcern
    # ==========================================

    @classmethod
    def before_validate_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for validate transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("before", callback, transition="validate", priority=priority)

    @classmethod
    def after_validate_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for validate transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("after", callback, transition="validate", priority=priority)

    @classmethod
    def around_validate_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register around callback for validate transition.

        Args:
            callback: Callable accepting (command, proceed) and calling proceed()
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("around", callback, transition="validate", priority=priority)

    @classmethod
    def _register_transition_callback(
        cls,
        callback_type: str,
        transition: str,
        callback: Callable,
        priority: int = 0
    ) -> None:
        """
        Helper method to register a callback for a specific transition.

        Args:
            callback_type: Type of callback ("before", "after", "around")
            transition: Transition name
            callback: Callable to register
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            callback_type, callback, transition=transition, priority=priority
        )

    @classmethod
    def before_cast_and_validate_inputs(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for cast_and_validate_inputs transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._register_transition_callback("before", "cast_and_validate_inputs", callback, priority)

    @classmethod
    def after_cast_and_validate_inputs(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for cast_and_validate_inputs transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._register_transition_callback("after", "cast_and_validate_inputs", callback, priority)

    @classmethod
    def around_cast_and_validate_inputs(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register around callback for cast_and_validate_inputs transition.

        Args:
            callback: Callable accepting (command, proceed) and calling proceed()
            priority: Execution priority (lower = earlier)
        """
        cls._register_transition_callback("around", "cast_and_validate_inputs", callback, priority)

    @classmethod
    def before_load_records(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for load_records transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "before", callback, transition="load_records", priority=priority
        )

    @classmethod
    def after_load_records(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for load_records transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "after", callback, transition="load_records", priority=priority
        )

    @classmethod
    def before_validate_records(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for validate_records transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "before", callback, transition="validate_records", priority=priority
        )

    @classmethod
    def after_validate_records(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for validate_records transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "after", callback, transition="validate_records", priority=priority
        )

    @classmethod
    def before_open_transaction(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for open_transaction transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "before", callback, transition="open_transaction", priority=priority
        )

    @classmethod
    def after_open_transaction(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for open_transaction transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "after", callback, transition="open_transaction", priority=priority
        )

    @classmethod
    def before_commit_transaction(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for commit_transaction transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "before", callback, transition="commit_transaction", priority=priority
        )

    @classmethod
    def after_commit_transaction(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for commit_transaction transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "after", callback, transition="commit_transaction", priority=priority
        )

    # ==========================================
    # Execute and Validate transition callbacks
    # These are the primary methods for the most common transitions
    # ==========================================

    @classmethod
    def before_execute_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for execute transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("before", callback, transition="execute", priority=priority)

    @classmethod
    def after_execute_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for execute transition.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("after", callback, transition="execute", priority=priority)

    @classmethod
    def around_execute_transition(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register around callback for execute transition.

        Args:
            callback: Callable accepting (command, proceed) and calling proceed()
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register("around", callback, transition="execute", priority=priority)

    @classmethod
    def before_transition_from_initialized_to_executing(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register before callback for INITIALIZED -> EXECUTING transition.

        Note: This is a multi-hop transition that goes through intermediate states.
        Consider using before_transition_from_initialized or before_transition_to_executing instead.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "before",
            callback,
            from_state=CommandState.INITIALIZED,
            to_state=CommandState.EXECUTING,
            priority=priority,
        )

    @classmethod
    def after_transition_from_initialized_to_executing(cls, callback: Callable, priority: int = 0) -> None:
        """
        Register after callback for INITIALIZED -> EXECUTING transition.

        Note: This is a multi-hop transition that goes through intermediate states.
        Consider using after_transition_from_initialized or after_transition_to_executing instead.

        Args:
            callback: Callable accepting command instance
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "after",
            callback,
            from_state=CommandState.INITIALIZED,
            to_state=CommandState.EXECUTING,
            priority=priority,
        )

    # ==========================================
    # Generic callback registration
    # ==========================================

    @classmethod
    def before_transition(
        cls,
        callback: Callable,
        from_state: Optional[CommandState] = None,
        to_state: Optional[CommandState] = None,
        transition: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        """
        Register generic before callback with all conditions.

        This is the most flexible registration method, allowing any combination
        of conditions.

        Args:
            callback: Callable accepting command instance
            from_state: Optional state to transition from
            to_state: Optional state to transition to
            transition: Optional transition name
            priority: Execution priority (lower = earlier)

        Example:
            # Before any execute transition
            cls.before_transition(my_callback, transition="execute")

            # Before transitions to succeeded from any state
            cls.before_transition(my_callback, to_state=CommandState.SUCCEEDED)

            # Before specific state transition
            cls.before_transition(
                my_callback,
                from_state=CommandState.VALIDATING,
                to_state=CommandState.EXECUTING
            )
        """
        cls._ensure_callback_registry().register(
            "before",
            callback,
            from_state=from_state,
            to_state=to_state,
            transition=transition,
            priority=priority,
        )

    @classmethod
    def after_transition(
        cls,
        callback: Callable,
        from_state: Optional[CommandState] = None,
        to_state: Optional[CommandState] = None,
        transition: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        """
        Register generic after callback with all conditions.

        Args:
            callback: Callable accepting command instance
            from_state: Optional state to transition from
            to_state: Optional state to transition to
            transition: Optional transition name
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "after",
            callback,
            from_state=from_state,
            to_state=to_state,
            transition=transition,
            priority=priority,
        )

    @classmethod
    def around_transition(
        cls,
        callback: Callable,
        from_state: Optional[CommandState] = None,
        to_state: Optional[CommandState] = None,
        transition: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        """
        Register generic around callback with all conditions.

        Args:
            callback: Callable accepting (command, proceed) and calling proceed()
            from_state: Optional state to transition from
            to_state: Optional state to transition to
            transition: Optional transition name
            priority: Execution priority (lower = earlier)
        """
        cls._ensure_callback_registry().register(
            "around",
            callback,
            from_state=from_state,
            to_state=to_state,
            transition=transition,
            priority=priority,
        )
