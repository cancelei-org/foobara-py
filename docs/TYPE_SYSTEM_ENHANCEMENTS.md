# Type System Enhancements - Summary

This document summarizes the enhancements made to the Foobara Python type system, focusing on improved type safety, Pydantic integration, and developer experience.

## Overview

The type system has been enhanced with:

1. **Improved Type Declarations** with Python 3.10+ features
2. **Protocol-based Design** for better duck typing
3. **Enhanced Pydantic Integration** with automatic model generation
4. **New Validators and Transformers** for common use cases
5. **Better Type Hints** throughout the codebase
6. **Comprehensive Documentation** and examples

## Key Enhancements

### 1. Protocol-based Design

**Before:**
```python
# Had to inherit from TypeProcessor
class MyProcessor(TypeProcessor[str]):
    def process(self, value: Any) -> str:
        return str(value).upper()
```

**After:**
```python
# Duck typing with ProcessorProtocol - no inheritance needed
class MyProcessor:
    def process(self, value: Any) -> str:
        return str(value).upper()

    def __call__(self, value: Any) -> str:
        return self.process(value)

# Works automatically with FoobaraType
```

**Benefits:**
- Less boilerplate code
- More flexible integration
- Better support for third-party processors

### 2. Pydantic Model Generation

**New Feature:**
```python
from foobara_py.types import EmailType, PositiveIntegerType, StringType

# Define fields using FoobaraTypes
fields = {
    'email': EmailType,
    'age': PositiveIntegerType,
    'name': StringType,
}

# Automatically create Pydantic model
UserModel = StringType.create_pydantic_model('User', fields)

# Use the model with automatic validation
user = UserModel(
    email='  JOHN@EXAMPLE.COM  ',  # Auto-normalized
    age='30',  # Auto-cast to int
    name='John Doe'
)

print(user.email)  # Output: "john@example.com"
```

**Key Methods:**
- `to_pydantic_field()` - Convert FoobaraType to Pydantic Field
- `to_pydantic_validator()` - Create Pydantic validator function
- `create_pydantic_model()` - Generate complete Pydantic models

**Benefits:**
- Automatic validation using FoobaraType processors
- Seamless integration with FastAPI and other Pydantic-based frameworks
- Type-safe serialization/deserialization
- Reduced boilerplate for model creation

### 3. Enhanced Type Hints

**Improvements:**
```python
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    Type,
    Union,
    runtime_checkable,
)

# Updated type annotations throughout
def __init__(
    self,
    name: str,
    python_type: Type[T],
    *,
    casters: Optional[List[Caster]] = None,
    validators: Optional[List[Validator]] = None,
    transformers: Optional[List[Transformer]] = None,
    # ... more parameters
)
```

**Benefits:**
- Better IDE autocomplete
- Improved mypy type checking
- Clearer API documentation
- Reduced runtime errors

### 4. New Validators

#### RangeValidator
```python
validator = RangeValidator(0, 100)
validator.process(50)   # OK
validator.process(150)  # ValueError
```

#### NotEmptyValidator
```python
validator = NotEmptyValidator()
validator.process("hello")  # OK
validator.process("")       # ValueError
validator.process([1, 2])   # OK
validator.process([])       # ValueError
```

#### UniqueItemsValidator
```python
validator = UniqueItemsValidator()
validator.process([1, 2, 3])  # OK
validator.process([1, 2, 2])  # ValueError
```

#### ContainsValidator
```python
validator = ContainsValidator("@", case_sensitive=False)
validator.process("user@example.com")  # OK
validator.process("username")  # ValueError
```

### 5. New Transformers

#### ClampTransformer
```python
transformer = ClampTransformer(0, 100)
transformer.process(-10)  # Returns: 0
transformer.process(150)  # Returns: 100
transformer.process(50)   # Returns: 50
```

