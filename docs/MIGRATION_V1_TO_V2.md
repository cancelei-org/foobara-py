# V1 to V2 Migration Guide

**Last Updated:** 2026-01-30
**Version:** 0.2.0 → 0.3.0 → 0.4.0

## Overview

This guide helps you migrate from foobara-py V1 (deprecated) to V2 (current). The migration is straightforward, and most code can be updated in under an hour.

## Why Migrate?

V1 is deprecated and will be removed in v0.4.0. V2 offers:

- **15-25% faster** performance
- **Full Ruby Foobara parity** (95% feature complete)
- **8-state lifecycle** with comprehensive hooks
- **Transaction support** with automatic rollback
- **Entity loading** system
- **Domain mappers** for type conversion
- **Better error handling** with path tracking

## Timeline

| Version | Status | What Happens |
|---------|--------|--------------|
| **v0.2.0** (current) | V1 in `_deprecated/` | No warnings, V1 still works |
| **v0.3.0** (upcoming) | Deprecation warnings | Warnings logged for V1 usage |
| **v0.4.0** (future) | V1 removed | `_deprecated/` directory deleted |

**Recommendation:** Migrate now to avoid issues with v0.4.0 release.

## Quick Start: 3-Step Migration

### Step 1: Update Imports (2 minutes)

```python
# ❌ V1 (Deprecated)
from foobara_py.core.command import Command
from foobara_py.core.errors import Error
from foobara_py.domain.domain import Domain

# ✅ V2 (Current)
from foobara_py import Command, FoobaraError, Domain
```

### Step 2: Update Outcome API (2 minutes)

```python
# ❌ V1 (Deprecated)
if outcome.success:
    result = outcome.value

# ✅ V2 (Current)
if outcome.is_success():
    result = outcome.unwrap()
```

### Step 3: Test (5 minutes)

```bash
# Check for V1 usage
grep -r "from foobara_py.core.command import" . --include="*.py"

# Run tests with warnings
python -W default -m pytest tests/ -v

# Verify no errors
pytest tests/ -v
```

Done! Most migrations are complete after these 3 steps.

## Do You Need to Migrate?

### ✅ You DON'T need to migrate if:

- You import from the public API: `from foobara_py import Command`
- You see no deprecation warnings when running your code
- You use `outcome.is_success()` and `outcome.unwrap()`

**The public API has always used V2 implementations.** If you followed best practices, you're already on V2!

### ⚠️ You NEED to migrate if:

- You import from internal paths: `from foobara_py.core.command import Command`
- You see deprecation warnings about `_deprecated`
- You use `outcome.success` or `outcome.value`
- You directly manipulate `self.errors` collection

## Breaking Changes

### 1. Import Paths

| V1 (Deprecated) | V2 (Current) |
|-----------------|--------------|
| `from foobara_py.core.command import Command` | `from foobara_py import Command` |
| `from foobara_py.core.errors import Error` | `from foobara_py import FoobaraError` |
| `from foobara_py.domain.domain import Domain` | `from foobara_py import Domain` |
| `from foobara_py.connectors.mcp import MCPConnector` | `from foobara_py.connectors import MCPConnector` |

### 2. Outcome API

| V1 (Deprecated) | V2 (Current) |
|-----------------|--------------|
| `outcome.success` | `outcome.is_success()` |
| `outcome.failure` | `outcome.is_failure()` |
| `outcome.value` | `outcome.unwrap()` |
| `outcome.result` | `outcome.unwrap()` |

### 3. Error Handling

| V1 (Deprecated) | V2 (Current) |
|-----------------|--------------|
| `self.errors.add("symbol", "message")` | `self.add_runtime_error("symbol", "message")` |
| `errors.add_error(error)` | `errors.add(error)` (or keep using deprecated alias) |
| `errors.add_errors(e1, e2)` | `errors.add_all(e1, e2)` (or keep using deprecated alias) |

### 4. Domain Registration

