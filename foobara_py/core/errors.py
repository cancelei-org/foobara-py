"""
Enhanced error system with full Ruby Foobara compatibility.

Key features:
- runtime_path for subcommand error tracking
- Composite error keys matching Ruby format
- Error context typing
- Fatal error support
- Error chaining and causality tracking
- Stack trace support for debugging
- Severity levels and error priorities
- Actionable suggestions for fixes
- High-performance using __slots__
"""

import sys
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterator, List, Literal, Optional, Tuple, Union


class ErrorSeverity(str, Enum):
    """Error severity levels for prioritization"""

    DEBUG = "debug"  # Informational, not really an error
    INFO = "info"  # Minor issue, operation can continue
    WARNING = "warning"  # Potential problem, should be addressed
    ERROR = "error"  # Standard error, operation failed
    CRITICAL = "critical"  # Severe error, system-level impact
    FATAL = "fatal"  # Unrecoverable error, immediate halt required


class ErrorCategory(str, Enum):
    """Enhanced error categories matching Ruby patterns"""

    # Data/validation errors
    DATA = "data"
    VALIDATION = "validation"
    INPUT = "input"

    # Runtime errors
    RUNTIME = "runtime"
    EXECUTION = "execution"

    # Domain/business logic errors
    DOMAIN = "domain"
    BUSINESS_RULE = "business_rule"

    # System/infrastructure errors
    SYSTEM = "system"
    INFRASTRUCTURE = "infrastructure"

    # Authorization/authentication
    AUTH = "auth"
    AUTHORIZATION = "authorization"
    AUTHENTICATION = "authentication"

    # External service errors
    EXTERNAL = "external"
    NETWORK = "network"
    API = "api"


