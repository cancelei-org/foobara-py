"""
ExecutionConcern - Core command execution and lifecycle hooks.

Handles:
- Main execute() method (abstract)
- Lifecycle hooks (before_execute, after_execute)
- Result storage
- Class-level run() method

Pattern: Ruby Foobara's Runtime concern
"""

from abc import abstractmethod
from typing import Generic, Optional, TypeVar

ResultT = TypeVar("ResultT")


class ExecutionConcern(Generic[ResultT]):
    """Mixin for command execution and lifecycle."""

    # Instance attributes (defined in __slots__ in Command)
    _result: Optional[ResultT]

    def before_execute(self) -> None:
        """
        Lifecycle hook called before execute().

        Override to add logic that runs before the main execute() method.
        Add errors via add_error() to prevent execute() from running.
        """
        pass

    def after_execute(self, result: ResultT) -> ResultT:
        """
        Lifecycle hook called after execute().

        Override to transform or process the result after execute() completes.
        Return the potentially modified result.

        Args:
            result: The result returned from execute()

        Returns:
            The final result (can be transformed)
        """
        return result

    @abstractmethod
    def execute(self) -> ResultT:
        """
        Execute command business logic.

        Override this method to implement command behavior.
        Return the result value on success.

        Returns:
            Command result

        Raises:
            Halt: To stop execution and fail the command
        """
        pass

    @classmethod
    def run(cls, **inputs) -> "CommandOutcome[ResultT]":
        """
        Create and run command with given inputs.

        Args:
            **inputs: Raw input dictionary

        Returns:
            CommandOutcome with result or errors
        """
        instance = cls(**inputs)
        return instance.run_instance()
