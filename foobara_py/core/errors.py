"""
Enhanced error system with full Ruby Foobara compatibility.

Key features:
- runtime_path for subcommand error tracking
- Composite error keys matching Ruby format
- Error context typing
- Fatal error support
- High-performance using __slots__
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Literal, Optional, Tuple, Union


@dataclass(slots=True, frozen=False)
class FoobaraError:
    """
    Enhanced error class with full Ruby Foobara compatibility.

    Error key format: runtime_path>category.data_path.symbol
    Example: "subcommand>data.user.email.invalid_format"

    Using dataclass with slots for performance.
    """

    category: Literal["data", "runtime", "system"] = "data"
    symbol: str = ""
    path: Tuple[str, ...] = ()  # Using tuple for immutability
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    runtime_path: Tuple[str, ...] = ()  # Path through subcommands
    is_fatal: bool = False

    def __post_init__(self):
        """Convert list paths to tuples for immutability"""
        if isinstance(self.path, list):
            object.__setattr__(self, 'path', tuple(self.path))
        if isinstance(self.runtime_path, list):
            object.__setattr__(self, 'runtime_path', tuple(self.runtime_path))

    def key(self) -> str:
        """
        Generate composite error key matching Ruby Foobara format.

        Format: [runtime_path>]category.data_path.symbol

        Examples:
            "data.user.email.invalid_format"
            "subcommand>data.field.required"
            "outer>inner>runtime.root.execution_error"
        """
        parts = []

        # Runtime path prefix
        if self.runtime_path:
            parts.append(">".join(self.runtime_path) + ">")

        # Category
        parts.append(self.category)

        # Data path
        if self.path:
            parts.append(".")
            parts.append(".".join(self.path))
        else:
            # Empty path means root level
            parts.append(".root")

        # Symbol
        parts.append(".")
        parts.append(self.symbol)

        return "".join(parts)

    def with_runtime_path_prefix(self, *prefix: str) -> "FoobaraError":
        """Return new error with runtime path prefix added"""
        return FoobaraError(
            category=self.category,
            symbol=self.symbol,
            path=self.path,
            message=self.message,
            context=self.context,
            runtime_path=tuple(prefix) + self.runtime_path,
            is_fatal=self.is_fatal,
        )

    def with_path_prefix(self, *prefix: str) -> "FoobaraError":
        """Return new error with data path prefix added"""
        return FoobaraError(
            category=self.category,
            symbol=self.symbol,
            path=tuple(prefix) + self.path,
            message=self.message,
            context=self.context,
            runtime_path=self.runtime_path,
            is_fatal=self.is_fatal,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary matching Ruby format"""
        return {
            "key": self.key(),
            "category": self.category,
            "symbol": self.symbol,
            "path": list(self.path),
            "runtime_path": list(self.runtime_path),
            "message": self.message,
            "context": self.context,
            "is_fatal": self.is_fatal,
        }

    @classmethod
    def data_error(
        cls, symbol: str, path: Union[List[str], Tuple[str, ...]], message: str, **context
    ) -> "FoobaraError":
        """Factory for data category errors"""
        return cls(
            category="data",
            symbol=symbol,
            path=tuple(path) if isinstance(path, list) else path,
            message=message,
            context=context,
        )

    @classmethod
    def runtime_error(
        cls, symbol: str, message: str, is_fatal: bool = False, **context
    ) -> "FoobaraError":
        """Factory for runtime category errors"""
        return cls(
            category="runtime",
            symbol=symbol,
            path=(),
            message=message,
            context=context,
            is_fatal=is_fatal,
        )

    @classmethod
    def system_error(
        cls, symbol: str, message: str, is_fatal: bool = True, **context
    ) -> "FoobaraError":
        """Factory for system category errors"""
        return cls(
            category="system",
            symbol=symbol,
            path=(),
            message=message,
            context=context,
            is_fatal=is_fatal,
        )


