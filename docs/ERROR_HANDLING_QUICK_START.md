# Error Handling Quick Start

Quick reference guide for using the enhanced error handling system.

## Basic Error Creation

```python
from foobara_py.core import FoobaraError, Symbols

# Data validation error
error = FoobaraError.data_error(
    Symbols.INVALID_FORMAT,
    ["email"],
    "Invalid email format",
    suggestion="Use format: user@example.com"
)

# Runtime error
error = FoobaraError.runtime_error(
    Symbols.TIMEOUT,
    "Request timed out",
    timeout_seconds=30
)

# Domain/business error
error = FoobaraError.domain_error(
    "insufficient_balance",
    "Not enough funds",
    current=100,
    needed=150
)

# Auth error
error = FoobaraError.auth_error(
    Symbols.NOT_AUTHENTICATED,
    "Please log in"
)

# External service error
error = FoobaraError.external_error(
    "api_error",
    "Payment failed",
    service="stripe"
)
```

## Error Collections

```python
from foobara_py.core import ErrorCollection

errors = ErrorCollection()

# Add errors
errors.add(FoobaraError.data_error(...))
errors.add_all(error1, error2, error3)

# Query errors
email_errors = errors.at_path(["email"])
critical = errors.critical_errors()
with_help = errors.with_suggestions()

# Display to users
print(errors.to_human_readable())

# Get summary
stats = errors.summary()
```

## Error Recovery

```python
from foobara_py.core import ErrorRecoveryManager, RetryConfig

# Setup recovery
manager = ErrorRecoveryManager()
manager.add_retry_hook(RetryConfig(max_attempts=3))
manager.add_fallback_hook(fallback_value={"default": "data"})

# Attempt recovery
recovered, remaining, context = manager.attempt_recovery(error)

if context.get("should_retry"):
    delay = context["retry_delay"]
    # Retry after delay
```

## Common Patterns

### Validation Errors

```python
if not email:
    error = FoobaraError.data_error(
        Symbols.REQUIRED,
        ["email"],
        "Email is required",
        suggestion="Enter your email address"
    )

if not is_valid_email(email):
    error = FoobaraError.data_error(
        Symbols.INVALID_FORMAT,
        ["email"],
        "Invalid email format",
        suggestion="Use format: user@example.com",
        provided=email
    )
```

### Error Chaining

```python
try:
    api_call()
except ConnectionError as e:
    network_err = FoobaraError.from_exception(e)

    operation_err = FoobaraError.runtime_error(
        "operation_failed",
        "Could not complete operation"
    ).with_cause(network_err)
```

### Human-Readable Output

```python
# For end users
errors = ErrorCollection()
# ... add errors ...

print(errors.to_human_readable())
# Errors:
# 1. 🔸 [email] Invalid email format
#    💡 Suggestion: Use user@example.com
```

## Standard Symbols

```python
from foobara_py.core import Symbols

# Validation
Symbols.REQUIRED
Symbols.INVALID_FORMAT
Symbols.TOO_SHORT
Symbols.TOO_LONG

# Records
Symbols.NOT_FOUND
Symbols.ALREADY_EXISTS

# Auth
Symbols.NOT_AUTHENTICATED
Symbols.FORBIDDEN
Symbols.TOKEN_EXPIRED

# Runtime
Symbols.TIMEOUT
Symbols.CONNECTION_FAILED
Symbols.RATE_LIMIT_EXCEEDED
```

## See Also

- Full documentation: `docs/ERROR_HANDLING.md`
- Examples: `examples/error_handling_demo.py`
- Technical details: `ERROR_SYSTEM_ENHANCEMENTS.md`
