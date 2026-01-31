"""
Error recovery mechanisms for Foobara commands.

Provides retry logic, fallback strategies, and recovery hooks
to handle transient failures gracefully.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from foobara_py.core.errors import ErrorCollection, FoobaraError, Symbols

logger = logging.getLogger(__name__)


class RecoveryStrategy(str, Enum):
    """Available error recovery strategies"""

    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAKER = "circuit_breaker"
    IGNORE = "ignore"
    ESCALATE = "escalate"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    max_attempts: int = 3
    initial_delay: float = 0.1  # seconds
    max_delay: float = 10.0
    backoff_multiplier: float = 2.0
    exponential_backoff: bool = True
    jitter: bool = True
    retryable_symbols: List[str] = field(
        default_factory=lambda: [
            Symbols.TIMEOUT,
            Symbols.CONNECTION_FAILED,
            Symbols.EXTERNAL_SERVICE_ERROR,
            Symbols.RATE_LIMIT_EXCEEDED,
        ]
    )
    retryable_categories: List[str] = field(default_factory=lambda: [])

    def is_retryable(self, error: FoobaraError) -> bool:
        """Check if error is retryable based on config"""
        if error.symbol in self.retryable_symbols:
            return True
        if error.category in self.retryable_categories:
            return True
        return False

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (1-indexed)"""
        if self.exponential_backoff:
            delay = self.initial_delay * (self.backoff_multiplier ** (attempt - 1))
        else:
            delay = self.initial_delay

        delay = min(delay, self.max_delay)

        if self.jitter:
            import random

            delay = delay * (0.5 + random.random())

        return delay


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern"""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0  # seconds
    half_open_requests: int = 1


class CircuitState(str, Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    When too many errors occur, the circuit "opens" and subsequent
    requests fail fast without attempting the operation.
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_attempts = 0

    def can_execute(self) -> bool:
        """Check if execution should be attempted"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time >= self.config.timeout
            ):
                self.state = CircuitState.HALF_OPEN
                self.half_open_attempts = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_attempts < self.config.half_open_requests

        return False

    def record_success(self):
        """Record successful execution"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker transitioning to CLOSED")
        else:
            self.failure_count = 0

    def record_failure(self):
        """Record failed execution"""
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_attempts = 0
            logger.warning("Circuit breaker transitioning back to OPEN")
        else:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker OPENED after {self.failure_count} failures"
                )


class ErrorRecoveryHook(ABC):
    """Base class for error recovery hooks"""

    @abstractmethod
    def should_recover(self, error: FoobaraError, context: Dict[str, Any]) -> bool:
        """Determine if this hook should handle the error"""
        pass

    @abstractmethod
    def recover(
        self, error: FoobaraError, context: Dict[str, Any]
    ) -> Optional[FoobaraError]:
        """
        Attempt to recover from error.

        Returns None if recovery succeeded, or a new/modified error if it failed.
        """
        pass


class RetryHook(ErrorRecoveryHook):
    """Recovery hook that implements retry logic"""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    def should_recover(self, error: FoobaraError, context: Dict[str, Any]) -> bool:
        """Check if error is retryable"""
        return self.config.is_retryable(error)

    def recover(
        self, error: FoobaraError, context: Dict[str, Any]
    ) -> Optional[FoobaraError]:
        """
        Implement retry logic.

        Note: Actual retry execution should be handled by the command runner.
        This hook just validates and configures retry behavior.
        """
        attempt = context.get("attempt", 1)

        if attempt >= self.config.max_attempts:
            # Max attempts reached, return error with context
            return FoobaraError(
                category=error.category,
                symbol=error.symbol,
                path=error.path,
                message=f"{error.message} (failed after {attempt} attempts)",
                context={
                    **error.context,
                    "max_attempts_reached": True,
                    "attempts": attempt,
                },
                runtime_path=error.runtime_path,
                is_fatal=True,
            )

        # Calculate delay for next attempt
        delay = self.config.get_delay(attempt + 1)
        logger.info(
            f"Scheduling retry attempt {attempt + 1}/{self.config.max_attempts} "
            f"after {delay:.2f}s for error: {error.symbol}"
        )

        # Signal that retry should happen
        context["should_retry"] = True
        context["retry_delay"] = delay
        context["attempt"] = attempt + 1

        return error


class FallbackHook(ErrorRecoveryHook):
    """Recovery hook that provides fallback values"""

    def __init__(
        self,
        fallback_value: Any = None,
        fallback_fn: Optional[Callable] = None,
        applicable_symbols: Optional[List[str]] = None,
    ):
        self.fallback_value = fallback_value
        self.fallback_fn = fallback_fn
        self.applicable_symbols = applicable_symbols or []

    def should_recover(self, error: FoobaraError, context: Dict[str, Any]) -> bool:
        """Check if fallback should be used"""
        if not self.applicable_symbols:
            return True
        return error.symbol in self.applicable_symbols

    def recover(
        self, error: FoobaraError, context: Dict[str, Any]
    ) -> Optional[FoobaraError]:
        """Provide fallback value"""
        if self.fallback_fn:
            try:
                context["fallback_result"] = self.fallback_fn(error, context)
                return None  # Recovery succeeded
            except Exception as e:
                logger.error(f"Fallback function failed: {e}")
                return error
        else:
            context["fallback_result"] = self.fallback_value
            return None  # Recovery succeeded


class CircuitBreakerHook(ErrorRecoveryHook):
    """Recovery hook that implements circuit breaker pattern"""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.breakers: Dict[str, CircuitBreaker] = {}

    def _get_breaker(self, identifier: str) -> CircuitBreaker:
        """Get or create circuit breaker for identifier"""
        if identifier not in self.breakers:
            self.breakers[identifier] = CircuitBreaker(self.config)
        return self.breakers[identifier]

    def should_recover(self, error: FoobaraError, context: Dict[str, Any]) -> bool:
        """Always participate in recovery to track failures"""
        return True

    def recover(
        self, error: FoobaraError, context: Dict[str, Any]
    ) -> Optional[FoobaraError]:
        """Record failure in circuit breaker"""
        identifier = context.get("circuit_breaker_id", "default")
        breaker = self._get_breaker(identifier)
        breaker.record_failure()

        if breaker.state == CircuitState.OPEN:
            return FoobaraError(
                category="runtime",
                symbol="circuit_breaker_open",
                path=(),
                message="Circuit breaker is open, request rejected",
                context={
                    "original_error": error.to_dict(),
                    "circuit_state": breaker.state.value,
                },
                is_fatal=True,
            )

        return error

    def check_before_execution(self, identifier: str = "default") -> bool:
        """Check if execution should proceed"""
        breaker = self._get_breaker(identifier)
        return breaker.can_execute()

    def record_success(self, identifier: str = "default"):
        """Record successful execution"""
        breaker = self._get_breaker(identifier)
        breaker.record_success()


class ErrorRecoveryManager:
    """
    Manages error recovery hooks and strategies.

    Coordinates multiple recovery mechanisms to handle errors gracefully.
    """

    def __init__(self):
        self.hooks: List[ErrorRecoveryHook] = []
        self.global_hooks: List[ErrorRecoveryHook] = []

    def add_hook(self, hook: ErrorRecoveryHook, global_hook: bool = False):
        """Add a recovery hook"""
        if global_hook:
            self.global_hooks.append(hook)
        else:
            self.hooks.append(hook)

    def add_retry_hook(
        self, config: Optional[RetryConfig] = None, global_hook: bool = False
    ):
        """Add retry recovery hook"""
        self.add_hook(RetryHook(config), global_hook)

    def add_fallback_hook(
        self,
        fallback_value: Any = None,
        fallback_fn: Optional[Callable] = None,
        applicable_symbols: Optional[List[str]] = None,
        global_hook: bool = False,
    ):
        """Add fallback recovery hook"""
        self.add_hook(
            FallbackHook(fallback_value, fallback_fn, applicable_symbols), global_hook
        )

    def add_circuit_breaker_hook(
        self, config: Optional[CircuitBreakerConfig] = None, global_hook: bool = False
    ):
        """Add circuit breaker recovery hook"""
        self.add_hook(CircuitBreakerHook(config), global_hook)

    def attempt_recovery(
        self,
        errors: Union[FoobaraError, ErrorCollection],
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Union[FoobaraError, ErrorCollection, None], Dict[str, Any]]:
        """
        Attempt to recover from errors using registered hooks.

        Returns:
            (recovered, remaining_errors, recovery_context)
            - recovered: True if any error was successfully recovered
            - remaining_errors: Errors that couldn't be recovered (or None if all recovered)
            - recovery_context: Updated context with recovery information
        """
        context = context or {}
        all_hooks = self.global_hooks + self.hooks

        # Handle single error
        if isinstance(errors, FoobaraError):
            for hook in all_hooks:
                if hook.should_recover(errors, context):
                    result = hook.recover(errors, context)
                    if result is None:
                        # Recovery succeeded
                        return True, None, context
                    errors = result

            # No hook recovered the error
            return False, errors, context

        # Handle error collection
        if isinstance(errors, ErrorCollection):
            recovered_any = False
            remaining = ErrorCollection()

            for error in errors:
                error_recovered = False
                current_error = error

                for hook in all_hooks:
                    if hook.should_recover(current_error, context):
                        result = hook.recover(current_error, context)
                        if result is None:
                            # This error was recovered
                            error_recovered = True
                            recovered_any = True
                            break
                        current_error = result

                if not error_recovered:
                    remaining.add(current_error)

            if remaining.is_empty():
                return True, None, context
            return recovered_any, remaining, context

        return False, errors, context


# Global recovery manager instance
_global_recovery_manager: Optional[ErrorRecoveryManager] = None


def get_global_recovery_manager() -> ErrorRecoveryManager:
    """Get or create global recovery manager"""
    global _global_recovery_manager
    if _global_recovery_manager is None:
        _global_recovery_manager = ErrorRecoveryManager()
    return _global_recovery_manager


def configure_default_recovery():
    """Configure default recovery strategies"""
    manager = get_global_recovery_manager()

    # Add retry for transient errors
    manager.add_retry_hook(global_hook=True)

    # Add circuit breaker for external service errors
    manager.add_circuit_breaker_hook(
        CircuitBreakerConfig(failure_threshold=5, timeout=60.0), global_hook=True
    )
