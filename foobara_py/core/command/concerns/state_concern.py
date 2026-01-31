"""
StateConcern - Command state machine and execution flow.

Handles:
- State machine management
- 8-phase execution flow
- Callback execution (enhanced and legacy)
- Outcome generation

Features:
- Enhanced callbacks with state transition awareness
- Backward compatibility with phase-based callbacks
- Conditional callback execution based on state transitions

Pattern: Ruby Foobara's StateMachine concern
"""

from typing import Any, Callable, ClassVar, Optional

from foobara_py.core.callbacks import CallbackExecutor, CallbackPhase, CallbackRegistry
from foobara_py.core.callbacks_enhanced import EnhancedCallbackExecutor, EnhancedCallbackRegistry
from foobara_py.core.state_machine import STATE_NAMES, CommandState, CommandStateMachine, Halt


class StateConcern:
    """Mixin for state machine and execution flow."""

    # Class-level callback registries
    _callback_registry: ClassVar[Optional[CallbackRegistry]] = None
    _enhanced_callback_registry: ClassVar[Optional[EnhancedCallbackRegistry]] = None

    # Instance attributes (defined in __slots__ in Command)
    _state_machine: CommandStateMachine
    _callback_executor: Optional[CallbackExecutor]
    _enhanced_callback_executor: Optional[EnhancedCallbackExecutor]
    _outcome: Optional["CommandOutcome"]

    @property
    def state(self) -> CommandState:
        """
        Get current execution state.

        Returns:
            Current CommandState enum value
        """
        return self._state_machine.state

    @property
    def state_name(self) -> str:
        """
        Get current state name.

        Returns:
            Human-readable state name (e.g., "executing")
        """
        return STATE_NAMES[self._state_machine.state]

    def run_instance(self) -> "CommandOutcome":
        """
        Run this command instance through full execution flow.

        Implements the complete 8-state execution flow:
        1. open_transaction - Begin database transaction
        2. cast_and_validate_inputs - Validate inputs via Pydantic
        3. load_records - Load entity records from database
        4. validate_records - Validate loaded records exist
        5. validate - Custom validation hook
        6. execute - Core business logic
        7. commit_transaction - Commit transaction
        8. succeed/fail/error - Terminal states

        Returns:
            CommandOutcome with result or errors
        """
        from foobara_py.core.outcome import CommandOutcome

        # Initialize enhanced callback executor if registry exists and has callbacks
        if (
            hasattr(self.__class__, "_enhanced_callback_registry")
            and self.__class__._enhanced_callback_registry
            and self.__class__._enhanced_callback_registry.has_callbacks()
        ):
            self._enhanced_callback_executor = EnhancedCallbackExecutor(
                self.__class__._enhanced_callback_registry, self
            )
        else:
            self._enhanced_callback_executor = None

        # Initialize callback executor (legacy support)
        if self._callback_registry:
            self._callback_executor = CallbackExecutor(self._callback_registry, self)

        try:
            # Phase 1: Open transaction
            self._execute_phase(
                CommandState.OPENING_TRANSACTION,
                CallbackPhase.OPEN_TRANSACTION,
                self.open_transaction,
                transition_name="open_transaction",
            )
            if self._errors.has_errors():
                return self._fail()

            try:
                # Phase 2: Cast and validate inputs
                self._execute_phase(
                    CommandState.CASTING_AND_VALIDATING_INPUTS,
                    CallbackPhase.CAST_AND_VALIDATE_INPUTS,
                    self.cast_and_validate_inputs,
                    transition_name="cast_and_validate_inputs",
                )
                if self._errors.has_errors():
                    return self._fail()

                # Phase 3: Load records
                self._execute_phase(
                    CommandState.LOADING_RECORDS,
                    CallbackPhase.LOAD_RECORDS,
                    self.load_records,
                    transition_name="load_records",
                )
                if self._errors.has_errors():
                    return self._fail()

                # Phase 4: Validate records
                self._execute_phase(
                    CommandState.VALIDATING_RECORDS,
                    CallbackPhase.VALIDATE_RECORDS,
                    self.validate_records,
                    transition_name="validate_records",
                )
                if self._errors.has_errors():
                    return self._fail()

                # Phase 5: Validate
                self._execute_phase(
                    CommandState.VALIDATING,
                    CallbackPhase.VALIDATE,
                    self.validate,
                    transition_name="validate",
                )
                if self._errors.has_errors():
                    return self._fail()

                # Phase 6: Execute
                try:
                    # Call before_execute hook if defined (optimized with single boolean check)
                    if self.__class__._has_before_execute:
                        self.before_execute()
                        if self._errors.has_errors():
                            return self._fail()

                    # Execute phase with enhanced or legacy callbacks
                    self._result = self._execute_phase(
                        CommandState.EXECUTING,
                        CallbackPhase.EXECUTE,
                        self.execute,
                        transition_name="execute",
                    )

                    # Call after_execute hook if defined (optimized with single boolean check)
                    if self.__class__._has_after_execute:
                        self._result = self.after_execute(self._result)
                except Halt:
                    return self._fail()
                except Exception as e:
                    from foobara_py.core.errors import FoobaraError, Symbols

                    self.add_error(
                        FoobaraError.runtime_error(
                            Symbols.EXECUTION_ERROR, str(e), exception_type=type(e).__name__
                        )
                    )
                    return self._fail()

                if self._errors.has_errors():
                    return self._fail()

                # Phase 7: Commit transaction
                self._execute_phase(
                    CommandState.COMMITTING_TRANSACTION,
                    CallbackPhase.COMMIT_TRANSACTION,
                    self.commit_transaction,
                    transition_name="commit_transaction",
                )

                # Success!
                self._state_machine.transition_to(CommandState.SUCCEEDED)
                return CommandOutcome.from_result(self._result)

            except Halt:
                return self._fail()

            finally:
                # Exit transaction context
                if self._transaction:
                    self._transaction.__exit__(None, None, None)

        except Exception as e:
            # Unhandled exception - error state
            self._state_machine.error()
            self.rollback_transaction()
            if self._transaction:
                self._transaction.__exit__(type(e), e, e.__traceback__)
            raise

    def _execute_phase(
        self,
        state: CommandState,
        callback_phase: CallbackPhase,
        action: Callable[[], Any],
        transition_name: Optional[str] = None,
    ) -> Any:
        """
        Execute a phase with state transition and callbacks.

        Supports both enhanced callbacks (with state transition awareness)
        and legacy callbacks (phase-based).

        Args:
            state: State to transition to
            callback_phase: Callback phase to execute (for legacy callbacks)
            action: Action to perform
            transition_name: Transition name for enhanced callbacks (defaults to phase value)

        Returns:
            Result from action execution

        Raises:
            Halt: If execution should halt
        """
        from_state = self._state_machine.state
        to_state = state

        # Transition state
        self._state_machine.transition_to(state)

        # Default transition name to callback phase value
        if transition_name is None:
            transition_name = callback_phase.value

        try:
            # Execute with enhanced callbacks if available
            if hasattr(self, "_enhanced_callback_executor") and self._enhanced_callback_executor:
                return self._enhanced_callback_executor.execute_transition(
                    from_state, to_state, transition_name, action
                )
            # Fall back to legacy callback system
            elif self._callback_executor:
                return self._callback_executor.execute_phase(callback_phase, action)
            # No callbacks - execute directly
            else:
                return action()
        except Halt:
            raise

    def _fail(self) -> "CommandOutcome":
        """
        Transition to failed state and return failure outcome.

        Returns:
            CommandOutcome with errors
        """
        from foobara_py.core.outcome import CommandOutcome

        self._state_machine.fail()
        self.rollback_transaction()
        return CommandOutcome.from_errors(*self._errors.all())
