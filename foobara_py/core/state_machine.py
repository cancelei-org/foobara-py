"""
High-performance state machine for command execution.

Implements Ruby Foobara's 8-state execution flow with minimal overhead.
Uses __slots__ and enum for performance.
"""

from enum import IntEnum, auto
from typing import Callable, List, Optional, Set, Tuple


class CommandState(IntEnum):
    """
    Command execution states matching Ruby Foobara.

    Using IntEnum for fast comparisons and minimal memory.
    """

    INITIALIZED = 0
    OPENING_TRANSACTION = auto()
    CASTING_AND_VALIDATING_INPUTS = auto()
    LOADING_RECORDS = auto()
    VALIDATING_RECORDS = auto()
    VALIDATING = auto()
    EXECUTING = auto()
    COMMITTING_TRANSACTION = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    ERRORED = auto()


# Terminal states - command cannot transition from these
TERMINAL_STATES: Set[CommandState] = {
    CommandState.SUCCEEDED,
    CommandState.FAILED,
    CommandState.ERRORED,
}

# States that can transition to failed
CAN_FAIL_STATES: Set[CommandState] = set(CommandState) - TERMINAL_STATES

# Valid state transitions (from_state -> set of to_states)
VALID_TRANSITIONS: dict = {
    CommandState.INITIALIZED: {
        CommandState.OPENING_TRANSACTION,
        CommandState.FAILED,
        CommandState.ERRORED,
    },
    CommandState.OPENING_TRANSACTION: {
        CommandState.CASTING_AND_VALIDATING_INPUTS,
        CommandState.FAILED,
        CommandState.ERRORED,
    },
    CommandState.CASTING_AND_VALIDATING_INPUTS: {
        CommandState.LOADING_RECORDS,
        CommandState.FAILED,
        CommandState.ERRORED,
    },
    CommandState.LOADING_RECORDS: {
        CommandState.VALIDATING_RECORDS,
        CommandState.FAILED,
        CommandState.ERRORED,
    },
    CommandState.VALIDATING_RECORDS: {
        CommandState.VALIDATING,
        CommandState.FAILED,
        CommandState.ERRORED,
    },
    CommandState.VALIDATING: {CommandState.EXECUTING, CommandState.FAILED, CommandState.ERRORED},
    CommandState.EXECUTING: {
        CommandState.COMMITTING_TRANSACTION,
        CommandState.FAILED,
        CommandState.ERRORED,
    },
    CommandState.COMMITTING_TRANSACTION: {
        CommandState.SUCCEEDED,
        CommandState.FAILED,
        CommandState.ERRORED,
    },
    CommandState.SUCCEEDED: set(),
    CommandState.FAILED: set(),
    CommandState.ERRORED: set(),
}


class Halt(Exception):
    """
    Raised to halt command execution and transition to failed state.
    Similar to Ruby Foobara's Halt exception.
    """

    __slots__ = ()


class CommandStateMachine:
    """
    High-performance state machine for command execution.

    Uses __slots__ for memory efficiency and fast attribute access.
    """

    __slots__ = ("_state", "_transition_history")

    def __init__(self):
        self._state: CommandState = CommandState.INITIALIZED
        self._transition_history: List[Tuple[CommandState, CommandState]] = []

    @property
    def state(self) -> CommandState:
        """Current state"""
        return self._state

    @property
    def is_terminal(self) -> bool:
        """Check if in terminal state"""
        return self._state in TERMINAL_STATES

    @property
    def can_fail(self) -> bool:
        """Check if can transition to failed"""
        return self._state in CAN_FAIL_STATES

    def transition_to(self, new_state: CommandState) -> bool:
        """
        Transition to new state if valid.

        Returns True if transition succeeded, False otherwise.
        """
        if new_state in VALID_TRANSITIONS.get(self._state, set()):
            self._transition_history.append((self._state, new_state))
            self._state = new_state
            return True
        return False

    def fail(self) -> bool:
        """Transition to failed state"""
        return self.transition_to(CommandState.FAILED)

    def error(self) -> bool:
        """Transition to errored state"""
        return self.transition_to(CommandState.ERRORED)

    def succeed(self) -> bool:
        """Transition to succeeded state"""
        return self.transition_to(CommandState.SUCCEEDED)

    def reset(self) -> None:
        """Reset to initial state"""
        self._state = CommandState.INITIALIZED
        self._transition_history.clear()


# State name mapping for display
STATE_NAMES: dict = {
    CommandState.INITIALIZED: "initialized",
    CommandState.OPENING_TRANSACTION: "opening_transaction",
    CommandState.CASTING_AND_VALIDATING_INPUTS: "cast_and_validate_inputs",
    CommandState.LOADING_RECORDS: "load_records",
    CommandState.VALIDATING_RECORDS: "validate_records",
    CommandState.VALIDATING: "validate",
    CommandState.EXECUTING: "execute",
    CommandState.COMMITTING_TRANSACTION: "commit_transaction",
    CommandState.SUCCEEDED: "succeeded",
    CommandState.FAILED: "failed",
    CommandState.ERRORED: "errored",
}
