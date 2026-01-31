"""
Comprehensive tests for enhanced error handling system.

Tests cover:
- Error categories and severity levels
- Error chaining and causality
- Stack trace capture
- Error suggestions and help
- Error prioritization and sorting
- Error recovery mechanisms
"""

import time

import pytest

from foobara_py.core.errors import (
    ERROR_SUGGESTIONS,
    ErrorCategory,
    ErrorCollection,
    ErrorSeverity,
    FoobaraError,
    Symbols,
)
from foobara_py.core.error_recovery import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerHook,
    CircuitState,
    ErrorRecoveryManager,
    FallbackHook,
    RetryConfig,
    RetryHook,
)


class TestErrorEnhancements:
    """Test enhanced error features"""

    def test_error_severity_levels(self):
        """Test different severity levels"""
        debug = FoobaraError(
            category="data",
            symbol="test",
            path=(),
            message="Debug",
            severity=ErrorSeverity.DEBUG,
        )
        assert debug.severity == ErrorSeverity.DEBUG

        fatal = FoobaraError.system_error("crash", "System crash", is_fatal=True)
        assert fatal.severity == ErrorSeverity.FATAL

    def test_error_categories(self):
        """Test different error categories"""
        data_err = FoobaraError.data_error("invalid", ["field"], "Invalid field")
        assert data_err.category == "data"

        domain_err = FoobaraError.domain_error("rule_violation", "Business rule violated")
        assert domain_err.category == "domain"

        auth_err = FoobaraError.auth_error("not_authenticated", "Not logged in")
        assert auth_err.category == "auth"

        external_err = FoobaraError.external_error(
            "api_error", "API failed", service="stripe"
        )
        assert external_err.category == "external"
        assert external_err.context["service"] == "stripe"

    def test_error_suggestions(self):
        """Test error suggestions"""
        error = FoobaraError.data_error(
            "required", ["email"], "Email is required", suggestion="Enter your email address"
        )
        assert error.suggestion == "Enter your email address"

        # Test with_suggestion
        error2 = error.with_suggestion("Try user@example.com")
        assert error2.suggestion == "Try user@example.com"

    def test_error_chaining(self):
        """Test error cause chains"""
        root = FoobaraError.external_error("connection_failed", "Network error")
        middle = FoobaraError.runtime_error("api_call_failed", "API call failed").with_cause(
            root
        )
        top = FoobaraError.runtime_error("operation_failed", "Operation failed").with_cause(
            middle
        )

        # Test chain traversal
        chain = top.get_error_chain()
        assert len(chain) == 3
        assert chain[0] == top
        assert chain[1] == middle
        assert chain[2] == root

        # Test root cause
        assert top.get_root_cause() == root

    def test_error_code_generation(self):
        """Test automatic error code generation"""
        error = FoobaraError.data_error("invalid_format", ["user", "email"], "Invalid email")
        assert error.error_code == "data.user.email.invalid_format"

        error2 = FoobaraError.runtime_error("timeout", "Request timed out")
        assert error2.error_code == "runtime.timeout"

    def test_error_timestamp(self):
        """Test error timestamp is set"""
        before = time.time()
        error = FoobaraError.data_error("test", [], "Test")
        after = time.time()

        assert error.timestamp is not None
        assert before <= error.timestamp <= after

    def test_stack_trace_capture(self):
        """Test stack trace capture"""
        error = FoobaraError.runtime_error("test", "Test error")
        error.capture_stack_trace()

        assert error.stack_trace is not None
        assert len(error.stack_trace) > 0
        assert any("test_stack_trace_capture" in line for line in error.stack_trace)

    def test_from_exception(self):
        """Test creating error from Python exception"""
        try:
            raise ValueError("Something went wrong")
        except ValueError as e:
            error = FoobaraError.from_exception(e)

        assert error.symbol == "exception"
        assert "Something went wrong" in error.message
        assert error.context["exception_type"] == "ValueError"
        assert error.stack_trace is not None

    def test_error_serialization_with_enhancements(self):
        """Test serialization includes new fields"""
        error = FoobaraError.data_error(
            "invalid_email",
            ["email"],
            "Invalid email format",
            suggestion="Use format: user@example.com",
        )
        error.help_url = "https://docs.example.com/email-format"

        data = error.to_dict()
        assert data["severity"] == "error"
        assert data["suggestion"] == "Use format: user@example.com"
        assert data["help_url"] == "https://docs.example.com/email-format"
        assert "timestamp" in data
        assert "error_code" in data

    def test_error_serialization_with_cause(self):
        """Test serialization includes cause chain"""
        cause = FoobaraError.runtime_error("db_error", "Database connection failed")
        error = FoobaraError.runtime_error("query_failed", "Query failed").with_cause(cause)

        data = error.to_dict()
        assert "cause" in data
        assert data["cause"]["symbol"] == "db_error"