#### DefaultTransformer
```python
transformer = DefaultTransformer("unknown", replace_empty=True)
transformer.process(None)  # Returns: "unknown"
transformer.process("")    # Returns: "unknown"
transformer.process("val") # Returns: "val"
```

#### TruncateTransformer
```python
transformer = TruncateTransformer(10, suffix="...")
transformer.process("Hello World!")  # Returns: "Hello W..."
```

#### SlugifyTransformer
```python
transformer = SlugifyTransformer()
transformer.process("Hello World!")  # Returns: "hello-world"
transformer.process("Product #123")  # Returns: "product-123"
```

#### NormalizeWhitespaceTransformer
```python
transformer = NormalizeWhitespaceTransformer()
transformer.process("hello    world")  # Returns: "hello world"
```

### 6. Pydantic Field Constraints

**New FoobaraType Parameters:**
```python
age_type = FoobaraType(
    name="age",
    python_type=int,
    ge=0,          # Greater than or equal (Pydantic)
    le=150,        # Less than or equal (Pydantic)
    description="Person's age",
    examples=[25, 30, 45]
)

username_type = FoobaraType(
    name="username",
    python_type=str,
    min_length=3,  # Minimum length (Pydantic)
    max_length=20, # Maximum length (Pydantic)
    pattern=r"^[a-zA-Z0-9_]+$",  # Regex pattern (Pydantic)
)
```

**Benefits:**
- Direct Pydantic constraint support
- Automatic OpenAPI schema generation
- Better integration with FastAPI

## Migration Guide

### Updating Existing Code

#### 1. No Changes Needed

Existing code continues to work without modifications:

```python
# This still works exactly as before
from foobara_py.types import EmailType

email = EmailType.process("  USER@EXAMPLE.COM  ")
# Returns: "user@example.com"
```

#### 2. Optional: Use New Pydantic Integration

If you want to leverage Pydantic models:

```python
# Old approach: Manual model definition
from pydantic import BaseModel, EmailStr

class User(BaseModel):
    email: EmailStr
    age: int
    name: str

# New approach: Automatic generation from FoobaraTypes
from foobara_py.types import EmailType, PositiveIntegerType, StringType

UserModel = EmailType.create_pydantic_model('User', {
    'email': EmailType,
    'age': PositiveIntegerType,
    'name': StringType,
})
```

#### 3. Optional: Use New Validators/Transformers

Replace custom implementations with built-ins:

```python
# Old: Custom implementation
class MyRangeValidator(Validator[int]):
    def process(self, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("Out of range")
        return value

# New: Use built-in
from foobara_py.types import RangeValidator

validator = RangeValidator(0, 100)
```

#### 4. Optional: Add Pydantic Constraints

Enhance existing types with Pydantic constraints:

```python
# Old
age_type = FoobaraType(
    name="age",
    python_type=int,
    validators=[MinValueValidator(0), MaxValueValidator(150)]
)

# New: Add Pydantic constraints for better integration
age_type = FoobaraType(
    name="age",
    python_type=int,
    validators=[MinValueValidator(0), MaxValueValidator(150)],
    ge=0,   # Pydantic constraint
    le=150, # Pydantic constraint
    description="Person's age in years",
    examples=[25, 30, 45]
)
```

## Testing

### Running Tests

All existing tests pass without modification:

```bash
# Run type declaration tests
pytest tests/test_type_declarations.py -v

# Run sensitive types tests
pytest tests/test_sensitive_types.py -v

# Run comprehensive type system tests
pytest tests/test_type_system_comprehensive.py -v

# Run new Pydantic integration tests
pytest tests/test_pydantic_integration.py -v

# Run enhanced processors tests
pytest tests/test_enhanced_processors.py -v
```

### Test Coverage

New test files added:

1. **test_pydantic_integration.py**
   - Pydantic Field generation
   - Model creation from FoobaraTypes
   - Validator integration
   - Runtime type checking
   - Serialization edge cases

