"""Simple command concern base class."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

TInputs = TypeVar("TInputs")
TResult = TypeVar("TResult")


class SimpleCommandConcern(ABC, Generic[TInputs, TResult]):
    """
    Base class for simple command concerns.

    A concern is a reusable piece of command behavior that can be mixed
    into command classes. Simple concerns provide lifecycle hooks that
    run before and after command execution.

    Type Parameters:
        TInputs: The command's input type
        TResult: The command's result type

    Example:
        >>> class LoggingConcern(SimpleCommandConcern[Any, Any]):
        ...     def before_execute(self, inputs: Any) -> None:
        ...         print(f"Executing with {inputs}")
        ...
        ...     def after_execute(self, result: Any) -> Any:
        ...         print(f"Completed with {result}")
        ...         return result
    """

    def before_execute(self, inputs: TInputs) -> None:
        """
        Hook called before command execution.

        Args:
            inputs: The validated command inputs

        This method can be used for logging, setting up resources,
        or performing pre-execution checks.
        """
        pass

    def after_execute(self, result: TResult) -> TResult:
        """
        Hook called after successful command execution.

        Args:
            result: The command result

        Returns:
            The result (possibly modified)

        This method can be used for logging, cleanup, or transforming
        the result before it's returned.
        """
        return result

    def on_error(self, error: Exception) -> None:
        """
        Hook called when command execution fails.

        Args:
            error: The exception that was raised

        This method can be used for error logging, cleanup, or
        error reporting. It should not suppress the error.
        """
        pass
