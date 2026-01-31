"""
ErrorsConcern - Error handling and collection for commands.

Handles:
- Error collection management
- Adding input/runtime errors
- Halting execution
- Error context with runtime paths (for subcommands)

Pattern: Ruby Foobara's Errors concern
"""

from typing import Any, Dict, List, Tuple, Union

from foobara_py.core.errors import ErrorCollection, FoobaraError
from foobara_py.core.state_machine import Halt


class ErrorsConcern:
    """Mixin for error handling and collection."""

    # Instance attributes (defined in __slots__ in Command)
    _errors: ErrorCollection
    _subcommand_runtime_path: Tuple[str, ...]

    @property
    def errors(self) -> ErrorCollection:
        """
        Get error collection.

        Returns:
            ErrorCollection containing all errors
        """
        return self._errors

    def add_error(self, error: FoobaraError) -> None:
        """
        Add an error to the collection.

        If this is a subcommand, automatically prefixes the error's
        runtime path with the parent command path.

        Args:
            error: The error to add
        """
        # Add runtime path prefix if we're a subcommand
        if self._subcommand_runtime_path:
            error = error.with_runtime_path_prefix(*self._subcommand_runtime_path)
        self._errors.add(error)

    def add_input_error(
        self, path: Union[List[str], Tuple[str, ...]], symbol: str, message: str, **context
    ) -> None:
        """
        Add an input validation error.

        Args:
            path: Path to the invalid input field (e.g., ["user", "email"])
            symbol: Error symbol (e.g., "invalid_email")
            message: Human-readable error message
            **context: Additional error context
        """
        self.add_error(FoobaraError.data_error(symbol, path, message, **context))

    def add_runtime_error(self, symbol: str, message: str, halt: bool = True, **context) -> None:
        """
        Add a runtime error, optionally halting execution.

        Args:
            symbol: Error symbol (e.g., "division_by_zero")
            message: Human-readable error message
            halt: Whether to halt execution after adding error (default: True)
            **context: Additional error context

        Raises:
            Halt: If halt=True
        """
        self.add_error(FoobaraError.runtime_error(symbol, message, **context))
        if halt:
            raise Halt()

    def halt(self) -> None:
        """
        Halt command execution immediately.

        Transitions command to failed state.

        Raises:
            Halt: Always
        """
        raise Halt()

    @classmethod
    def possible_error(
        cls, symbol: str, message: str = None, context: Dict[str, Any] = None
    ) -> None:
        """
        Declare a possible error for this command.

        Args:
            symbol: Error symbol
            message: Optional error message template
            context: Optional context schema
        """
        cls._possible_errors[symbol] = {
            "symbol": symbol,
            "message": message,
            "context": context or {},
        }

    @classmethod
    def possible_errors(cls) -> List[Dict[str, Any]]:
        """
        Get all declared possible errors for this command.

        Returns:
            List of error dicts with symbol and message
        """
        return [
            {"symbol": symbol, "message": details.get("message")}
            for symbol, details in cls._possible_errors.items()
        ]
