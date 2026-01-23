"""
⚠️  DEPRECATED V1 IMPLEMENTATION ⚠️

This file is deprecated as of v0.3.0 and will be removed in v0.4.0.

DO NOT USE THIS FILE. Use the current implementation instead:
    from foobara_py import FoobaraError, ErrorCollection, DataError

---

Error types for foobara-py (LEGACY V1)

Provides structured error types with path tracking, similar to Foobara's
error system with hierarchical error keys.
"""

import warnings

warnings.warn(
    "foobara_py._deprecated.core.errors_v1 is deprecated and will be removed in v0.4.0. "
    "Use 'from foobara_py import FoobaraError, ErrorCollection' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DataError(BaseModel):
    """
    Structured data/validation error with path tracking.

    Corresponds to Foobara's DataError with:
    - category: Error category (data, runtime, system)
    - symbol: Error identifier (e.g., 'invalid_email', 'too_short')
    - path: Path to the field with error (e.g., ['user', 'email'])
    - message: Human-readable error message
    - context: Additional error context

    Example:
        error = DataError(
            symbol="invalid_format",
            path=["user", "email"],
            message="Email must contain @ symbol"
        )
        print(error.key())  # "data.user.email.invalid_format"
    """

    category: Literal["data", "runtime", "system"] = "data"
    symbol: str
    path: List[str] = Field(default_factory=list)
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)

    def key(self) -> str:
        """
        Generate hierarchical error key like Foobara.

        Format: category.path.symbol
        Example: "data.user.email.invalid_format"
        """
        path_str = ".".join(self.path) if self.path else "root"
        return f"{self.category}.{path_str}.{self.symbol}"

    @classmethod
    def data_error(cls, symbol: str, path: List[str], message: str, **context) -> "DataError":
        """Factory for data category errors"""
        return cls(category="data", symbol=symbol, path=path, message=message, context=context)

    @classmethod
    def runtime_error(cls, symbol: str, message: str, **context) -> "DataError":
        """Factory for runtime category errors"""
        return cls(category="runtime", symbol=symbol, path=[], message=message, context=context)

    @classmethod
    def system_error(cls, symbol: str, message: str, **context) -> "DataError":
        """Factory for system category errors"""
        return cls(category="system", symbol=symbol, path=[], message=message, context=context)

    def with_path_prefix(self, *prefix: str) -> "DataError":
        """Return new error with path prefix added"""
        return DataError(
            category=self.category,
            symbol=self.symbol,
            path=list(prefix) + self.path,
            message=self.message,
            context=self.context,
        )


class ErrorCollection(BaseModel):
    """
    Collection of errors with hierarchy support.

    Similar to Foobara's ErrorCollection, provides methods to:
    - Add errors with automatic key generation
    - Query errors by path
    - Serialize to dictionary format

    Example:
        errors = ErrorCollection()
        errors.add_error(DataError.data_error(
            symbol="required",
            path=["name"],
            message="Name is required"
        ))
        errors.add_error(DataError.data_error(
            symbol="invalid_format",
            path=["email"],
            message="Invalid email format"
        ))

        print(errors.has_errors())  # True
        print(errors.at_path(["email"]))  # [DataError(...)]
    """

    errors: Dict[str, DataError] = Field(default_factory=dict)

    def add_error(self, error: DataError) -> "ErrorCollection":
        """Add error to collection, keyed by error.key()"""
        key = error.key()
        self.errors[key] = error
        return self

    def add_errors(self, *errors: DataError) -> "ErrorCollection":
        """Add multiple errors"""
        for error in errors:
            self.add_error(error)
        return self

    def has_errors(self) -> bool:
        """Check if collection has any errors"""
        return len(self.errors) > 0

    def is_empty(self) -> bool:
        """Check if collection is empty"""
        return len(self.errors) == 0

    def count(self) -> int:
        """Get number of errors"""
        return len(self.errors)

    def at_path(self, path: List[str]) -> List[DataError]:
        """Get all errors at a specific path"""
        return [e for e in self.errors.values() if e.path == path]

    def with_symbol(self, symbol: str) -> List[DataError]:
        """Get all errors with a specific symbol"""
        return [e for e in self.errors.values() if e.symbol == symbol]

    def by_category(self, category: str) -> List[DataError]:
        """Get all errors in a category"""
        return [e for e in self.errors.values() if e.category == category]

    def first(self) -> Optional[DataError]:
        """Get first error or None"""
        if self.errors:
            return next(iter(self.errors.values()))
        return None

    def all(self) -> List[DataError]:
        """Get all errors as list"""
        return list(self.errors.values())

    def messages(self) -> List[str]:
        """Get all error messages"""
        return [e.message for e in self.errors.values()]

    def to_dict(self) -> Dict[str, dict]:
        """
        Serialize to dictionary format like Foobara's errors_hash.

        Returns dict keyed by error key with full error details.
        """
        return {
            key: {
                "key": key,
                "path": error.path,
                "message": error.message,
                "category": error.category,
                "symbol": error.symbol,
                "context": error.context,
            }
            for key, error in self.errors.items()
        }

    def merge(self, other: "ErrorCollection") -> "ErrorCollection":
        """Merge another error collection into this one"""
        for key, error in other.errors.items():
            self.errors[key] = error
        return self


# Common error symbols (like Foobara's built-in errors)
class ErrorSymbols:
    """Standard error symbols for common validation errors"""

    REQUIRED = "required"
    INVALID_FORMAT = "invalid_format"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    TOO_SMALL = "too_small"
    TOO_LARGE = "too_large"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    NOT_ALLOWED = "not_allowed"
    INVALID_TYPE = "invalid_type"
    INVALID_VALUE = "invalid_value"
