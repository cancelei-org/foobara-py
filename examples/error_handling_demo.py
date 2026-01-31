"""
Demonstration of enhanced error handling features in foobara-py.

This example showcases:
- Error categories and severity levels
- Error chaining and causality
- Error suggestions and help
- Error recovery with retry and fallback
- Circuit breaker pattern
"""

from foobara_py.core import (
    Command,
    ErrorCollection,
    ErrorRecoveryManager,
    ErrorSeverity,
    FallbackHook,
    FoobaraError,
    RetryConfig,
    Symbols,
)


# ===== Example 1: Creating Rich Errors =====


def demo_error_creation():
    """Demonstrate creating errors with rich context"""
    print("=== Error Creation Examples ===\n")

    # Data validation error with suggestion
    email_error = FoobaraError.data_error(
        symbol=Symbols.INVALID_FORMAT,
        path=["user", "email"],
        message="Email address format is invalid",
        suggestion="Use format: user@example.com",
        provided_value="not-an-email",
    )

    print(f"Error: {email_error.message}")
    print(f"Suggestion: {email_error.suggestion}")
    print(f"Error Code: {email_error.error_code}")
    print(f"Severity: {email_error.severity.value}\n")

    # Domain/business logic error
    balance_error = FoobaraError.domain_error(
        symbol="insufficient_balance",
        message="Insufficient funds for withdrawal",
        path=["account"],
        suggestion="Deposit funds or reduce withdrawal amount",
        current_balance=100.00,
        requested_amount=150.00,
    )

    print(f"Error: {balance_error.message}")
    print(f"Context: {balance_error.context}\n")

    # External service error
    api_error = FoobaraError.external_error(
        symbol="payment_gateway_error",
        message="Payment processing failed",
        service="stripe",
        suggestion="Try again or use a different payment method",
        stripe_error_code="card_declined",
    )

    print(f"Error: {api_error.message}")
    print(f"Service: {api_error.context['service']}\n")


# ===== Example 2: Error Chaining =====


def demo_error_chaining():
    """Demonstrate error cause chains"""
    print("=== Error Chaining Example ===\n")

    # Simulate a chain of failures
    network_error = FoobaraError.external_error(
        symbol=Symbols.CONNECTION_FAILED, message="Network connection failed"
    )

    api_error = FoobaraError.runtime_error(
        symbol="api_call_failed", message="Failed to call external API"
    ).with_cause(network_error)

    operation_error = FoobaraError.runtime_error(
        symbol="operation_failed", message="User registration failed"
    ).with_cause(api_error)

    # Navigate the error chain
    print("Error chain:")
    for i, error in enumerate(operation_error.get_error_chain(), 1):
        print(f"  {i}. [{error.category}] {error.message}")

    print(f"\nRoot cause: {operation_error.get_root_cause().message}\n")


# ===== Example 3: Error Collections =====


def demo_error_collections():
    """Demonstrate error collection features"""
    print("=== Error Collection Example ===\n")

    errors = ErrorCollection()

    # Add various errors
    errors.add_all(
        FoobaraError.data_error(
            Symbols.REQUIRED, ["name"], "Name is required", suggestion="Enter your name"
        ),
        FoobaraError.data_error(
            Symbols.INVALID_FORMAT,
            ["email"],
            "Invalid email format",
            suggestion="Use user@example.com",
        ),
        FoobaraError.data_error(
            Symbols.TOO_SHORT, ["password"], "Password too short", suggestion="Use 8+ characters"
        ),
        FoobaraError.runtime_error(
            Symbols.TIMEOUT, "Request timed out", suggestion="Try again"
        ),
    )

    print(f"Total errors: {errors.count()}")
    print(f"Most severe: {errors.most_severe().severity.value}\n")

    # Query by category
    data_errors = errors.data_errors()
    print(f"Data errors: {len(data_errors)}")

    # Query by path
    email_errors = errors.at_path(["email"])
    print(f"Email errors: {len(email_errors)}")

    # Get errors with suggestions
    actionable = errors.with_suggestions()
    print(f"Errors with suggestions: {len(actionable)}\n")

    # Human-readable output
    print("Human-readable format:")
    print(errors.to_human_readable())
    print()

    # Summary statistics
    summary = errors.summary()
    print(f"Summary: {summary}\n")


# ===== Example 4: Error Recovery with Retry =====


class UnstableCommand(Command):
    """Command that fails occasionally to demonstrate retry"""

    inputs = {"attempt_number": int}
    result = str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_count = 0

    def execute(self):
        self.call_count += 1

        # Simulate failure on first two attempts
        if self.call_count < self.inputs["attempt_number"]:
            self.add_runtime_error(
                Symbols.TIMEOUT, f"Attempt {self.call_count} failed (simulated timeout)"
            )
        else:
            self.result = f"Success on attempt {self.call_count}"


