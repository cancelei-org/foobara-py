# Error System Enhancements

## Overview

This document describes the comprehensive enhancements made to the foobara-py error handling system to match Ruby Foobara patterns while adding powerful new features for better error management, recovery, and user experience.

## What Was Enhanced

### 1. Error Class Improvements (`foobara_py/core/errors.py`)

#### Better Error Categories

Extended error categories beyond the basic data/runtime/system to include:

- **Data/Validation**: Input validation errors (`data`, `validation`, `input`)
- **Runtime**: Execution errors (`runtime`, `execution`)
- **Domain**: Business logic errors (`domain`, `business_rule`)
- **System**: Infrastructure errors (`system`, `infrastructure`)
- **Auth**: Security errors (`auth`, `authorization`, `authentication`)
- **External**: Third-party service errors (`external`, `network`, `api`)

```python
# Domain/business rule error
error = FoobaraError.domain_error(
    symbol="insufficient_balance",
    message="Account balance too low",
    current_balance=100,
    requested=150
)

# External service error
error = FoobaraError.external_error(
    symbol="payment_failed",
    message="Payment gateway error",
    service="stripe"
)
```

#### Error Severity Levels

Added severity levels for error prioritization:

- `DEBUG` - Informational
- `INFO` - Minor issue
- `WARNING` - Potential problem
- `ERROR` - Standard error (default)
- `CRITICAL` - Severe error
- `FATAL` - Unrecoverable error

```python
from foobara_py.core.errors import ErrorSeverity

error = FoobaraError(
    category="data",
    symbol="deprecated_field",
    severity=ErrorSeverity.WARNING,
    message="This field will be removed in v2.0"
)
```

#### Error Context Tracking

Enhanced context with additional fields:

- **Cause**: Error that caused this error (chaining)
- **Suggestion**: Actionable fix suggestion
- **Stack Trace**: Captured stack for debugging
- **Timestamp**: When error occurred
- **Error Code**: Machine-readable code
- **Help URL**: Link to documentation

```python
error = FoobaraError.data_error(
    symbol="invalid_email",
    path=["email"],
    message="Invalid email format",
    suggestion="Use format: user@example.com",
    provided_value=email
)
error.help_url = "https://docs.example.com/email-validation"
error.capture_stack_trace()
```

#### Error Chaining

Track causality through error chains:

```python
network_error = FoobaraError.external_error(
    "connection_failed",
    "Network timeout"
)

api_error = FoobaraError.runtime_error(
    "api_call_failed",
    "API unavailable"
).with_cause(network_error)

chain = api_error.get_error_chain()  # [api_error, network_error]
root = api_error.get_root_cause()     # network_error
```

#### Enhanced Factory Methods

New factory methods for different error types:

```python
# Data/validation errors
FoobaraError.data_error(symbol, path, message, suggestion=None, **context)
FoobaraError.validation_error(...)  # Alias for data_error

# Domain/business logic errors
FoobaraError.domain_error(symbol, message, path=(), suggestion=None, **context)

# Auth errors
FoobaraError.auth_error(symbol, message, suggestion=None, **context)

# External service errors
FoobaraError.external_error(symbol, message, service=None, suggestion=None, **context)

# From Python exceptions
FoobaraError.from_exception(exception, symbol="exception", category="runtime")
```

### 2. Error Collection Improvements

#### Enhanced Querying

New query methods for ErrorCollection:

```python
errors = ErrorCollection()

# By severity
critical = errors.critical_errors()
by_level = errors.by_severity(ErrorSeverity.ERROR)
sorted_errors = errors.sort_by_severity()
most_severe = errors.most_severe()

# By category
domain = errors.domain_errors()
auth = errors.auth_errors()
system = errors.system_errors()

# Errors with suggestions
actionable = errors.with_suggestions()

# Grouping
by_path = errors.group_by_path()
by_category = errors.group_by_category()
```

#### Error Prioritization

Sort and filter errors by severity:

```python
# Handle most severe errors first
for error in errors.sort_by_severity():
    if error.severity == ErrorSeverity.FATAL:
        # Immediate halt
        break
    elif error.severity == ErrorSeverity.CRITICAL:
        # Alert ops team
        pass
```

#### Human-Readable Output

Format errors for end users:

```python
# Console-friendly format with emojis
print(errors.to_human_readable())

# Errors:
# 1. 🔸 [email] Invalid email format
#    💡 Suggestion: Use format: user@example.com
#
# 2. 🔴 [database] Connection failed
#    💡 Suggestion: Check database connection
```

#### Error Summaries