```python
# ❌ V1 (Deprecated)
class CreateUser(Command):
    _domain = users

# ✅ V2 (Current)
@users.command
class CreateUser(Command[CreateUserInputs, User]):
    pass
```

## What Hasn't Changed

These APIs remain **100% compatible**:

✅ Command execution: `MyCommand.run(param1=value1)`
✅ Public API imports: `from foobara_py import Command`
✅ Basic command structure
✅ Domain creation: `Domain("Name")`
✅ Error collection aliases (deprecated but still work)

## Step-by-Step Migration

### Phase 1: Update Imports (5 minutes)

**Find V1 imports:**
```bash
grep -r "from foobara_py.core.command import" .
grep -r "from foobara_py.core.errors import" .
grep -r "from foobara_py.domain.domain import" .
```

**Replace with V2 imports:**
```python
# One-liner for common imports
from foobara_py import Command, Domain, FoobaraError, AsyncCommand
```

### Phase 2: Update Outcome API (10 minutes)

**Find V1 outcome usage:**
```bash
grep -r "outcome\.success" .
grep -r "outcome\.value" .
```

**Update to V2:**
```python
# Before (V1)
outcome = MyCommand.run(...)
if outcome.success:
    result = outcome.value

# After (V2)
outcome = MyCommand.run(...)
if outcome.is_success():
    result = outcome.unwrap()
```

### Phase 3: Add Type Parameters (20 minutes)

V2 commands should include generic type parameters for better type safety:

```python
# Before (V1)
class CreateUser(Command):
    def execute(self):
        return {"id": 1, "name": "John"}

# After (V2)
from pydantic import BaseModel

class CreateUserInputs(BaseModel):
    name: str

class User(BaseModel):
    id: int
    name: str

class CreateUser(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        return User(id=1, name=self.inputs.name)
```

### Phase 4: Update Error Handling (15 minutes)

```python
# Before (V1)
class MyCommand(Command):
    def execute(self):
        if error_condition:
            self.errors.add("error_symbol", "Error message")
            return None

# After (V2)
class MyCommand(Command[MyInputs, MyResult]):
    def execute(self) -> MyResult:
        if error_condition:
            self.add_runtime_error(
                "error_symbol",
                "Error message",
                halt=True  # Stop execution immediately
            )
            return None
```

### Phase 5: Test Thoroughly (30 minutes)

```bash
# 1. Check for deprecation warnings
python -W default -m pytest tests/ -v

# 2. Run full test suite
pytest tests/ -v --cov

# 3. Verify no V1 imports remain
grep -r "from foobara_py.core.command import" . --include="*.py" | grep -v "_deprecated"

# 4. Check for V1 outcome API
grep -r "outcome\.success\b" . --include="*.py"
grep -r "outcome\.value\b" . --include="*.py"
```

## Complete Migration Example

### Before (V1)

```python
from foobara_py.core.command import Command
from foobara_py.domain.domain import Domain

users = Domain("Users")

class CreateUser(Command):
    _domain = users

    def execute(self):
        name = self.inputs.get("name")
        email = self.inputs.get("email")

        if not email or "@" not in email:
            self.errors.add("invalid_email", "Email is invalid")
            return None

        return {"id": 1, "name": name, "email": email}

# Usage
outcome = CreateUser.run(name="John", email="john@example.com")
if outcome.success:
    user = outcome.value
    print(f"Created user: {user['name']}")
else:
    for error in outcome.errors:
        print(f"Error: {error.message}")
```

### After (V2)

```python
from pydantic import BaseModel, Field, field_validator
from foobara_py import Domain, Command

users = Domain("Users")

class CreateUserInputs(BaseModel):
    name: str = Field(..., description="User's name")
    email: str = Field(..., description="Email address")

    @field_validator('email')
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Email is invalid")
        return v

class User(BaseModel):
    id: int
    name: str
    email: str

@users.command
class CreateUser(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        # Email validation automatic via Pydantic
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email
        )

# Usage (unchanged!)
outcome = CreateUser.run(name="John", email="john@example.com")
if outcome.is_success():
    user = outcome.unwrap()
    print(f"Created user: {user.name}")
else:
    for error in outcome.errors:
        print(f"Error: {error.message}")
```