class TestErrorCollection:
    """Test enhanced error collection features"""

    def test_severity_queries(self):
        """Test querying by severity"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError(
                category="data",
                symbol="e1",
                path=(),
                message="Error 1",
                severity=ErrorSeverity.ERROR,
            ),
            FoobaraError(
                category="runtime",
                symbol="e2",
                path=(),
                message="Error 2",
                severity=ErrorSeverity.CRITICAL,
            ),
            FoobaraError(
                category="system",
                symbol="e3",
                path=(),
                message="Error 3",
                severity=ErrorSeverity.WARNING,
            ),
        )

        critical = collection.by_severity(ErrorSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].symbol == "e2"

        critical_and_fatal = collection.critical_errors()
        assert len(critical_and_fatal) == 1

    def test_category_queries(self):
        """Test querying by category"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("e1", [], "Data error"),
            FoobaraError.domain_error("e2", "Domain error"),
            FoobaraError.auth_error("e3", "Auth error"),
        )

        domain = collection.domain_errors()
        assert len(domain) == 1

        auth = collection.auth_errors()
        assert len(auth) == 1

    def test_sort_by_severity(self):
        """Test sorting by severity"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError(
                category="data",
                symbol="e1",
                path=(),
                message="Warning",
                severity=ErrorSeverity.WARNING,
            ),
            FoobaraError(
                category="data",
                symbol="e2",
                path=(),
                message="Fatal",
                severity=ErrorSeverity.FATAL,
            ),
            FoobaraError(
                category="data",
                symbol="e3",
                path=(),
                message="Error",
                severity=ErrorSeverity.ERROR,
            ),
        )

        sorted_errors = collection.sort_by_severity()
        assert sorted_errors[0].severity == ErrorSeverity.FATAL
        assert sorted_errors[1].severity == ErrorSeverity.ERROR
        assert sorted_errors[2].severity == ErrorSeverity.WARNING

    def test_most_severe(self):
        """Test getting most severe error"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError(
                category="data",
                symbol="e1",
                path=(),
                message="Error",
                severity=ErrorSeverity.ERROR,
            ),
            FoobaraError(
                category="data",
                symbol="e2",
                path=(),
                message="Critical",
                severity=ErrorSeverity.CRITICAL,
            ),
        )

        most_severe = collection.most_severe()
        assert most_severe.severity == ErrorSeverity.CRITICAL

    def test_with_suggestions(self):
        """Test filtering errors with suggestions"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("e1", [], "Error 1"),
            FoobaraError.data_error("e2", [], "Error 2", suggestion="Fix this"),
        )

        with_suggestions = collection.with_suggestions()
        assert len(with_suggestions) == 1
        assert with_suggestions[0].symbol == "e2"

    def test_group_by_path(self):
        """Test grouping by path"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("e1", ["user", "email"], "Email error"),
            FoobaraError.data_error("e2", ["user", "email"], "Another email error"),
            FoobaraError.data_error("e3", ["user", "name"], "Name error"),
        )

        grouped = collection.group_by_path()
        assert len(grouped[("user", "email")]) == 2
        assert len(grouped[("user", "name")]) == 1

    def test_group_by_category(self):
        """Test grouping by category"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("e1", [], "Data 1"),
            FoobaraError.data_error("e2", [], "Data 2"),
            FoobaraError.runtime_error("e3", "Runtime 1"),
        )

        grouped = collection.group_by_category()
        assert len(grouped["data"]) == 2
        assert len(grouped["runtime"]) == 1

    def test_human_readable_format(self):
        """Test human-readable formatting"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error(
                "invalid_email", ["email"], "Invalid email", suggestion="Use user@example.com"
            ),
            FoobaraError.runtime_error("timeout", "Request timed out"),
        )

        text = collection.to_human_readable()
        assert "Invalid email" in text
        assert "Request timed out" in text
        assert "Suggestion:" in text
        assert "Use user@example.com" in text

    def test_summary(self):
        """Test error summary statistics"""
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("e1", [], "Data error"),
            FoobaraError.runtime_error("e2", "Runtime error", is_fatal=True),
            FoobaraError.auth_error("e3", "Auth error"),
        )

        summary = collection.summary()
        assert summary["total"] == 3
        assert summary["fatal"] == 1
        assert summary["by_category"]["data"] == 1
        assert summary["by_category"]["runtime"] == 1
        assert summary["by_category"]["auth"] == 1