Statistical overview of errors:

```python
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

### 3. Error Serialization Enhancements

#### Enhanced JSON Format

Serialization includes new fields:

```python
error_dict = error.to_dict(include_stack_trace=True)
# {
#   "key": "data.email.invalid_format",
#   "category": "data",
#   "symbol": "invalid_format",
#   "path": ["email"],
#   "message": "Invalid email format",
#   "severity": "error",
#   "error_code": "data.email.invalid_format",
#   "suggestion": "Use user@example.com",
#   "help_url": "https://docs.example.com/email",
#   "timestamp": 1234567890.123,
#   "cause": {...},  # Nested cause error
#   "stack_trace": [...]  # If included
# }
```

### 4. Error Recovery System (`foobara_py/core/error_recovery.py`)

#### Retry Logic

Automatically retry transient failures:

```python
from foobara_py.core.error_recovery import (
    ErrorRecoveryManager,
    RetryConfig
)

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

error = FoobaraError.runtime_error("timeout", "Request timed out")
recovered, remaining, context = manager.attempt_recovery(error, {"attempt": 1})

if context.get("should_retry"):
    delay = context["retry_delay"]
    # Sleep and retry
```

#### Fallback Strategies

Provide fallback values when operations fail:

```python
# Static fallback
manager.add_fallback_hook(
    fallback_value={"default": "data"},
    applicable_symbols=["api_error"]
)

# Dynamic fallback
def get_cached_data(error, context):
    return cache.get(context["cache_key"])

manager.add_fallback_hook(
    fallback_fn=get_cached_data,
    applicable_symbols=["cache_miss"]
)
```

#### Circuit Breaker Pattern

Prevent cascading failures:

```python
from foobara_py.core.error_recovery import (
    CircuitBreakerHook,
    CircuitBreakerConfig
)

hook = CircuitBreakerHook(
    CircuitBreakerConfig(
        failure_threshold=5,    # Open after 5 failures
        success_threshold=2,    # Close after 2 successes
        timeout=60.0           # Try again after 60s
    )
)
manager.add_hook(hook)

# Check before attempting operation
if hook.check_before_execution("external_api"):
    try:
        result = call_external_api()
        hook.record_success("external_api")
    except Exception as e:
        hook.record_failure("external_api")
```

#### Custom Recovery Hooks

Implement custom recovery strategies:

```python
from foobara_py.core.error_recovery import ErrorRecoveryHook

class CacheRecoveryHook(ErrorRecoveryHook):
    def should_recover(self, error, context):
        return error.symbol in ["db_error", "api_error"]

    def recover(self, error, context):
        cached = self.cache.get(context.get("cache_key"))
        if cached:
            context["fallback_result"] = cached
            return None  # Success
        return error  # Failed

manager.add_hook(CacheRecoveryHook())
```

### 5. Comprehensive Error Symbols

Expanded standard error symbols:

```python
from foobara_py.core.errors import Symbols

# Data validation
Symbols.REQUIRED
Symbols.INVALID_FORMAT
Symbols.PATTERN_MISMATCH
Symbols.NULL_NOT_ALLOWED

# String constraints
Symbols.TOO_SHORT
Symbols.TOO_LONG
Symbols.BLANK

# Collections
Symbols.TOO_FEW_ELEMENTS
Symbols.TOO_MANY_ELEMENTS
Symbols.DUPLICATE_ELEMENT

# Records
Symbols.NOT_FOUND
Symbols.ALREADY_EXISTS
Symbols.STALE_RECORD
Symbols.INVALID_STATE

# Auth
Symbols.NOT_AUTHENTICATED
Symbols.FORBIDDEN
Symbols.TOKEN_EXPIRED
Symbols.INSUFFICIENT_PERMISSIONS

# Runtime
Symbols.TIMEOUT
Symbols.DEADLOCK
Symbols.RESOURCE_EXHAUSTED

# External
Symbols.CONNECTION_FAILED
Symbols.RATE_LIMIT_EXCEEDED
Symbols.SERVICE_UNAVAILABLE

# Business logic
Symbols.BUSINESS_RULE_VIOLATION
Symbols.CONSTRAINT_VIOLATION
Symbols.PRECONDITION_FAILED

# File/IO
Symbols.FILE_NOT_FOUND
Symbols.PERMISSION_DENIED
```

### 6. Error Suggestions

Built-in suggestions for common errors:

```python
from foobara_py.core.errors import ERROR_SUGGESTIONS

# Get suggestion for symbol
suggestion = ERROR_SUGGESTIONS.get(Symbols.REQUIRED)
# "Provide a value for this field"