@dataclass(slots=True, frozen=False)
class FoobaraError:
    """
    Enhanced error class with full Ruby Foobara compatibility.

    Error key format: runtime_path>category.data_path.symbol
    Example: "subcommand>data.user.email.invalid_format"

    New features:
    - Error chaining via 'cause' field
    - Stack traces for debugging
    - Severity levels for prioritization
    - Actionable suggestions for fixes
    - Timestamps for error tracking

    Using dataclass with slots for performance.
    """

    category: Literal["data", "runtime", "system"] = "data"
    symbol: str = ""
    path: Tuple[str, ...] = ()  # Using tuple for immutability
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    runtime_path: Tuple[str, ...] = ()  # Path through subcommands
    is_fatal: bool = False

    # Enhanced fields
    cause: Optional["FoobaraError"] = None  # Error that caused this error
    severity: ErrorSeverity = ErrorSeverity.ERROR
    suggestion: Optional[str] = None  # Actionable suggestion for fixing
    stack_trace: Optional[List[str]] = None  # Stack trace for debugging
    timestamp: Optional[float] = None  # When error occurred
    error_code: Optional[str] = None  # Machine-readable error code
    help_url: Optional[str] = None  # Link to documentation

    def __post_init__(self):
        """Convert list paths to tuples for immutability and set defaults"""
        if isinstance(self.path, list):
            object.__setattr__(self, "path", tuple(self.path))
        if isinstance(self.runtime_path, list):
            object.__setattr__(self, "runtime_path", tuple(self.runtime_path))

        # Set timestamp if not provided
        if self.timestamp is None:
            import time

            object.__setattr__(self, "timestamp", time.time())

        # Generate error code if not provided
        if self.error_code is None:
            code = f"{self.category}.{self.symbol}"
            if self.path:
                code = f"{self.category}.{'.'.join(self.path)}.{self.symbol}"
            object.__setattr__(self, "error_code", code)

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

    def capture_stack_trace(self) -> "FoobaraError":
        """Capture current stack trace and attach to error"""
        stack = traceback.format_stack()[:-1]  # Exclude this function call
        object.__setattr__(self, "stack_trace", stack)
        return self

    def with_cause(self, cause: "FoobaraError") -> "FoobaraError":
        """Return new error with cause attached"""
        return FoobaraError(
            category=self.category,
            symbol=self.symbol,
            path=self.path,
            message=self.message,
            context=self.context,
            runtime_path=self.runtime_path,
            is_fatal=self.is_fatal,
            cause=cause,
            severity=self.severity,
            suggestion=self.suggestion,
            stack_trace=self.stack_trace,
            timestamp=self.timestamp,
            error_code=self.error_code,
            help_url=self.help_url,
        )

    def with_suggestion(self, suggestion: str) -> "FoobaraError":
        """Return new error with suggestion attached"""
        return FoobaraError(
            category=self.category,
            symbol=self.symbol,
            path=self.path,
            message=self.message,
            context=self.context,
            runtime_path=self.runtime_path,
            is_fatal=self.is_fatal,
            cause=self.cause,
            severity=self.severity,
            suggestion=suggestion,
            stack_trace=self.stack_trace,
            timestamp=self.timestamp,
            error_code=self.error_code,
            help_url=self.help_url,
        )

    def get_error_chain(self) -> List["FoobaraError"]:
        """Get full chain of errors (this error plus all causes)"""
        chain = [self]
        current = self.cause
        while current is not None:
            chain.append(current)
            current = current.cause
        return chain

    def get_root_cause(self) -> "FoobaraError":
        """Get the root cause of this error"""
        current = self
        while current.cause is not None:
            current = current.cause
        return current

    def to_dict(self, include_stack_trace: bool = False) -> Dict[str, Any]:
        """
        Serialize to dictionary matching Ruby format with enhancements.

        Args:
            include_stack_trace: Include stack trace in output (for debugging)
        """
        result = {
            "key": self.key(),
            "category": self.category,
            "symbol": self.symbol,
            "path": list(self.path),
            "runtime_path": list(self.runtime_path),
            "message": self.message,
            "context": self.context,
            "is_fatal": self.is_fatal,
            "severity": self.severity.value,
            "error_code": self.error_code,
        }

        # Optional fields
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.help_url:
            result["help_url"] = self.help_url
        if self.timestamp:
            result["timestamp"] = self.timestamp

        # Include cause chain
        if self.cause:
            result["cause"] = self.cause.to_dict(include_stack_trace)

        # Include stack trace if requested
        if include_stack_trace and self.stack_trace:
            result["stack_trace"] = self.stack_trace

        return result

    @classmethod
    def data_error(
        cls,
        symbol: str,
        path: Union[List[str], Tuple[str, ...]],
        message: str,
        suggestion: Optional[str] = None,
        **context,
    ) -> "FoobaraError":
        """Factory for data/validation category errors"""
        return cls(
            category="data",
            symbol=symbol,
            path=tuple(path) if isinstance(path, list) else path,
            message=message,
            context=context,
            severity=ErrorSeverity.ERROR,
            suggestion=suggestion,
        )

    @classmethod
    def validation_error(
        cls,
        symbol: str,
        path: Union[List[str], Tuple[str, ...]],
        message: str,
        suggestion: Optional[str] = None,
        **context,
    ) -> "FoobaraError":
        """Factory for validation errors (alias for data_error)"""
        return cls.data_error(symbol, path, message, suggestion, **context)

    @classmethod
    def runtime_error(
        cls,
        symbol: str,
        message: str,
        is_fatal: bool = False,
        suggestion: Optional[str] = None,
        **context,
    ) -> "FoobaraError":
        """Factory for runtime category errors"""
        return cls(
            category="runtime",
            symbol=symbol,
            path=(),
            message=message,
            context=context,
            is_fatal=is_fatal,
            severity=ErrorSeverity.CRITICAL if is_fatal else ErrorSeverity.ERROR,
            suggestion=suggestion,
        )

    @classmethod
    def domain_error(
        cls,
        symbol: str,
        message: str,
        path: Union[List[str], Tuple[str, ...]] = (),
        suggestion: Optional[str] = None,
        **context,
    ) -> "FoobaraError":
        """Factory for domain/business rule errors"""
        return cls(
            category="domain",
            symbol=symbol,
            path=tuple(path) if isinstance(path, list) else path,
            message=message,
            context=context,
            severity=ErrorSeverity.ERROR,
            suggestion=suggestion,
        )

    @classmethod
    def system_error(
        cls,
        symbol: str,
        message: str,
        is_fatal: bool = True,
        suggestion: Optional[str] = None,
        **context,
    ) -> "FoobaraError":
        """Factory for system category errors"""
        return cls(
            category="system",
            symbol=symbol,
            path=(),
            message=message,
            context=context,
            is_fatal=is_fatal,
            severity=ErrorSeverity.FATAL if is_fatal else ErrorSeverity.CRITICAL,
            suggestion=suggestion,
        )

    @classmethod
    def auth_error(
        cls, symbol: str, message: str, suggestion: Optional[str] = None, **context
    ) -> "FoobaraError":
        """Factory for authentication/authorization errors"""
        return cls(
            category="auth",
            symbol=symbol,
            path=(),
            message=message,
            context=context,
            severity=ErrorSeverity.ERROR,
            suggestion=suggestion,
        )

    @classmethod
    def external_error(
        cls,
        symbol: str,
        message: str,
        service: Optional[str] = None,
        suggestion: Optional[str] = None,
        **context,
    ) -> "FoobaraError":
        """Factory for external service errors"""
        if service:
            context["service"] = service
        return cls(
            category="external",
            symbol=symbol,
            path=(),
            message=message,
            context=context,
            severity=ErrorSeverity.WARNING,
            suggestion=suggestion,
        )

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        symbol: str = "exception",
        category: str = "runtime",
        include_traceback: bool = True,
    ) -> "FoobaraError":
        """
        Create FoobaraError from a Python exception.

        Args:
            exception: The exception to convert
            symbol: Error symbol to use
            category: Error category
            include_traceback: Whether to capture stack trace

        Returns:
            FoobaraError instance
        """
        error = cls(
            category=category,
            symbol=symbol,
            path=(),
            message=str(exception),
            context={
                "exception_type": type(exception).__name__,
                "exception_module": type(exception).__module__,
            },
            severity=ErrorSeverity.ERROR,
        )

        if include_traceback:
            tb_lines = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
            object.__setattr__(error, "stack_trace", tb_lines)

        return error


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

    def system_errors(self) -> List[FoobaraError]:
        """Get all system category errors"""
        return self.by_category("system")

    def domain_errors(self) -> List[FoobaraError]:
        """Get all domain category errors"""
        return self.by_category("domain")

    def auth_errors(self) -> List[FoobaraError]:
        """Get all auth category errors"""
        return self.by_category("auth")

    def by_severity(self, severity: Union[ErrorSeverity, str]) -> List[FoobaraError]:
        """Get all errors with specific severity level"""
        if isinstance(severity, str):
            severity = ErrorSeverity(severity)
        return [e for e in self._errors.values() if e.severity == severity]

    def critical_errors(self) -> List[FoobaraError]:
        """Get all critical and fatal severity errors"""
        return [
            e
            for e in self._errors.values()
            if e.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.FATAL)
        ]

    def sort_by_severity(self) -> List[FoobaraError]:
        """
        Get all errors sorted by severity (most severe first).

        Order: FATAL > CRITICAL > ERROR > WARNING > INFO > DEBUG
        """
        severity_order = {
            ErrorSeverity.FATAL: 0,
            ErrorSeverity.CRITICAL: 1,
            ErrorSeverity.ERROR: 2,
            ErrorSeverity.WARNING: 3,
            ErrorSeverity.INFO: 4,
            ErrorSeverity.DEBUG: 5,
        }
        return sorted(
            self._errors.values(), key=lambda e: severity_order.get(e.severity, 99)
        )

    def most_severe(self) -> Optional[FoobaraError]:
        """Get the most severe error"""
        sorted_errors = self.sort_by_severity()
        return sorted_errors[0] if sorted_errors else None

    def with_suggestions(self) -> List[FoobaraError]:
        """Get all errors that have suggestions"""
        return [e for e in self._errors.values() if e.suggestion is not None]

    def group_by_path(self) -> Dict[Tuple[str, ...], List[FoobaraError]]:
        """Group errors by their data path"""
        grouped: Dict[Tuple[str, ...], List[FoobaraError]] = {}
        for error in self._errors.values():
            if error.path not in grouped:
                grouped[error.path] = []
            grouped[error.path].append(error)
        return grouped

    def group_by_category(self) -> Dict[str, List[FoobaraError]]:
        """Group errors by category"""
        grouped: Dict[str, List[FoobaraError]] = {}
        for error in self._errors.values():
            if error.category not in grouped:
                grouped[error.category] = []
            grouped[error.category].append(error)
        return grouped

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

    def to_dict(self, include_stack_trace: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Serialize to dictionary format matching Ruby Foobara's errors_hash.

        Args:
            include_stack_trace: Include stack traces in output

        Returns dict keyed by error key with full error details.
        """
        return {
            key: error.to_dict(include_stack_trace)
            for key, error in self._errors.items()
        }

    def to_list(self, include_stack_trace: bool = False) -> List[Dict[str, Any]]:
        """
        Serialize to list format for JSON responses.

        Args:
            include_stack_trace: Include stack traces in output
        """
        return [error.to_dict(include_stack_trace) for error in self._errors.values()]

    def to_human_readable(self, include_suggestions: bool = True) -> str:
        """
        Format errors as human-readable text.

        Args:
            include_suggestions: Include suggestions for fixes

        Returns:
            Formatted error text
        """
        if self.is_empty():
            return "No errors"

        lines = ["Errors:"]
        for i, error in enumerate(self.sort_by_severity(), 1):
            severity_indicator = {
                ErrorSeverity.FATAL: "🔴",
                ErrorSeverity.CRITICAL: "🔴",
                ErrorSeverity.ERROR: "🔸",
                ErrorSeverity.WARNING: "⚠️",
                ErrorSeverity.INFO: "ℹ️",
                ErrorSeverity.DEBUG: "🔍",
            }.get(error.severity, "•")

            path_str = ".".join(error.path) if error.path else "general"
            lines.append(f"\n{i}. {severity_indicator} [{path_str}] {error.message}")

            if error.context:
                lines.append(f"   Context: {error.context}")

            if include_suggestions and error.suggestion:
                lines.append(f"   💡 Suggestion: {error.suggestion}")

            if error.help_url:
                lines.append(f"   📖 Help: {error.help_url}")

            # Show error chain if present
            if error.cause:
                chain = error.get_error_chain()[1:]  # Skip self
                if chain:
                    lines.append(f"   Caused by chain of {len(chain)} error(s)")

        return "\n".join(lines)

    def summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about errors.

        Returns:
            Dictionary with error counts and statistics
        """
        by_category = self.group_by_category()
        by_severity = {}
        for severity in ErrorSeverity:
            count = len(self.by_severity(severity))
            if count > 0:
                by_severity[severity.value] = count

        return {
            "total": len(self),
            "fatal": len(self.fatal_errors()),
            "by_category": {k: len(v) for k, v in by_category.items()},
            "by_severity": by_severity,
            "has_suggestions": len(self.with_suggestions()),
            "most_severe": (
                self.most_severe().severity.value if self.most_severe() else None
            ),
        }

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
    """Standard error symbols for common validation and runtime errors"""

    # ===== Data Validation =====
    REQUIRED = "required"
    MISSING_REQUIRED_ATTRIBUTE = "missing_required_attribute"
    UNEXPECTED_ATTRIBUTE = "unexpected_attribute"
    CANNOT_CAST = "cannot_cast"
    INVALID_TYPE = "invalid_type"
    INVALID_FORMAT = "invalid_format"
    INVALID_VALUE = "invalid_value"
    NULL_NOT_ALLOWED = "null_not_allowed"

    # ===== String Constraints =====
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    BLANK = "blank"
    EMPTY = "empty"
    INVALID_LENGTH = "invalid_length"
    PATTERN_MISMATCH = "pattern_mismatch"
    INVALID_ENCODING = "invalid_encoding"

    # ===== Numeric Constraints =====
    TOO_SMALL = "too_small"
    TOO_LARGE = "too_large"
    NOT_INTEGER = "not_integer"
    NOT_POSITIVE = "not_positive"
    NOT_NEGATIVE = "not_negative"
    NOT_IN_RANGE = "not_in_range"
    PRECISION_LOSS = "precision_loss"

    # ===== Collection Constraints =====
    TOO_FEW_ELEMENTS = "too_few_elements"
    TOO_MANY_ELEMENTS = "too_many_elements"
    DUPLICATE_ELEMENT = "duplicate_element"
    INVALID_ELEMENT = "invalid_element"

    # ===== Records/Entities =====
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    RECORD_NOT_FOUND = "record_not_found"
    RECORD_NOT_UNIQUE = "record_not_unique"
    STALE_RECORD = "stale_record"
    INVALID_STATE = "invalid_state"
    CANNOT_DELETE = "cannot_delete"
    CANNOT_UPDATE = "cannot_update"

    # ===== Authorization/Authentication =====
    NOT_ALLOWED = "not_allowed"
    NOT_AUTHENTICATED = "not_authenticated"
    FORBIDDEN = "forbidden"
    AUTHENTICATION_FAILED = "authentication_failed"
    TOKEN_EXPIRED = "token_expired"
    INVALID_TOKEN = "invalid_token"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    SESSION_EXPIRED = "session_expired"

    # ===== Runtime Errors =====
    EXECUTION_ERROR = "execution_error"
    SUBCOMMAND_ERROR = "subcommand_error"
    TRANSACTION_ERROR = "transaction_error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    DEADLOCK = "deadlock"
    RESOURCE_EXHAUSTED = "resource_exhausted"

    # ===== External Service Errors =====
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    CONNECTION_FAILED = "connection_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SERVICE_UNAVAILABLE = "service_unavailable"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"

    # ===== System Errors =====
    INTERNAL_ERROR = "internal_error"
    CONFIGURATION_ERROR = "configuration_error"
    DEPENDENCY_ERROR = "dependency_error"
    OUT_OF_MEMORY = "out_of_memory"
    DISK_FULL = "disk_full"

    # ===== Business Logic Errors =====
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    CONSTRAINT_VIOLATION = "constraint_violation"
    INVARIANT_VIOLATION = "invariant_violation"
    PRECONDITION_FAILED = "precondition_failed"
    POSTCONDITION_FAILED = "postcondition_failed"

    # ===== File/IO Errors =====
    FILE_NOT_FOUND = "file_not_found"
    FILE_ALREADY_EXISTS = "file_already_exists"
    PERMISSION_DENIED = "permission_denied"
    READ_ERROR = "read_error"
    WRITE_ERROR = "write_error"


# Common error suggestions mapping
ERROR_SUGGESTIONS = {
    Symbols.REQUIRED: "Provide a value for this field",
    Symbols.TOO_SHORT: "Increase the length of this value",
    Symbols.TOO_LONG: "Reduce the length of this value",
    Symbols.INVALID_FORMAT: "Check the format matches the expected pattern",
    Symbols.NOT_AUTHENTICATED: "Log in or provide valid credentials",
    Symbols.NOT_ALLOWED: "Check your permissions or contact an administrator",
    Symbols.RATE_LIMIT_EXCEEDED: "Wait a moment and try again",
    Symbols.TIMEOUT: "Try again, or increase the timeout if possible",
    Symbols.CONNECTION_FAILED: "Check your network connection and try again",
    Symbols.NOT_FOUND: "Verify the ID or identifier is correct",
    Symbols.ALREADY_EXISTS: "Use a different unique identifier or update the existing record",
}


# Backward compatibility alias
DataError = FoobaraError
ErrorSymbols = Symbols
