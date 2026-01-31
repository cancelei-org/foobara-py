"""Core components: Command, Outcome, Errors, Error Recovery"""

from foobara_py.core.command import (
    AsyncCommand,
    AsyncSimpleCommand,
    Command,
    SimpleCommand,
    async_command,
    async_simple_command,
    command,
    simple_command,
)
from foobara_py.core.errors import (
    ERROR_SUGGESTIONS,
    DataError,
    ErrorCategory,
    ErrorCollection,
    ErrorSeverity,
    ErrorSymbols,
    FoobaraError,
    Symbols,
)
from foobara_py.core.error_recovery import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerHook,
    CircuitState,
    ErrorRecoveryHook,
    ErrorRecoveryManager,
    FallbackHook,
    RecoveryStrategy,
    RetryConfig,
    RetryHook,
    configure_default_recovery,
    get_global_recovery_manager,
)
from foobara_py.core.outcome import CommandOutcome, Failure, Outcome, Success
from foobara_py.core.registry import CommandRegistry, get_default_registry, register

__all__ = [
    # Outcome types
    "Outcome",
    "Success",
    "Failure",
    "CommandOutcome",
    # Command types
    "Command",
    "command",
    "SimpleCommand",
    "simple_command",
    "AsyncCommand",
    "async_command",
    "AsyncSimpleCommand",
    "async_simple_command",
    # Error types
    "FoobaraError",
    "DataError",
    "ErrorCollection",
    "ErrorSymbols",
    "Symbols",
    "ErrorCategory",
    "ErrorSeverity",
    "ERROR_SUGGESTIONS",
    # Error recovery
    "ErrorRecoveryManager",
    "ErrorRecoveryHook",
    "RetryHook",
    "RetryConfig",
    "FallbackHook",
    "CircuitBreakerHook",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "RecoveryStrategy",
    "get_global_recovery_manager",
    "configure_default_recovery",
    # Registry
    "CommandRegistry",
    "get_default_registry",
    "register",
]