class TestErrorRecovery:
    """Test error recovery mechanisms"""

    def test_retry_config(self):
        """Test retry configuration"""
        config = RetryConfig(max_attempts=3, initial_delay=0.1, backoff_multiplier=2.0)

        # Test retryable check
        timeout_error = FoobaraError.runtime_error("timeout", "Timed out")
        assert config.is_retryable(timeout_error)

        validation_error = FoobaraError.data_error("invalid", [], "Invalid")
        assert not config.is_retryable(validation_error)

        # Test delay calculation
        delay1 = config.get_delay(1)
        delay2 = config.get_delay(2)
        assert delay2 > delay1  # Exponential backoff

    def test_retry_hook(self):
        """Test retry recovery hook"""
        config = RetryConfig(max_attempts=3)
        hook = RetryHook(config)

        error = FoobaraError.runtime_error("timeout", "Timed out")
        context = {"attempt": 1}

        # Should allow retry
        result = hook.recover(error, context)
        assert context["should_retry"] is True
        assert context["attempt"] == 2

        # Max attempts reached
        context = {"attempt": 3}
        result = hook.recover(error, context)
        assert result.is_fatal
        assert "failed after 3 attempts" in result.message

    def test_fallback_hook(self):
        """Test fallback recovery hook"""
        hook = FallbackHook(fallback_value={"default": "value"})

        error = FoobaraError.runtime_error("error", "Failed")
        context = {}

        result = hook.recover(error, context)
        assert result is None  # Recovery succeeded
        assert context["fallback_result"] == {"default": "value"}

    def test_fallback_with_function(self):
        """Test fallback with custom function"""

        def custom_fallback(error, context):
            return f"Fallback for {error.symbol}"

        hook = FallbackHook(fallback_fn=custom_fallback)
        error = FoobaraError.runtime_error("error", "Failed")
        context = {}

        result = hook.recover(error, context)
        assert result is None
        assert context["fallback_result"] == "Fallback for error"

    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions"""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=1.0)
        breaker = CircuitBreaker(config)

        # Initially closed
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute()

        # Record failures
        for _ in range(3):
            breaker.record_failure()

        # Should open after threshold
        assert breaker.state == CircuitState.OPEN
        assert not breaker.can_execute()

        # Wait for timeout
        time.sleep(1.1)

        # Should transition to half-open
        assert breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

        # Success should close it
        breaker.record_success()
        breaker.record_success()  # Need success_threshold successes
        assert breaker.state == CircuitState.CLOSED

    def test_circuit_breaker_hook(self):
        """Test circuit breaker recovery hook"""
        config = CircuitBreakerConfig(failure_threshold=2)
        hook = CircuitBreakerHook(config)

        # Check execution allowed
        assert hook.check_before_execution("test")

        # Record failures
        error = FoobaraError.runtime_error("error", "Failed")
        hook.recover(error, {"circuit_breaker_id": "test"})
        hook.recover(error, {"circuit_breaker_id": "test"})

        # Circuit should be open
        assert not hook.check_before_execution("test")

        # Recovery should return circuit breaker error
        result = hook.recover(error, {"circuit_breaker_id": "test"})
        assert result.symbol == "circuit_breaker_open"
        assert result.is_fatal

    def test_recovery_manager(self):
        """Test error recovery manager"""
        manager = ErrorRecoveryManager()

        # Add retry hook
        manager.add_retry_hook(RetryConfig(max_attempts=2))

        # Attempt recovery on retryable error
        error = FoobaraError.runtime_error("timeout", "Timed out")
        context = {"attempt": 1}

        recovered, remaining, new_context = manager.attempt_recovery(error, context)
        assert not recovered  # Error not fully recovered, but retry scheduled
        assert new_context["should_retry"] is True

    def test_recovery_with_fallback(self):
        """Test recovery with fallback succeeds"""
        manager = ErrorRecoveryManager()
        manager.add_fallback_hook(fallback_value="default")

        error = FoobaraError.runtime_error("error", "Failed")
        context = {}

        recovered, remaining, new_context = manager.attempt_recovery(error, context)
        assert recovered  # Fully recovered via fallback
        assert remaining is None
        assert new_context["fallback_result"] == "default"

    def test_recovery_on_error_collection(self):
        """Test recovery on error collection"""
        manager = ErrorRecoveryManager()
        manager.add_fallback_hook(
            fallback_value="default", applicable_symbols=["recoverable"]
        )

        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.runtime_error("recoverable", "Can recover"),
            FoobaraError.runtime_error("fatal", "Cannot recover"),
        )

        context = {}
        recovered, remaining, _ = manager.attempt_recovery(collection, context)

        assert recovered  # At least one recovered
        assert remaining is not None
        assert remaining.count() == 1  # One error remains
        assert remaining.first().symbol == "fatal"


class TestStandardSymbols:
    """Test standard error symbols"""

    def test_symbols_exist(self):
        """Test all standard symbols are defined"""
        assert Symbols.REQUIRED == "required"
        assert Symbols.INVALID_FORMAT == "invalid_format"
        assert Symbols.TOO_SHORT == "too_short"
        assert Symbols.NOT_FOUND == "not_found"
        assert Symbols.NOT_AUTHENTICATED == "not_authenticated"
        assert Symbols.TIMEOUT == "timeout"
        assert Symbols.BUSINESS_RULE_VIOLATION == "business_rule_violation"
        assert Symbols.FILE_NOT_FOUND == "file_not_found"

    def test_error_suggestions_mapping(self):
        """Test error suggestions are available"""
        assert Symbols.REQUIRED in ERROR_SUGGESTIONS
        assert Symbols.TOO_SHORT in ERROR_SUGGESTIONS
        assert Symbols.NOT_AUTHENTICATED in ERROR_SUGGESTIONS


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""

    def test_dataerror_alias(self):
        """Test DataError alias still works"""
        from foobara_py.core.errors import DataError

        error = DataError.data_error("test", [], "Test")
        assert isinstance(error, FoobaraError)

    def test_basic_error_creation(self):
        """Test basic error creation still works"""
        error = FoobaraError(
            category="data", symbol="test", path=["field"], message="Test error"
        )
        assert error.key() == "data.field.test"
        assert error.message == "Test error"

    def test_error_collection_methods(self):
        """Test error collection backward compatibility"""
        collection = ErrorCollection()
        error = FoobaraError.data_error("test", [], "Test")

        # Old methods should still work
        collection.add_error(error)  # Old method name
        assert collection.has_errors()

        collection2 = ErrorCollection()
        collection2.add_errors(error)  # Old method name
        assert collection2.count() == 1