### Key Changes:
1. ✅ Import from public API
2. ✅ Created Pydantic input model with validation
3. ✅ Added type parameters to Command
4. ✅ Created structured User output model
5. ✅ Used decorator for domain registration
6. ✅ Updated outcome API to methods

## Automated Migration Script

Save as `migrate_v1_to_v2.sh`:

```bash
#!/bin/bash
# Simple migration script for foobara-py V1 to V2

echo "🔄 Migrating foobara-py V1 imports to V2..."

# Backup first
echo "📦 Creating backup..."
tar -czf pre-migration-backup.tar.gz .

# Update imports
echo "📝 Updating imports..."
find . -type f -name "*.py" ! -path "./_deprecated/*" ! -path "./venv/*" \
    -exec sed -i.bak 's/from foobara_py\.core\.command import Command/from foobara_py import Command/g' {} +

find . -type f -name "*.py" ! -path "./_deprecated/*" ! -path "./venv/*" \
    -exec sed -i.bak 's/from foobara_py\.core\.errors import Error/from foobara_py import FoobaraError/g' {} +

find . -type f -name "*.py" ! -path "./_deprecated/*" ! -path "./venv/*" \
    -exec sed -i.bak 's/from foobara_py\.domain\.domain import Domain/from foobara_py import Domain/g' {} +

# Update Outcome API (be careful with these - may have false positives)
echo "📝 Updating outcome API..."
find . -type f -name "*.py" ! -path "./_deprecated/*" ! -path "./venv/*" \
    -exec sed -i.bak 's/\.success\b/.is_success()/g' {} +

find . -type f -name "*.py" ! -path "./_deprecated/*" ! -path "./venv/*" \
    -exec sed -i.bak 's/\.failure\b/.is_failure()/g' {} +

find . -type f -name "*.py" ! -path "./_deprecated/*" ! -path "./venv/*" \
    -exec sed -i.bak 's/\.value\b/.unwrap()/g' {} +

# Clean up backup files
find . -name "*.py.bak" -delete

echo "✅ Migration complete!"
echo ""
echo "⚠️  IMPORTANT: Review changes before committing:"
echo "   git diff"
echo ""
echo "🧪 Run tests to verify:"
echo "   pytest tests/ -v"
echo ""
echo "🔍 Check for remaining V1 usage:"
echo "   grep -r 'from foobara_py.core.command import' . --include='*.py'"
echo ""
echo "💾 Backup saved to: pre-migration-backup.tar.gz"
```

**Usage:**
```bash
chmod +x migrate_v1_to_v2.sh
./migrate_v1_to_v2.sh
git diff  # Review changes
pytest tests/ -v  # Verify tests pass
```

**⚠️ Warning:** This script uses basic pattern matching and may have false positives. Always review changes before committing!

## Troubleshooting

### Issue: "Module 'foobara_py.core.command' has no attribute 'Command'"

**Solution:** Update import to use public API:
```python
from foobara_py import Command
```

### Issue: "AttributeError: 'CommandOutcome' object has no attribute 'success'"

**Solution:** Use method instead of property:
```python
if outcome.is_success():  # Not outcome.success
    ...
```

### Issue: Deprecation warnings

**Solution:** Find and update the file causing warnings:
```bash
# Enable warnings to see source file
python -W default yourapp.py

# Find V1 imports
grep -r "from foobara_py.core" . --include="*.py"
```

### Issue: Type errors with generics

**Solution:** Add type parameters:
```python
# Before
class MyCommand(Command):
    ...

# After
class MyCommand(Command[MyInputs, MyResult]):
    ...
```

### Issue: Tests failing after migration