class ErrorCollection:
    """
    High-performance error collection with Ruby Foobara compatibility.

    Features:
    - Indexed by composite key for O(1) lookup
    - Maintains insertion order
    - Supports path-based queries
    - Tracks fatal errors
    - Uses __slots__ for memory efficiency
    """

    __slots__ = ("_errors", "_has_fatal")

    def __init__(self):
        self._errors: Dict[str, FoobaraError] = {}
        self._has_fatal: bool = False

    def add(self, error: FoobaraError) -> "ErrorCollection":
        """Add error to collection"""
        key = error.key()
        self._errors[key] = error
        if error.is_fatal:
            self._has_fatal = True
        return self

    def add_all(self, *errors: FoobaraError) -> "ErrorCollection":
        """Add multiple errors"""
        for error in errors:
            self.add(error)
        return self

    # Backward compatibility aliases (V1 used add_error/add_errors, V2 uses add/add_all)
    def add_error(self, error: FoobaraError) -> "ErrorCollection":
        """Backward compatibility alias for add()"""
        return self.add(error)

    def add_errors(self, *errors: FoobaraError) -> "ErrorCollection":
        """Backward compatibility alias for add_all()"""
        return self.add_all(*errors)

    def merge(self, other: "ErrorCollection") -> "ErrorCollection":
        """Merge another collection into this one"""
        for error in other:
            self.add(error)
        return self

    def has_errors(self) -> bool:
        """Check if collection has any errors"""
        return len(self._errors) > 0

    def has_fatal(self) -> bool:
        """Check if any error is fatal"""
        return self._has_fatal

    def is_empty(self) -> bool:
        """Check if collection is empty"""
        return len(self._errors) == 0

    def count(self) -> int:
        """Get the number of errors in the collection"""
        return len(self._errors)

    def __len__(self) -> int:
        return len(self._errors)

    def __iter__(self) -> Iterator[FoobaraError]:
        return iter(self._errors.values())

    def __bool__(self) -> bool:
        return self.has_errors()

    def __contains__(self, key: str) -> bool:
        return key in self._errors

    def get(self, key: str) -> Optional[FoobaraError]:
        """Get error by key"""
        return self._errors.get(key)

    def first(self) -> Optional[FoobaraError]:
        """Get first error or None"""
        if self._errors:
            return next(iter(self._errors.values()))
        return None

    def all(self) -> List[FoobaraError]:
        """Get all errors as list"""
        return list(self._errors.values())

    def keys(self) -> List[str]:
        """Get all error keys"""
        return list(self._errors.keys())

    # Query methods

    def at_path(self, path: Union[List[str], Tuple[str, ...], str], *rest: str) -> List[FoobaraError]:
        """Get all errors at specific data path"""
        # Handle both at_path(["email"]) and at_path("user", "email")
        if rest:
            # Variadic form: at_path("user", "email")
            target = (path,) + rest if isinstance(path, str) else tuple(path) + rest
        elif isinstance(path, (list, tuple)):
            # Single arg form: at_path(["email"])
            target = tuple(path)
        else:
            # Single string: at_path("email")
            target = (path,)
        return [e for e in self._errors.values() if e.path == target]

    def with_symbol(self, symbol: str) -> List[FoobaraError]:
        """Get all errors with specific symbol"""
        return [e for e in self._errors.values() if e.symbol == symbol]

    def by_category(self, category: str) -> List[FoobaraError]:
        """Get all errors in category"""
        return [e for e in self._errors.values() if e.category == category]

    def in_runtime_path(self, *path: str) -> List[FoobaraError]:
        """Get errors with runtime path prefix"""
        prefix = tuple(path)
        prefix_len = len(prefix)
        return [
            e
            for e in self._errors.values()
            if len(e.runtime_path) >= prefix_len and e.runtime_path[:prefix_len] == prefix
        ]

    def fatal_errors(self) -> List[FoobaraError]:
        """Get all fatal errors"""
        return [e for e in self._errors.values() if e.is_fatal]

    def data_errors(self) -> List[FoobaraError]:
        """Get all data category errors"""
        return self.by_category("data")

    def runtime_errors(self) -> List[FoobaraError]:
        """Get all runtime category errors"""
        return self.by_category("runtime")

    # Serialization

    def messages(self) -> List[str]:
        """Get all error messages"""
        return [e.message for e in self._errors.values()]

    def to_sentence(self) -> str:
        """Join messages into sentence"""
        msgs = self.messages()
        if not msgs:
            return ""
        if len(msgs) == 1:
            return msgs[0]
        return ", ".join(msgs[:-1]) + " and " + msgs[-1]

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Serialize to dictionary format matching Ruby Foobara's errors_hash.

        Returns dict keyed by error key with full error details.
        """
        return {key: error.to_dict() for key, error in self._errors.items()}

    def to_list(self) -> List[Dict[str, Any]]:
        """Serialize to list format for JSON responses"""
        return [error.to_dict() for error in self._errors.values()]

    def clear(self) -> None:
        """Clear all errors"""
        self._errors.clear()
        self._has_fatal = False

    def copy(self) -> "ErrorCollection":
        """Create a copy of this collection"""
        new_collection = ErrorCollection()
        new_collection._errors = self._errors.copy()
        new_collection._has_fatal = self._has_fatal
        return new_collection


# Standard error symbols matching Ruby Foobara
class Symbols:
    """Standard error symbols for common validation errors"""

    # Data validation
    REQUIRED = "required"
    MISSING_REQUIRED_ATTRIBUTE = "missing_required_attribute"
    UNEXPECTED_ATTRIBUTE = "unexpected_attribute"
    CANNOT_CAST = "cannot_cast"
    INVALID_TYPE = "invalid_type"
    INVALID_FORMAT = "invalid_format"
    INVALID_VALUE = "invalid_value"

    # String constraints
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    BLANK = "blank"

    # Numeric constraints
    TOO_SMALL = "too_small"
    TOO_LARGE = "too_large"
    NOT_INTEGER = "not_integer"
    NOT_POSITIVE = "not_positive"
    NOT_NEGATIVE = "not_negative"

    # Records/entities
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    RECORD_NOT_FOUND = "record_not_found"
    RECORD_NOT_UNIQUE = "record_not_unique"

    # Authorization
    NOT_ALLOWED = "not_allowed"
    NOT_AUTHENTICATED = "not_authenticated"
    FORBIDDEN = "forbidden"

    # Runtime
    EXECUTION_ERROR = "execution_error"
    SUBCOMMAND_ERROR = "subcommand_error"
    TRANSACTION_ERROR = "transaction_error"
    TIMEOUT = "timeout"

    # HTTP/API
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    CONNECTION_FAILED = "connection_failed"


# Backward compatibility alias
DataError = FoobaraError
ErrorSymbols = Symbols