2. **test_enhanced_processors.py**
   - New validators (RangeValidator, NotEmptyValidator, etc.)
   - New transformers (ClampTransformer, SlugifyTransformer, etc.)
   - Edge cases and complex usage patterns

## Performance Considerations

### Impact

- **Minimal overhead**: New features don't affect existing code performance
- **Lazy evaluation**: Pydantic models are only created when needed
- **Caching**: Type processors are reused, not recreated

### Benchmarks

The processing pipeline performance remains the same:

```python
# Before and After - same performance
email = EmailType.process("  USER@EXAMPLE.COM  ")
```

Pydantic model creation is a one-time cost:

```python
# One-time cost
UserModel = EmailType.create_pydantic_model('User', fields)

# Subsequent validations are fast
user1 = UserModel(**data1)  # Fast
user2 = UserModel(**data2)  # Fast
```

## Best Practices

### 1. Use Built-in Validators/Transformers

Prefer built-in processors over custom ones when possible:

```python
# Good
from foobara_py.types import RangeValidator, SlugifyTransformer

# Less Good - custom implementation
class MyRangeValidator(Validator[int]):
    # ... custom implementation
```

### 2. Leverage Pydantic Integration

Use Pydantic models for complex data structures:

```python
# Good - Automatic validation
fields = {
    'email': EmailType,
    'age': PositiveIntegerType,
}
UserModel = EmailType.create_pydantic_model('User', fields)

# Less Good - Manual validation
def validate_user(data):
    email = EmailType.process(data['email'])
    age = PositiveIntegerType.process(data['age'])
    return {'email': email, 'age': age}
```

### 3. Add Type Hints Everywhere

Use proper type hints for better IDE support:

```python
from typing import Optional
from foobara_py.types import FoobaraType

def process_email(email: str) -> str:
    """Process email with type safety"""
    return EmailType.process(email)
```

### 4. Document Custom Types

Always add descriptions:

```python
custom_type = FoobaraType(
    name="product_code",
    python_type=str,
    pattern=r"^[A-Z]{3}\d{6}$",
    description="Product code in format ABC123456"
)
```

## Future Enhancements

Potential future improvements:

1. **AsyncIO Support**: Async validators and transformers
2. **Type Composition**: Union types and conditional validation
3. **Custom Error Messages**: Per-validator error message customization
4. **Type Inference**: Automatic type detection from examples
5. **Performance Optimization**: Compiled validators for high-throughput scenarios

## References

- [Type System Guide](./TYPE_SYSTEM_GUIDE.md) - Complete guide with examples
- [Pydantic Documentation](https://docs.pydantic.dev/) - Pydantic v2 docs
- [Python Type Hints](https://docs.python.org/3/library/typing.html) - Python typing module
- [Foobara Ruby](https://github.com/foobara/foobara) - Original Ruby implementation

## Support

For questions or issues:

1. Check the [Type System Guide](./TYPE_SYSTEM_GUIDE.md)
2. Review test files for examples
3. Open an issue on GitHub
4. Consult the Foobara community

## Changelog

### Version 0.2.0

**Added:**
- `ProcessorProtocol` for duck typing
- `to_pydantic_field()` method on FoobaraType
- `to_pydantic_validator()` method on FoobaraType
- `create_pydantic_model()` static method
- New validators: `RangeValidator`, `NotEmptyValidator`, `UniqueItemsValidator`, `ContainsValidator`
- New transformers: `ClampTransformer`, `DefaultTransformer`, `TruncateTransformer`, `SlugifyTransformer`, `NormalizeWhitespaceTransformer`
- Pydantic field constraints: `ge`, `le`, `gt`, `lt`, `min_length`, `max_length`, `pattern`, `examples`
- Improved type hints using Python 3.10+ features

**Changed:**
- Enhanced type annotations throughout codebase
- Better documentation for all processors
- Improved error messages

**Fixed:**
- Type hint consistency
- Optional parameter handling in Pydantic fields

**Backward Compatible:**
- All existing code continues to work without changes
- New features are opt-in