**Solution:** Check for:
1. V1 imports in test files
2. `outcome.success` → `outcome.is_success()`
3. `outcome.value` → `outcome.unwrap()`
4. Mock/patch paths updated to new imports

## New Features in V2

After migrating, take advantage of these V2-only features:

### 1. Lifecycle Hooks

```python
class CreateUser(Command[CreateUserInputs, User]):
    def before_execute(self) -> None:
        """Runs before execute(). Errors here prevent execute() from running."""
        if not self.is_authorized():
            self.add_runtime_error('unauthorized', 'Not authorized')

    def execute(self) -> User:
        return User(id=1, name=self.inputs.name)

    def after_execute(self, result: User) -> User:
        """Runs after successful execute()."""
        log_user_creation(result)
        return result
```

### 2. Entity Loading

```python
from foobara_py.persistence import load

class UpdateUser(Command[UpdateUserInputs, User]):
    _loads = [load(User, from_input='user_id', into='user', required=True)]

    def execute(self) -> User:
        # self.user is already loaded and validated!
        self.user.name = self.inputs.name
        return self.user
```

### 3. Transaction Support

```python
from foobara_py import transaction

@transaction
class CreateUserWithProfile(Command[CreateUserInputs, User]):
    def execute(self) -> User:
        user = create_user()
        profile = create_profile(user)
        # Both operations rolled back on error
        return user
```

### 4. Domain Mappers

```python
from foobara_py.domain.mapper import DomainMapper

class UserToDTOMapper(DomainMapper[User, UserDTO]):
    def map(self, user: User) -> UserDTO:
        return UserDTO(id=user.id, name=user.name)

# Use in commands
mapped = self.run_mapped_subcommand(CreateUser, name="John")
```

## Testing Your Migration

### Automated Test

```python
# test_v2_migration.py
from foobara_py import Command
from pydantic import BaseModel

class TestInputs(BaseModel):
    value: int

class TestCommand(Command[TestInputs, int]):
    def execute(self) -> int:
        return self.inputs.value * 2

def test_v2_works():
    """Verify V2 command works correctly"""
    outcome = TestCommand.run(value=5)
    assert outcome.is_success()
    assert outcome.unwrap() == 10

def test_v2_errors():
    """Verify V2 error handling"""
    outcome = TestCommand.run(value="invalid")
    assert outcome.is_failure()
    assert len(outcome.errors) > 0

if __name__ == "__main__":
    test_v2_works()
    test_v2_errors()
    print("✅ V2 migration successful!")
```

### Verification Checklist

```bash
# ✅ 1. No deprecation warnings
python -W default -m pytest tests/ -v | grep -i deprecat

# ✅ 2. No V1 imports
grep -r "from foobara_py.core.command import" . --include="*.py" | grep -v "_deprecated"

# ✅ 3. No V1 outcome API
grep -r "outcome\.success\b" . --include="*.py" | wc -l  # Should be 0
grep -r "outcome\.value\b" . --include="*.py" | wc -l    # Should be 0

# ✅ 4. All tests pass
pytest tests/ -v --cov

# ✅ 5. Type checking (if using mypy)
mypy your_package/ --ignore-missing-imports
```

If all checks pass: **Migration complete!** 🎉

## Getting Help

- **Migration Guide**: See [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) for comprehensive examples
- **Examples**: Check `tests/test_full_parity.py` for V2 patterns
- **Issues**: https://github.com/foobara/foobara-py/issues
- **Discussions**: https://github.com/foobara/foobara-py/discussions
- **Ruby Comparison**: See [PARITY_CHECKLIST.md](../PARITY_CHECKLIST.md)

## Next Steps

1. ✅ Complete migration using this guide
2. 🧪 Test thoroughly in development
3. 📝 Update internal documentation
4. 🚀 Deploy to staging/production
5. 🎯 Explore V2-only features (lifecycle hooks, entity loading, transactions)
6. 📊 Monitor performance improvements (15-25% faster!)

Happy migrating! 🚀
