# Error Handling Guide

Comprehensive guide to error handling in foobara-py, covering error creation, categorization, recovery, and best practices.

## Table of Contents

1. [Overview](#overview)
2. [Error Categories](#error-categories)
3. [Error Severity](#error-severity)
4. [Creating Errors](#creating-errors)
5. [Error Collections](#error-collections)
6. [Error Recovery](#error-recovery)
7. [Error Suggestions](#error-suggestions)
8. [Best Practices](#best-practices)

## Overview

Foobara-py provides a comprehensive error handling system that goes beyond simple exception throwing. Errors are first-class objects that carry rich context, support chaining, and enable sophisticated recovery strategies.

### Key Features

- **Rich Error Context**: Errors carry detailed context about what went wrong
- **Error Categorization**: Organize errors by category (data, runtime, domain, etc.)
- **Severity Levels**: Prioritize errors from DEBUG to FATAL
- **Error Chaining**: Track causality through error chains
- **Actionable Suggestions**: Provide users with clear guidance on fixing issues
- **Recovery Mechanisms**: Retry, fallback, and circuit breaker patterns
- **Stack Traces**: Debug production issues with captured stack traces

## Error Categories

Foobara errors are organized into categories that reflect the nature of the problem:

### Data/Validation Errors

Problems with input data or validation failures.

```python
from foobara_py.core.errors import FoobaraError

error = FoobaraError.data_error(
    symbol="invalid_email",
    path=["user", "email"],
    message="Invalid email format",
    suggestion="Use format: user@example.com"
)
```

### Runtime Errors

Errors that occur during command execution.

```python
error = FoobaraError.runtime_error(
    symbol="timeout",
    message="Request timed out after 30 seconds",
    suggestion="Try again or increase the timeout",
    timeout_seconds=30
)
```

### Domain Errors

Business rule violations and domain-specific errors.

```python
error = FoobaraError.domain_error(
    symbol="insufficient_balance",
    message="Insufficient balance for withdrawal",
    path=["account"],
    suggestion="Deposit funds or reduce withdrawal amount",
    current_balance=100,
    requested_amount=150
)
```

### System Errors

Infrastructure and system-level failures.

```python
error = FoobaraError.system_error(
    symbol="database_unavailable",
    message="Database connection pool exhausted",
    is_fatal=True,
    suggestion="Contact system administrator"
)
```

### Authentication/Authorization Errors

Security and access control errors.

```python
error = FoobaraError.auth_error(
    symbol="insufficient_permissions",
    message="You don't have permission to delete this resource",
    suggestion="Request admin access or contact support",
    required_role="admin",
    user_role="viewer"
)
```

### External Service Errors

Failures in external APIs and services.

```python
error = FoobaraError.external_error(
    symbol="payment_gateway_error",
    message="Payment processing failed",
    service="stripe",
    suggestion="Try again or use a different payment method",
    stripe_error_code="card_declined"
)
```

## Error Severity

Errors can have different severity levels to help with prioritization:

```python
from foobara_py.core.errors import ErrorSeverity

# DEBUG - Informational, not really an error
error = FoobaraError(category="data", symbol="debug_info",
                     severity=ErrorSeverity.DEBUG, ...)

# INFO - Minor issue, operation can continue
error = FoobaraError(category="data", symbol="deprecated_field",
                     severity=ErrorSeverity.INFO, ...)

# WARNING - Potential problem, should be addressed
error = FoobaraError(category="data", symbol="near_limit",
                     severity=ErrorSeverity.WARNING, ...)

# ERROR - Standard error, operation failed
error = FoobaraError.data_error(...)  # Default severity

# CRITICAL - Severe error, system-level impact
error = FoobaraError.runtime_error(..., is_fatal=False)

# FATAL - Unrecoverable error, immediate halt required
error = FoobaraError.system_error(..., is_fatal=True)
```

## Creating Errors

### Using Factory Methods

The recommended way to create errors is using factory methods:

```python
from foobara_py.core.errors import FoobaraError

# Data/validation error
error = FoobaraError.data_error(
    symbol="too_short",
    path=["password"],
    message="Password is too short",
    suggestion="Use at least 8 characters",
    min_length=8,
    actual_length=5
)

# Runtime error
error = FoobaraError.runtime_error(
    symbol="execution_error",
    message="Command execution failed",
    suggestion="Check the logs for details"
)
```

### From Python Exceptions

Convert standard Python exceptions to Foobara errors:

```python
try:
    # Some operation
    result = risky_operation()
except ValueError as e:
    error = FoobaraError.from_exception(
        e,
        symbol="invalid_input",
        category="data"
    )
```

### Error Chaining

Track causality with error chains:

```python
# Root cause
network_error = FoobaraError.external_error(
    "connection_failed",
    "Failed to connect to API"
)

# Intermediate error
api_error = FoobaraError.runtime_error(
    "api_call_failed",
    "API call failed"
).with_cause(network_error)

# Top-level error
operation_error = FoobaraError.runtime_error(
    "operation_failed",
    "Operation could not complete"
).with_cause(api_error)

# Navigate the chain
chain = operation_error.get_error_chain()  # [operation_error, api_error, network_error]
root = operation_error.get_root_cause()     # network_error
```

### Capturing Stack Traces

For debugging, capture stack traces:

```python
error = FoobaraError.runtime_error("unexpected_error", "Something went wrong")
error.capture_stack_trace()

# Stack trace is included in serialization
data = error.to_dict(include_stack_trace=True)
```

## Error Collections

The `ErrorCollection` class manages multiple errors efficiently:

### Basic Usage

```python
from foobara_py.core.errors import ErrorCollection

errors = ErrorCollection()

# Add errors
errors.add(FoobaraError.data_error("required", ["name"], "Name is required"))
errors.add(FoobaraError.data_error("invalid_email", ["email"], "Invalid email"))

# Check for errors
if errors.has_errors():
    print(f"Found {errors.count()} errors")
```

### Querying Errors

```python
# By path
email_errors = errors.at_path(["email"])

# By symbol
required_errors = errors.with_symbol("required")

# By category
data_errors = errors.data_errors()
runtime_errors = errors.runtime_errors()
auth_errors = errors.auth_errors()

# By severity
critical = errors.critical_errors()
sorted_by_severity = errors.sort_by_severity()
most_severe = errors.most_severe()

# Errors with suggestions
actionable = errors.with_suggestions()
```

### Grouping Errors

```python
# Group by path
by_path = errors.group_by_path()
# { ("email",): [error1, error2], ("name",): [error3] }

# Group by category
by_category = errors.group_by_category()
# { "data": [error1, error2], "runtime": [error3] }
```

### Error Summaries

```python
# Get statistical summary
summary = errors.summary()
# {
#   "total": 5,
#   "fatal": 1,
#   "by_category": {"data": 3, "runtime": 2},
#   "by_severity": {"error": 4, "critical": 1},
#   "has_suggestions": 3,
#   "most_severe": "critical"
# }
```

### Human-Readable Output

```python
# Format for display to users
print(errors.to_human_readable())
# Errors:
#
# 1. 🔸 [email] Invalid email format
#    💡 Suggestion: Use format: user@example.com
#
# 2. 🔸 [name] Name is required
#    💡 Suggestion: Provide a name
```

## Error Recovery

Foobara provides sophisticated error recovery mechanisms:

### Retry Logic

Automatically retry transient failures:

```python
from foobara_py.core.error_recovery import (
    ErrorRecoveryManager,
    RetryConfig
)

# Configure retry behavior
manager = ErrorRecoveryManager()
manager.add_retry_hook(
    RetryConfig(
        max_attempts=3,
        initial_delay=0.1,
        backoff_multiplier=2.0,
        exponential_backoff=True,
        retryable_symbols=["timeout", "connection_failed"]
    )
)

# Attempt recovery
error = FoobaraError.runtime_error("timeout", "Request timed out")
context = {"attempt": 1}

recovered, remaining, new_context = manager.attempt_recovery(error, context)

if new_context.get("should_retry"):
    delay = new_context["retry_delay"]
    # Sleep and retry...
```

### Fallback Values

Provide fallback values when operations fail:

```python
from foobara_py.core.error_recovery import FallbackHook

# Static fallback
manager.add_fallback_hook(
    fallback_value={"default": "data"},
    applicable_symbols=["data_fetch_failed"]
)

# Dynamic fallback with function
def get_cached_data(error, context):
    return cache.get(context["key"], default={})

manager.add_fallback_hook(
    fallback_fn=get_cached_data,
    applicable_symbols=["cache_miss"]
)

# Use fallback
error = FoobaraError.runtime_error("data_fetch_failed", "API down")
recovered, _, context = manager.attempt_recovery(error)

if recovered and "fallback_result" in context:
    result = context["fallback_result"]
```

### Circuit Breaker

Prevent cascading failures with circuit breaker pattern:

```python
from foobara_py.core.error_recovery import (
    CircuitBreakerConfig,
    CircuitBreakerHook
)

# Configure circuit breaker
hook = CircuitBreakerHook(
    CircuitBreakerConfig(
        failure_threshold=5,      # Open after 5 failures
        success_threshold=2,      # Close after 2 successes
        timeout=60.0             # Try again after 60s
    )
)
manager.add_hook(hook)

# Check before attempting operation
if hook.check_before_execution("external_api"):
    try:
        result = call_external_api()
        hook.record_success("external_api")
    except Exception as e:
        error = FoobaraError.from_exception(e)
        hook.recover(error, {"circuit_breaker_id": "external_api"})
else:
    # Circuit is open, don't attempt the operation
    print("Circuit breaker is open, skipping call")
```

### Custom Recovery Hooks

Create custom recovery strategies:

```python
from foobara_py.core.error_recovery import ErrorRecoveryHook

class CacheRecoveryHook(ErrorRecoveryHook):
    def should_recover(self, error, context):
        return error.symbol in ["db_error", "api_error"]

    def recover(self, error, context):
        # Try to get data from cache
        cached_data = self.cache.get(context.get("cache_key"))
        if cached_data:
            context["fallback_result"] = cached_data
            return None  # Recovery succeeded
        return error  # Recovery failed

manager.add_hook(CacheRecoveryHook())
```

## Error Suggestions

Provide actionable guidance to help users fix issues:

### Built-in Suggestions

Many standard error symbols have built-in suggestions:

```python
from foobara_py.core.errors import ERROR_SUGGESTIONS, Symbols

# Get suggestion for a symbol
suggestion = ERROR_SUGGESTIONS.get(Symbols.REQUIRED)
# "Provide a value for this field"
```

### Custom Suggestions

Add suggestions to your errors:

```python
error = FoobaraError.data_error(
    "password_too_weak",
    ["password"],
    "Password does not meet requirements",
    suggestion="Use at least 8 characters including uppercase, lowercase, and numbers"
)

# Or add later
error = error.with_suggestion("Try a stronger password")
```

### Help URLs

Link to documentation:

```python
error = FoobaraError.auth_error(
    "oauth_failed",
    "OAuth authentication failed"
)
error.help_url = "https://docs.example.com/auth/oauth-troubleshooting"

# Included in serialization
data = error.to_dict()
# data["help_url"] = "https://docs.example.com/auth/oauth-troubleshooting"
```

## Best Practices

### 1. Use Specific Error Symbols

Don't use generic symbols like "error" or "invalid". Be specific:

```python
# Bad
error = FoobaraError.data_error("invalid", ["email"], "Invalid")

# Good
error = FoobaraError.data_error(
    "invalid_email_format",
    ["email"],
    "Email address format is invalid",
    suggestion="Use format: user@example.com",
    provided_value=email
)
```

### 2. Include Rich Context

Add context that helps debugging and recovery:

```python
error = FoobaraError.runtime_error(
    "query_timeout",
    "Database query timed out",
    query=sql_query,
    timeout_seconds=30,
    table="users",
    num_rows_scanned=1000000
)
```

### 3. Use Appropriate Categories

Choose the category that best describes the error:

- **data**: User input validation
- **runtime**: Execution errors
- **domain**: Business rule violations
- **system**: Infrastructure failures
- **auth**: Security/permissions
- **external**: Third-party service errors

### 4. Set Severity Correctly

Use severity to indicate impact:

```python
# User can fix this - ERROR
error = FoobaraError.data_error("invalid_format", ...)

# System issue, user can't fix - CRITICAL
error = FoobaraError.system_error("database_down", ..., is_fatal=False)

# Immediate halt required - FATAL
error = FoobaraError.system_error("out_of_memory", ..., is_fatal=True)
```

### 5. Chain Related Errors

Show causality:

```python
try:
    api_result = call_api()
except ConnectionError as e:
    network_error = FoobaraError.from_exception(e)

    api_error = FoobaraError.runtime_error(
        "api_unavailable",
        "Could not connect to API"
    ).with_cause(network_error)

    raise api_error
```

### 6. Always Provide Suggestions

Help users fix the problem:

```python
# Bad
error = FoobaraError.data_error("too_short", ["name"], "Name too short")

# Good
error = FoobaraError.data_error(
    "too_short",
    ["name"],
    "Name must be at least 3 characters",
    suggestion="Enter a longer name",
    min_length=3,
    actual_length=len(name)
)
```

### 7. Use Recovery Hooks Appropriately

- **Retry**: Transient failures (network, timeout)
- **Fallback**: When stale data is acceptable
- **Circuit Breaker**: Protect against cascading failures

```python
# Configure for your use case
manager = ErrorRecoveryManager()

# Retry transient errors
manager.add_retry_hook(RetryConfig(max_attempts=3))

# Fallback to cache for data fetching
manager.add_fallback_hook(
    fallback_fn=get_from_cache,
    applicable_symbols=["api_error"]
)

# Circuit breaker for external services
manager.add_circuit_breaker_hook(
    CircuitBreakerConfig(failure_threshold=5)
)
```

### 8. Log Errors Appropriately

Include error details in logs:

```python
import logging

logger = logging.getLogger(__name__)

for error in errors.critical_errors():
    logger.error(
        f"Critical error: {error.message}",
        extra={
            "error_code": error.error_code,
            "symbol": error.symbol,
            "category": error.category,
            "context": error.context,
            "path": list(error.path)
        }
    )
```

### 9. Test Error Scenarios

Write tests for error cases:

```python
def test_validation_errors():
    result = CreateUser.run(
        name="",
        email="invalid"
    )

    assert result.is_failure()
    errors = result.errors

    # Check specific errors
    assert errors.at_path(["name"])
    assert errors.at_path(["email"])

    # Verify suggestions are present
    assert all(e.suggestion for e in errors.with_symbol("invalid_format"))
```

### 10. Serialize Errors for APIs

Format errors for API responses:

```python
# For JSON APIs
errors_json = errors.to_list()
response = {
    "success": False,
    "errors": errors_json,
    "summary": errors.summary()
}

# For human-readable responses
response_text = errors.to_human_readable(include_suggestions=True)
```

## Standard Error Symbols

Foobara defines standard error symbols in the `Symbols` class. Use these for consistency:

```python
from foobara_py.core.errors import Symbols

# Common symbols
Symbols.REQUIRED
Symbols.INVALID_FORMAT
Symbols.TOO_SHORT
Symbols.TOO_LONG
Symbols.NOT_FOUND
Symbols.ALREADY_EXISTS
Symbols.NOT_AUTHENTICATED
Symbols.FORBIDDEN
Symbols.TIMEOUT
Symbols.RATE_LIMIT_EXCEEDED
# ... and many more
```

See the source code for the complete list.

## Migration from Old Error System

If you're migrating from an older error system:

```python
# Old style (still works)
from foobara_py.core.errors import DataError

error = DataError(
    symbol="invalid",
    path=["field"],
    message="Invalid field"
)

# New style (recommended)
error = FoobaraError.data_error(
    "invalid_format",
    ["field"],
    "Invalid field format",
    suggestion="Check the format and try again"
)
```

The old `DataError` is an alias for `FoobaraError` and continues to work for backward compatibility.

## Conclusion

The enhanced error handling system provides powerful tools for creating helpful, actionable errors. By using appropriate categories, severity levels, suggestions, and recovery mechanisms, you can build robust applications that gracefully handle failures and guide users toward solutions.