def demo_retry_recovery():
    """Demonstrate retry error recovery"""
    print("=== Retry Recovery Example ===\n")

    # Configure retry
    manager = ErrorRecoveryManager()
    manager.add_retry_hook(
        RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            retryable_symbols=[Symbols.TIMEOUT, Symbols.CONNECTION_FAILED],
        )
    )

    # Simulate retryable error
    error = FoobaraError.runtime_error(Symbols.TIMEOUT, "Request timed out")

    for attempt in range(1, 4):
        context = {"attempt": attempt}
        recovered, remaining, new_context = manager.attempt_recovery(error, context)

        if new_context.get("should_retry"):
            delay = new_context.get("retry_delay", 0)
            print(f"Attempt {attempt} failed, retrying in {delay:.2f}s...")
        else:
            if recovered:
                print(f"Recovered on attempt {attempt}!")
            else:
                print(f"Failed after {attempt} attempts")
            break

    print()


# ===== Example 5: Fallback Recovery =====


def demo_fallback_recovery():
    """Demonstrate fallback error recovery"""
    print("=== Fallback Recovery Example ===\n")

    # Configure fallback
    manager = ErrorRecoveryManager()

    # Static fallback
    manager.add_fallback_hook(
        fallback_value={"cached": "data"}, applicable_symbols=["api_error"]
    )

    # Dynamic fallback with function
    def get_default_user(error, context):
        return {"id": None, "name": "Guest", "email": "guest@example.com"}

    manager.add_fallback_hook(
        fallback_fn=get_default_user, applicable_symbols=["user_not_found"]
    )

    # Test static fallback
    error1 = FoobaraError.runtime_error("api_error", "API call failed")
    recovered, _, context = manager.attempt_recovery(error1, {})

    if recovered and "fallback_result" in context:
        print(f"Using fallback data: {context['fallback_result']}")

    # Test dynamic fallback
    error2 = FoobaraError.runtime_error("user_not_found", "User not found")
    recovered, _, context = manager.attempt_recovery(error2, {})

    if recovered and "fallback_result" in context:
        print(f"Using default user: {context['fallback_result']}")

    print()


# ===== Example 6: Severity-Based Error Handling =====


def demo_severity_handling():
    """Demonstrate handling errors by severity"""
    print("=== Severity-Based Handling Example ===\n")

    errors = ErrorCollection()

    # Add errors with different severities
    errors.add_all(
        FoobaraError(
            category="data",
            symbol="deprecated_field",
            path=["settings"],
            message="Field is deprecated",
            severity=ErrorSeverity.WARNING,
        ),
        FoobaraError.data_error(
            "invalid_format", ["email"], "Invalid email", severity=ErrorSeverity.ERROR
        ),
        FoobaraError.system_error("database_down", "Database unavailable", is_fatal=True),
    )

    # Handle based on severity
    for error in errors.sort_by_severity():
        if error.severity == ErrorSeverity.FATAL:
            print(f"🔴 FATAL: {error.message} - HALT EXECUTION")
        elif error.severity == ErrorSeverity.CRITICAL:
            print(f"🔴 CRITICAL: {error.message} - Alert ops team")
        elif error.severity == ErrorSeverity.ERROR:
            print(f"🔸 ERROR: {error.message} - Show to user")
        elif error.severity == ErrorSeverity.WARNING:
            print(f"⚠️ WARNING: {error.message} - Log for review")

    print()


# ===== Example 7: Exception Conversion =====


def demo_exception_conversion():
    """Demonstrate converting Python exceptions to Foobara errors"""
    print("=== Exception Conversion Example ===\n")

    try:
        # Simulate an error
        result = 1 / 0
    except ZeroDivisionError as e:
        error = FoobaraError.from_exception(
            e, symbol="division_by_zero", category="runtime", include_traceback=True
        )

        print(f"Error: {error.message}")
        print(f"Exception type: {error.context['exception_type']}")
        print(f"Has stack trace: {error.stack_trace is not None}\n")


# ===== Main Demo =====


def main():
    """Run all demonstrations"""
    print("\n" + "=" * 60)
    print("Enhanced Error Handling Demonstration")
    print("=" * 60 + "\n")

    demo_error_creation()
    demo_error_chaining()
    demo_error_collections()
    demo_retry_recovery()
    demo_fallback_recovery()
    demo_severity_handling()
    demo_exception_conversion()

    print("=" * 60)
    print("Demo completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
