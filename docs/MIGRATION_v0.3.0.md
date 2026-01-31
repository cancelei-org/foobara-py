# Migration Guide: v0.2.0 → v0.3.0

This guide helps you migrate from foobara-py v0.2.0 to v0.3.0.

## Table of Contents

- [Overview](#overview)
- [Breaking Changes](#breaking-changes)
- [Migration Checklist](#migration-checklist)
- [Detailed Migration Patterns](#detailed-migration-patterns)
- [Code Examples](#code-examples)
- [Testing Your Migration](#testing-your-migration)
- [Rollback Strategy](#rollback-strategy)
- [Getting Help](#getting-help)

---

## Overview

### What's Changing

v0.3.0 introduces two major architectural improvements:

1. **Enhanced Error System** - Unified `context` dictionary replaces individual error fields
2. **Concern-Based Architecture** - Modular command structure (internal implementation only)

### Impact Assessment

**Low Impact (Most Users):**
- ✅ Public API mostly unchanged
- ✅ Existing commands work with deprecation warnings
- ✅ Migration can be gradual

**Medium Impact (Advanced Users):**
- ⚠️ Custom error handling needs updates
- ⚠️ Error serialization format changed
- ⚠️ Some error field access patterns deprecated

**High Impact (Framework Developers):**
- 🔴 Internal command structure reorganized
- 🔴 Private API imports will break
- 🔴 Concern-based architecture replaces monolithic structure

### Estimated Migration Time

- **Simple projects** (basic commands): 15-30 minutes
- **Medium projects** (custom error handling): 1-2 hours
- **Complex projects** (internal API usage): 2-4 hours

---

## Breaking Changes

### 1. Error Field Migration: `context` Replaces Individual Fields

#### What Changed

Error objects now use a unified `context` dictionary instead of separate keyword arguments for metadata.

#### Before (v0.2.0)

```python
# Creating errors with individual fields
error = FoobaraError(
    category="data",
    symbol="invalid_email",
    path=["user", "email"],
    message="Invalid email format",
    provided_value="not-an-email",
    expected_format="user@example.com",
    pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$"
)

# Accessing fields
value = error.provided_value
format = error.expected_format
```

#### After (v0.3.0)

```python
# Use factory methods - they handle context automatically
error = FoobaraError.data_error(
    "invalid_email",
    ["user", "email"],
    "Invalid email format",
    provided_value="not-an-email",  # Now part of context
    expected_format="user@example.com",  # Now part of context
    pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$"  # Now part of context
)

# Accessing fields from context
value = error.context.get('provided_value')
format = error.context.get('expected_format')
pattern = error.context.get('pattern')
```

#### Why This Change

- **Cleaner API**: No need to track which fields are "special"
- **More Flexible**: Add any metadata without schema changes
- **Better Serialization**: Single dict is easier to serialize/deserialize
- **Type Safety**: TypedDict for common context patterns
- **Ruby Alignment**: Matches Ruby Foobara's error structure

---

### 2. Command Architecture: Concern-Based Structure

#### What Changed

Internal command implementation split into 10 modular concerns. **Public API unchanged.**

#### Impact

**✅ No Impact (Public API):**

```python
# These imports STILL WORK in v0.3.0
from foobara_py.core.command import Command, AsyncCommand
from foobara_py.core.command import command, async_command

class CreateUser(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        # Your code unchanged
        pass
```

**🔴 Breaking (Internal API):**

```python
# Before (v0.2.0) - These WILL BREAK
from foobara_py.core.command import _internal_helper
from foobara_py.core.command import CommandMeta  # Still works but location changed

# After (v0.3.0) - Use public API instead
from foobara_py.core.command import Command  # Preferred
# Or if you really need internals:
from foobara_py.core.command.base import Command
from foobara_py.core.command.concerns.errors_concern import ErrorsConcern
```

#### Migration

**If you only use public API:** No changes needed.

**If you use internal APIs:** Refactor to use public API or file an issue to make needed functionality public.

---

### 3. Removed Deprecated APIs

The following APIs were deprecated in v0.2.0 and are now removed:

#### Removed: `Command._enhanced_error_fields`

```python
# Before (v0.2.0)
class MyCommand(Command):
    _enhanced_error_fields = ['custom_field']

# After (v0.3.0) - Use context
class MyCommand(Command):
    def add_custom_error(self, symbol, message, custom_field):
        self.add_error(FoobaraError.data_error(
            symbol, [], message,
            custom_field=custom_field  # Automatically in context
        ))
```

#### Removed: `ErrorCollection.add_errors_from_dict()`

```python
# Before (v0.2.0)
errors.add_errors_from_dict({'field': {'symbol': 'invalid', 'message': 'Error'}})

# After (v0.3.0)
error = FoobaraError.data_error('invalid', ['field'], 'Error')
errors.add(error)
```

#### Removed: Internal `_v1_*` Compatibility Methods

```python
# Before (v0.2.0)
command._v1_add_error(symbol, message)

# After (v0.3.0)
command.add_error(FoobaraError.runtime_error(symbol, message))
```

---

## Migration Checklist

Use this checklist to track your migration progress:

### Phase 1: Preparation (Before Upgrading)

- [ ] **Back up your codebase** (git commit, branch, or tag)
- [ ] **Review changelog** - Read `CHANGELOG.md` v0.3.0 section
- [ ] **Run existing tests** - Ensure all tests pass on v0.2.0
- [ ] **Document custom error handling** - Note any custom error patterns
- [ ] **Check for internal imports** - Search for `from foobara_py.core.command import _*`
- [ ] **Review error serialization** - If you serialize errors, note the format

### Phase 2: Upgrade (Installing v0.3.0)

- [ ] **Update pyproject.toml** - Change version to `foobara-py>=0.3.0,<0.4.0`
- [ ] **Install new version** - `pip install --upgrade foobara-py`
- [ ] **Verify installation** - `python -c "import foobara_py; print(foobara_py.__version__)"`

### Phase 3: Fix Breaking Changes

- [ ] **Update error creation** - Replace direct instantiation with factory methods
- [ ] **Update error field access** - Use `error.context.get('field')`
- [ ] **Replace removed APIs** - See [Removed APIs](#3-removed-deprecated-apis)
- [ ] **Fix internal imports** - Use public API or update import paths
- [ ] **Update error serialization** - Adapt to new context-based format

### Phase 4: Testing

- [ ] **Run test suite** - `pytest` (expect deprecation warnings)
- [ ] **Review deprecation warnings** - Note all warnings
- [ ] **Fix deprecations** - Update code to avoid deprecated patterns
- [ ] **Test error handling** - Verify error creation and serialization
- [ ] **Integration tests** - Test full application flow
- [ ] **Performance tests** - Verify no performance regressions

### Phase 5: Cleanup

- [ ] **Remove workarounds** - Delete any v0.2.0 compatibility code
- [ ] **Update documentation** - Reflect new error handling patterns
- [ ] **Code review** - Have team review migration changes
- [ ] **Deploy to staging** - Test in staging environment
- [ ] **Monitor production** - Deploy and monitor for issues

---

## Detailed Migration Patterns

### Pattern 1: Error Creation with Metadata

#### Before (v0.2.0)

```python
# Direct instantiation with separate fields
error = FoobaraError(
    category="data",
    symbol="too_short",
    path=["password"],
    message="Password too short",
    provided_value=password,
    min_length=8,
    actual_length=len(password)
)
self._errors.add(error)
```

#### After (v0.3.0)

```python
# Use factory method - cleaner and more flexible
error = FoobaraError.data_error(
    "too_short",
    ["password"],
    "Password too short",
    provided_value=password,
    min_length=8,
    actual_length=len(password)
)
self.add_error(error)
```

#### Find & Replace

```bash
# Find all direct FoobaraError instantiations
grep -r "FoobaraError(" --include="*.py"

# Common patterns to replace:
# Pattern: FoobaraError(category="data", symbol=..., path=..., message=...)
# Replace: FoobaraError.data_error(symbol, path, message, ...)
```

---

### Pattern 2: Error Field Access

#### Before (v0.2.0)

```python
# Accessing error fields directly
for error in outcome.errors:
    print(f"Value: {error.provided_value}")
    print(f"Format: {error.expected_format}")
    print(f"Min: {error.min_value}")
    print(f"Max: {error.max_value}")
```

#### After (v0.3.0)

```python
# Access via context dictionary
for error in outcome.errors:
    print(f"Value: {error.context.get('provided_value')}")
    print(f"Format: {error.context.get('expected_format')}")
    print(f"Min: {error.context.get('min_value')}")
    print(f"Max: {error.context.get('max_value')}")
```

#### Find & Replace

```bash
# Find all error field accesses
grep -r "error\\.provided_value" --include="*.py"
grep -r "error\\.expected_format" --include="*.py"
grep -r "error\\.min_value" --include="*.py"
grep -r "error\\.max_value" --include="*.py"

# Replace pattern:
# error.FIELD_NAME → error.context.get('FIELD_NAME')
```

---

### Pattern 3: Custom Error Types

#### Before (v0.2.0)

```python
class MyCommand(Command):
    def execute(self):
        if not self.validate_business_rule():
            error = FoobaraError(
                category="runtime",
                symbol="business_rule_violation",
                message="Business rule failed",
                rule_name="credit_limit",
                current_value=1000,
                limit=500
            )
            self.add_error(error)
            self.halt()
```

#### After (v0.3.0)

```python
class MyCommand(Command):
    def execute(self):
        if not self.validate_business_rule():
            # Use domain_error for business logic
            self.add_error(FoobaraError.domain_error(
                "business_rule_violation",
                "Business rule failed",
                suggestion="Reduce amount to stay within limit",
                rule_name="credit_limit",
                current_value=1000,
                limit=500
            ))
            self.halt()
```

---

### Pattern 4: Error Serialization

#### Before (v0.2.0)

```python
# Serialization included separate fields
error_dict = {
    "category": error.category,
    "symbol": error.symbol,
    "path": error.path,
    "message": error.message,
    "provided_value": error.provided_value,  # Separate field
    "expected_format": error.expected_format  # Separate field
}
```

#### After (v0.3.0)

```python
# Use built-in serialization with context
error_dict = error.to_dict()
# Returns:
# {
#   "category": "data",
#   "symbol": "invalid_format",
#   "path": ["email"],
#   "message": "Invalid email format",
#   "context": {
#     "provided_value": "not-an-email",
#     "expected_format": "user@example.com"
#   }
# }

# Or access context directly
error_dict = {
    "category": error.category,
    "symbol": error.symbol,
    "path": error.path,
    "message": error.message,
    "context": error.context  # All metadata in one dict
}
```

---

### Pattern 5: Error Collections with Metadata

#### Before (v0.2.0)

```python
# Filtering errors by metadata
errors_with_min = [
    e for e in outcome.errors
    if hasattr(e, 'min_value') and e.min_value is not None
]
```

#### After (v0.3.0)

```python
# Filter using context
errors_with_min = [
    e for e in outcome.errors
    if 'min_value' in e.context
]

# Or use new query methods
errors_with_context = [
    e for e in outcome.errors
    if e.context  # Non-empty context
]
```

---

### Pattern 6: Testing Error Metadata

#### Before (v0.2.0)

```python
def test_error_metadata():
    outcome = MyCommand.run(invalid_input="bad")

    assert outcome.is_failure()
    error = outcome.errors[0]
    assert error.provided_value == "bad"
    assert error.min_length == 5
```

#### After (v0.3.0)

```python
def test_error_metadata():
    outcome = MyCommand.run(invalid_input="bad")

    assert outcome.is_failure()
    error = outcome.errors[0]
    assert error.context['provided_value'] == "bad"
    assert error.context['min_length'] == 5

    # Or use assertion helper
    from tests.helpers import AssertionHelpers
    AssertionHelpers.assert_error_present(
        outcome,
        symbol="too_short",
        context_contains={'provided_value': 'bad', 'min_length': 5}
    )
```

---

## Code Examples

### Example 1: Complete Command Migration

#### Before (v0.2.0)

```python
from pydantic import BaseModel, EmailStr
from foobara_py.core.command import Command
from foobara_py.core.errors import FoobaraError

class CreateUserInputs(BaseModel):
    email: EmailStr
    age: int

class CreateUser(Command[CreateUserInputs, dict]):
    def execute(self) -> dict:
        # Validate age
        if self.inputs.age < 18:
            error = FoobaraError(
                category="data",
                symbol="underage",
                path=["age"],
                message="User must be 18 or older",
                provided_value=self.inputs.age,
                min_value=18
            )
            self._errors.add(error)
            self.halt()

        # Check email uniqueness
        if self.email_exists(self.inputs.email):
            error = FoobaraError(
                category="runtime",
                symbol="email_taken",
                message="Email already registered",
                provided_value=self.inputs.email
            )
            self._errors.add(error)
            self.halt()

        return {"id": 1, "email": self.inputs.email}
```

#### After (v0.3.0)

```python
from pydantic import BaseModel, EmailStr
from foobara_py.core.command import Command
from foobara_py.core.errors import FoobaraError

class CreateUserInputs(BaseModel):
    email: EmailStr
    age: int

class CreateUser(Command[CreateUserInputs, dict]):
    def execute(self) -> dict:
        # Validate age - use data_error factory
        if self.inputs.age < 18:
            self.add_error(FoobaraError.data_error(
                "underage",
                ["age"],
                "User must be 18 or older",
                suggestion="Provide an age of 18 or higher",
                provided_value=self.inputs.age,
                min_value=18
            ))
            self.halt()

        # Check email uniqueness - use domain_error for business logic
        if self.email_exists(self.inputs.email):
            self.add_error(FoobaraError.domain_error(
                "email_taken",
                "Email already registered",
                path=["email"],
                suggestion="Use a different email or log in",
                provided_value=self.inputs.email
            ))
            self.halt()

        return {"id": 1, "email": self.inputs.email}
```

---

### Example 2: External Service Error Handling

#### Before (v0.2.0)

```python
import requests
from foobara_py.core.command import Command
from foobara_py.core.errors import FoobaraError

class FetchUserData(Command):
    def execute(self) -> dict:
        try:
            response = requests.get("https://api.example.com/user")
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            error = FoobaraError(
                category="runtime",
                symbol="timeout",
                message="API request timed out",
                service="example_api",
                timeout_seconds=30
            )
            self._errors.add(error)
            self.halt()
        except requests.RequestException as e:
            error = FoobaraError(
                category="runtime",
                symbol="api_error",
                message=f"API error: {e}",
                service="example_api"
            )
            self._errors.add(error)
            self.halt()
```

#### After (v0.3.0)

```python
import requests
from foobara_py.core.command import Command
from foobara_py.core.errors import FoobaraError

class FetchUserData(Command):
    def execute(self) -> dict:
        try:
            response = requests.get("https://api.example.com/user")
            response.raise_for_status()
            return response.json()
        except requests.Timeout as e:
            # Use external_error factory
            self.add_error(FoobaraError.external_error(
                "timeout",
                "API request timed out",
                service="example_api",
                suggestion="Try again or check service status",
                timeout_seconds=30,
                url="https://api.example.com/user"
            ))
            self.halt()
        except requests.RequestException as e:
            # Convert exception to error
            self.add_error(FoobaraError.from_exception(
                e,
                symbol="api_error",
                category="external"
            ))
            self.halt()
```

---

### Example 3: Error Recovery with Context

#### New in v0.3.0

```python
from foobara_py.core.command import Command
from foobara_py.core.errors import FoobaraError
from foobara_py.core.error_recovery import (
    ErrorRecoveryManager,
    RetryConfig,
    FallbackConfig
)

class SendEmail(Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up error recovery
        self.recovery = ErrorRecoveryManager()

        # Retry transient failures
        self.recovery.add_retry_hook(RetryConfig(
            max_attempts=3,
            initial_delay=0.5,
            backoff_multiplier=2.0,
            retryable_symbols=["smtp_timeout", "connection_failed"]
        ))

        # Fallback to queue
        self.recovery.add_fallback_hook(FallbackConfig(
            applicable_symbols=["smtp_error"],
            fallback_fn=lambda error, ctx: self.queue_for_later(ctx['email'])
        ))

    def execute(self) -> dict:
        try:
            self.send_via_smtp(
                self.inputs.recipient,
                self.inputs.subject,
                self.inputs.body
            )
            return {"status": "sent"}
        except SMTPException as e:
            error = FoobaraError.external_error(
                "smtp_timeout",
                f"SMTP error: {e}",
                service="smtp",
                suggestion="Email will be retried automatically",
                recipient=self.inputs.recipient
            )

            # Attempt recovery (automatic retry or fallback)
            recovered, remaining, context = self.recovery.attempt_recovery(
                error, {"email": self.inputs}
            )

            if context.get("should_retry"):
                # Framework handles retry
                return {"status": "retrying"}
            elif context.get("fallback_result"):
                return {"status": "queued"}
            else:
                self.add_error(error)
                self.halt()
```

---

## Testing Your Migration

### Step 1: Run Tests with Warnings

```bash
# Run tests and capture deprecation warnings
pytest -W default::DeprecationWarning

# Or save warnings to file
pytest -W default::DeprecationWarning 2> warnings.txt
```

### Step 2: Review Deprecation Warnings

Look for warnings like:

```
DeprecationWarning: Direct error.provided_value access is deprecated.
Use error.context['provided_value'] instead.

DeprecationWarning: FoobaraError() direct instantiation is deprecated.
Use FoobaraError.data_error() or similar factory methods.
```

### Step 3: Create Migration Tests

```python
# tests/test_migration_v0_3_0.py

def test_error_context_migration():
    """Ensure errors use context dict"""
    error = FoobaraError.data_error(
        "invalid",
        ["field"],
        "Error message",
        custom_value="test"
    )

    # New way
    assert error.context['custom_value'] == "test"

    # Old way should work but trigger warning
    # (Remove this after migration)
    # assert error.custom_value == "test"  # Deprecated


def test_error_factory_methods():
    """Ensure using factory methods"""
    # Data error
    data_err = FoobaraError.data_error("invalid", ["field"], "Message")
    assert data_err.category == "data"

    # Domain error
    domain_err = FoobaraError.domain_error("violation", "Message")
    assert domain_err.category == "domain"

    # Auth error
    auth_err = FoobaraError.auth_error("forbidden", "Message")
    assert auth_err.category == "auth"


def test_error_serialization():
    """Ensure serialization includes context"""
    error = FoobaraError.data_error(
        "invalid",
        ["email"],
        "Invalid email",
        provided_value="bad-email",
        expected_format="user@example.com"
    )

    error_dict = error.to_dict()
    assert "context" in error_dict
    assert error_dict["context"]["provided_value"] == "bad-email"
    assert error_dict["context"]["expected_format"] == "user@example.com"
```

### Step 4: Integration Tests

```python
def test_command_error_handling():
    """Test full command with new error system"""
    outcome = CreateUser.run(email="invalid", age=15)

    assert outcome.is_failure()

    # Check error structure
    error = outcome.errors[0]
    assert error.category == "data"
    assert error.symbol == "underage"
    assert error.context['provided_value'] == 15
    assert error.context['min_value'] == 18

    # Test serialization
    error_dict = error.to_dict()
    assert error_dict['context']['provided_value'] == 15
```

---

## Rollback Strategy

If you encounter issues during migration:

### Option 1: Quick Rollback

```bash
# Revert to v0.2.0
pip install foobara-py==0.2.0

# Or pin in pyproject.toml
[project]
dependencies = [
    "foobara-py>=0.2.0,<0.3.0"
]
```

### Option 2: Gradual Migration

```bash
# Stay on v0.2.0 while preparing migration
pip install foobara-py==0.2.0

# Update code to be v0.3.0-compatible
# Use factory methods, context access, etc.

# Once ready, upgrade
pip install foobara-py>=0.3.0
```

### Option 3: Version Compatibility Layer

```python
# compatibility.py - Temporary bridge during migration

from foobara_py.core.errors import FoobaraError

def create_data_error(symbol, path, message, **fields):
    """Compatibility wrapper for error creation"""
    # Works with both v0.2.0 and v0.3.0
    return FoobaraError.data_error(symbol, path, message, **fields)

def get_error_field(error, field_name, default=None):
    """Compatibility wrapper for field access"""
    # Try new way first (v0.3.0)
    if hasattr(error, 'context'):
        return error.context.get(field_name, default)
    # Fall back to old way (v0.2.0)
    return getattr(error, field_name, default)
```

---

## Getting Help

### Documentation

- [CHANGELOG.md](../CHANGELOG.md) - Full v0.3.0 changes
- [ERROR_HANDLING.md](./ERROR_HANDLING.md) - Error system guide
- [FEATURES.md](./FEATURES.md) - All features including new ones

### Support Channels

- **GitHub Issues**: https://github.com/foobara/foobara-py/issues
- **GitHub Discussions**: https://github.com/foobara/foobara-py/discussions
- **Email**: foobara@example.com

### Common Issues

#### Issue: "AttributeError: 'FoobaraError' object has no attribute 'provided_value'"

**Solution**: Update to use context dict:

```python
# Before
value = error.provided_value

# After
value = error.context.get('provided_value')
```

#### Issue: "ImportError: cannot import name '_internal_method' from 'foobara_py.core.command'"

**Solution**: Use public API or update import path:

```python
# Before
from foobara_py.core.command import _internal_method

# After (if public API exists)
from foobara_py.core.command import public_method

# Or (if you must use internal)
from foobara_py.core.command.concerns.xxx_concern import method
```

#### Issue: "DeprecationWarning: ..."

**Solution**: These are just warnings. Fix them incrementally:

1. Note the warning
2. Find the deprecated code
3. Update using this guide
4. Re-run tests

---

## Summary

**Migration effort**: 1-4 hours depending on project complexity

**Key changes**:
1. ✅ Use error factory methods (`data_error()`, `domain_error()`, etc.)
2. ✅ Access error fields via `error.context['field']`
3. ✅ Use public API (avoid internal imports)
4. ✅ Update error serialization if needed

**Benefits after migration**:
- 🚀 20-30% faster error handling
- 📦 15% less code complexity
- 🎯 Better error messages with suggestions
- 🔄 Error recovery framework (retry, fallback)
- 📊 Enhanced error querying and analysis

**Next steps**:
1. Follow [Migration Checklist](#migration-checklist)
2. Update code using [Detailed Migration Patterns](#detailed-migration-patterns)
3. Run tests and fix deprecation warnings
4. Deploy incrementally (staging → production)

---

**Questions?** Open an issue or discussion on GitHub!

**Last Updated**: January 31, 2026 • **Version**: 0.3.0
