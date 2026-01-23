"""
Outcome monad for foobara-py

Provides Success/Failure types for command results, avoiding exception-based
error handling for expected business logic failures.

Inspired by Foobara's Outcome pattern and Rust's Result type.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field

T = TypeVar("T")  # Success result type
E = TypeVar("E")  # Error type


class OutcomeBase(ABC, Generic[T]):
    """Abstract base for Success and Failure outcomes"""

    @abstractmethod
    def is_success(self) -> bool:
        """Check if outcome is successful"""
        pass

    @abstractmethod
    def is_failure(self) -> bool:
        """Check if outcome is a failure"""
        pass

    @abstractmethod
    def unwrap(self) -> T:
        """Get the result value, raises if failure"""
        pass

    @abstractmethod
    def unwrap_or(self, default: T) -> T:
        """Get the result or return default if failure"""
        pass


class Success(BaseModel, Generic[T]):
    """
    Successful command outcome containing the result.

    Example:
        outcome = Success(result={"id": 1, "name": "John"})
        if outcome.is_success():
            user = outcome.unwrap()
    """

    result: T

    def is_success(self) -> bool:
        return True

    def is_failure(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.result

    def unwrap_or(self, default: T) -> T:
        return self.result

    def map(self, fn) -> "Success":
        """Apply function to result, return new Success"""
        return Success(result=fn(self.result))


class Failure(BaseModel, Generic[E]):
    """
    Failed command outcome containing errors.

    Example:
        error = DataError(symbol="invalid_email", path=["email"], message="Invalid format")
        outcome = Failure(errors=[error])
        if outcome.is_failure():
            print(outcome.error_messages())
    """

    errors: List[E] = Field(default_factory=list)

    def is_success(self) -> bool:
        return False

    def is_failure(self) -> bool:
        return True

    def unwrap(self) -> Any:
        error_msgs = self.error_messages() if hasattr(self, "error_messages") else str(self.errors)
        raise ValueError(f"Called unwrap on failure: {error_msgs}")

    def unwrap_or(self, default: T) -> T:
        return default

    def error_messages(self) -> List[str]:
        """Get list of error messages"""
        messages = []
        for error in self.errors:
            if hasattr(error, "message"):
                messages.append(error.message)
            else:
                messages.append(str(error))
        return messages

    def first_error(self) -> Optional[E]:
        """Get first error if any"""
        return self.errors[0] if self.errors else None


# Type alias for Outcome
Outcome = Union[Success[T], Failure[E]]


class CommandOutcome(BaseModel, Generic[T]):
    """
    Unified command outcome (alternative pattern).

    Provides a single type that can represent both success and failure,
    similar to Foobara's Outcome class.

    Example:
        # Success case
        outcome = CommandOutcome.success(user_data)

        # Failure case
        outcome = CommandOutcome.failure(
            DataError(symbol="not_found", path=["id"], message="User not found")
        )

        if outcome.success():
            print(outcome.result)
        else:
            for error in outcome.errors:
                print(f"{error.path}: {error.message}")
    """

    result: Optional[T] = None
    errors: List[Any] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    def is_success(self) -> bool:
        """Check if outcome is successful (no errors)"""
        return len(self.errors) == 0

    def is_failure(self) -> bool:
        """Check if outcome has errors"""
        return len(self.errors) > 0

    # Aliases for compatibility
    success = is_success
    failure = is_failure

    @classmethod
    def from_result(cls, result: T, **metadata) -> "CommandOutcome[T]":
        """Create successful outcome from result"""
        return cls(result=result, errors=[], metadata=metadata)

    @classmethod
    def from_errors(cls, *errors, **metadata) -> "CommandOutcome[T]":
        """Create failure outcome from errors"""
        return cls(result=None, errors=list(errors), metadata=metadata)

    def unwrap(self) -> T:
        """Get result, raises if failure"""
        if self.is_success():
            return self.result
        error_messages = [e.message if hasattr(e, "message") else str(e) for e in self.errors]
        raise ValueError(f"Command failed: {', '.join(error_messages)}")

    def unwrap_or(self, default: T) -> T:
        """Get result or default if failure"""
        if self.is_success():
            return self.result
        return default

    def map(self, fn) -> "CommandOutcome":
        """Apply function to result if successful"""
        if self.is_success():
            return CommandOutcome.from_result(fn(self.result), **self.metadata)
        return self

    def flat_map(self, fn) -> "CommandOutcome":
        """Apply function returning CommandOutcome if successful"""
        if self.is_success():
            return fn(self.result)
        return self

    def add_error(self, error) -> "CommandOutcome[T]":
        """Add error and return self (for chaining)"""
        self.errors.append(error)
        return self

    def to_dict(self) -> dict:
        """Serialize outcome for API responses"""
        if self.is_success():
            return {"success": True, "result": self.result, "metadata": self.metadata}
        else:
            return {
                "success": False,
                "errors": [
                    e.model_dump() if hasattr(e, "model_dump") else str(e) for e in self.errors
                ],
                "metadata": self.metadata,
            }