# Errors automatically get suggestions
error = FoobaraError.data_error(
    Symbols.TOO_SHORT,
    ["password"],
    "Password too short"
)
# Auto-suggestion: "Increase the length of this value"
```

## Testing

Comprehensive test suite in `tests/test_error_enhancements.py`:

- **33 test cases** covering all new features
- Error severity and category handling
- Error chaining and causality
- Stack trace capture
- Error serialization
- Recovery mechanisms (retry, fallback, circuit breaker)
- Backward compatibility

Run tests:

```bash
pytest tests/test_error_enhancements.py -v
```

## Documentation

### User Guide

Comprehensive guide in `docs/ERROR_HANDLING.md`:

- Overview of error system
- Error categories and severity
- Creating and managing errors
- Error collections
- Error recovery patterns
- Best practices
- Migration guide

### Demo

Interactive demonstration in `examples/error_handling_demo.py`:

```bash
python examples/error_handling_demo.py
```

Shows real-world usage of:
- Error creation with context
- Error chaining
- Error collections and queries
- Recovery strategies
- Severity-based handling

## Backward Compatibility

All enhancements are fully backward compatible:

- Existing `DataError` alias works
- Old method names preserved (`add_error`, `add_errors`)
- Default values for new fields
- No breaking changes to existing APIs

```python
# Old code continues to work
error = DataError(
    symbol="invalid",
    path=["field"],
    message="Invalid"
)

# New code uses enhanced features
error = FoobaraError.data_error(
    "invalid_format",
    ["field"],
    "Invalid format",
    suggestion="Fix the format"
)
```

## Migration Guide

### From Old Error System

```python
# Before
error = DataError(
    category="data",
    symbol="invalid",
    path=["field"],
    message="Invalid field"
)

# After (recommended)
error = FoobaraError.data_error(
    "invalid_format",
    ["field"],
    "Field format is invalid",
    suggestion="Check the format and try again",
    expected_format="YYYY-MM-DD"
)
```

### Adding Error Recovery

```python
# Configure recovery for your command
from foobara_py.core import (
    ErrorRecoveryManager,
    RetryConfig,
    CircuitBreakerConfig
)

manager = ErrorRecoveryManager()

# Retry transient errors
manager.add_retry_hook(
    RetryConfig(max_attempts=3)
)

# Circuit breaker for external services
manager.add_circuit_breaker_hook(
    CircuitBreakerConfig(failure_threshold=5)
)

# Use in command
class MyCommand(Command):
    def execute(self):
        try:
            result = risky_operation()
        except Exception as e:
            error = FoobaraError.from_exception(e)
            recovered, remaining, context = manager.attempt_recovery(error)

            if context.get("should_retry"):
                # Retry logic
                pass
```

## Benefits

### For Developers

- **Better Debugging**: Stack traces, error chains, detailed context
- **Clearer Code**: Specific error categories and symbols
- **Less Boilerplate**: Factory methods and recovery hooks
- **Flexible Recovery**: Retry, fallback, circuit breaker patterns
- **Type Safety**: Enums for categories and severity

### For Users

- **Actionable Errors**: Suggestions on how to fix issues
- **Clear Messages**: Human-readable error formatting
- **Better Experience**: Graceful degradation with fallbacks
- **Help Resources**: Links to documentation

### For Operations

- **Better Monitoring**: Severity levels for alerting
- **Error Analysis**: Summary statistics and grouping
- **Resilience**: Circuit breakers prevent cascading failures
- **Debugging Tools**: Stack traces in production errors

## Future Enhancements

Potential future improvements:

1. **Error Localization**: Multi-language error messages
2. **Error Metrics**: Prometheus/StatsD integration
3. **Error Aggregation**: Group similar errors
4. **Smart Suggestions**: ML-based suggestion generation
5. **Error Templates**: Predefined error patterns
6. **Async Recovery**: Async retry and fallback hooks

## Summary

The enhanced error handling system provides:

✅ **Rich Error Context** - Causes, suggestions, stack traces
✅ **Better Organization** - Categories and severity levels
✅ **Error Recovery** - Retry, fallback, circuit breaker
✅ **User-Friendly** - Actionable suggestions and help
✅ **Developer-Friendly** - Clean APIs and comprehensive docs
✅ **Production-Ready** - Monitoring, debugging, resilience
✅ **Fully Compatible** - No breaking changes

These enhancements make foobara-py errors more helpful, actionable, and robust - matching Ruby Foobara patterns while adding Python-specific improvements.
