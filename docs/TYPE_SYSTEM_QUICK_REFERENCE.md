# Type System Quick Reference

## Import Statements

```python
from foobara_py.types import (
    # Core
    FoobaraType,
    TypeRegistry,
    ProcessorProtocol,

    # Base classes
    Caster,
    Validator,
    Transformer,

    # Built-in types
    StringType,
    IntegerType,
    FloatType,
    BooleanType,
    DateType,
    DateTimeType,
    UUIDType,
    EmailType,
    URLType,
    PositiveIntegerType,
    NonNegativeIntegerType,
    PercentageType,
    ArrayType,
    HashType,

    # Casters
    StringCaster,
    IntegerCaster,
    FloatCaster,
    BooleanCaster,
    DateCaster,
    DateTimeCaster,
    UUIDCaster,
    ListCaster,
    DictCaster,

    # Validators
    RequiredValidator,
    MinLengthValidator,
    MaxLengthValidator,
    MinValueValidator,
    MaxValueValidator,
    PatternValidator,
    OneOfValidator,
    EmailValidator,
    URLValidator,
    RangeValidator,
    NotEmptyValidator,
    UniqueItemsValidator,
    ContainsValidator,

    # Transformers
    StripWhitespaceTransformer,
    LowercaseTransformer,
    UppercaseTransformer,
    TitleCaseTransformer,
    RoundTransformer,
    ClampTransformer,
    DefaultTransformer,
    TruncateTransformer,
    SlugifyTransformer,
    NormalizeWhitespaceTransformer,

    # Pydantic types
    EmailAddress,
    PhoneNumber,
    Username,
    PositiveInt,
    NonNegativeInt,
    Percentage,
    ShortStr,
    MediumStr,
    LongStr,

    # Sensitive types
    Sensitive,
    Password,
    APIKey,
    SecretToken,
)
```

## Quick Examples

### Basic Usage

```python
# Process a value
result = EmailType.process("  USER@EXAMPLE.COM  ")
# Returns: "user@example.com"

# Validate without exceptions
is_valid, error = EmailType.validate("invalid")
# Returns: (False, "Invalid email format")

# Check validity
EmailType.is_valid("user@example.com")  # True
```

### Create Custom Type

```python
custom_type = FoobaraType(
    name="username",
    python_type=str,
    casters=[StringCaster()],
    transformers=[LowercaseTransformer()],
    validators=[MinLengthValidator(3)],
    min_length=3,
    max_length=20,
    description="Alphanumeric username"
)
```

### Pydantic Integration

```python
# Create model
fields = {
    'email': EmailType,
    'age': PositiveIntegerType,
}

UserModel = EmailType.create_pydantic_model('User', fields)

# Use model
user = UserModel(email='john@example.com', age='30')
```

### Arrays

```python
# Array of emails
email_list = EmailType.array()
emails = email_list.process(["user1@example.com", "user2@example.com"])
```

### Optional Types

```python
# Optional with default
optional_name = StringType.optional(default="Anonymous")

# Nullable without default
nullable_bio = StringType.optional()
```

### Type Chaining

```python
username = (
    StringType
    .with_transformers(LowercaseTransformer())
    .with_validators(MinLengthValidator(3))
)
```

## Validators Reference

| Validator | Usage | Example |
|-----------|-------|---------|
| `MinLengthValidator(n)` | Min string/list length | `MinLengthValidator(3)` |
| `MaxLengthValidator(n)` | Max string/list length | `MaxLengthValidator(50)` |
| `MinValueValidator(n)` | Min numeric value | `MinValueValidator(0)` |
| `MaxValueValidator(n)` | Max numeric value | `MaxValueValidator(100)` |
| `RangeValidator(min, max)` | Value in range | `RangeValidator(0, 100)` |
| `PatternValidator(regex)` | Regex match | `PatternValidator(r"^\d+$")` |
| `OneOfValidator(list)` | Value in list | `OneOfValidator(['a', 'b'])` |
| `EmailValidator()` | Valid email | `EmailValidator()` |
| `URLValidator()` | Valid URL | `URLValidator()` |
| `NotEmptyValidator()` | Not empty | `NotEmptyValidator()` |
| `UniqueItemsValidator()` | Unique list items | `UniqueItemsValidator()` |
| `ContainsValidator(s)` | Contains substring | `ContainsValidator('@')` |

## Transformers Reference

| Transformer | Usage | Example |
|-------------|-------|---------|
| `StripWhitespaceTransformer()` | Strip whitespace | `"  hi  "` → `"hi"` |
| `LowercaseTransformer()` | Convert to lowercase | `"HI"` → `"hi"` |
| `UppercaseTransformer()` | Convert to uppercase | `"hi"` → `"HI"` |
| `TitleCaseTransformer()` | Convert to title case | `"hi"` → `"Hi"` |
| `RoundTransformer(n)` | Round to n decimals | `3.14159` → `3.14` |
| `ClampTransformer(min, max)` | Clamp to range | `-10` → `0` (min=0) |
| `DefaultTransformer(val)` | Replace None/empty | `None` → `"default"` |
| `TruncateTransformer(n)` | Truncate to length | `"hello"` → `"he..."` |
| `SlugifyTransformer()` | Create URL slug | `"Hello!"` → `"hello"` |
| `NormalizeWhitespaceTransformer()` | Normalize spaces | `"a  b"` → `"a b"` |

## Casters Reference

| Caster | From | To | Example |
|--------|------|-----|---------|
| `StringCaster()` | Any | str | `123` → `"123"` |
| `IntegerCaster()` | str/float/bool | int | `"42"` → `42` |
| `FloatCaster()` | str/int | float | `"3.14"` → `3.14` |
| `BooleanCaster()` | str/int | bool | `"yes"` → `True` |
| `DateCaster()` | str/datetime | date | `"2024-01-15"` → date |
| `DateTimeCaster()` | str/date/int | datetime | `"2024-01-15"` → datetime |
| `UUIDCaster()` | str | UUID | `"..."` → UUID |
| `ListCaster()` | str/tuple/set | list | `"a,b"` → `["a", "b"]` |
| `DictCaster()` | BaseModel/object | dict | object → dict |

## Pipeline Order

```
Input Value
    ↓
1. Handle None/Default
    ↓
2. Casters (type conversion)
    ↓
3. Transformers (normalization)
    ↓
4. Nested Types (if array/dict)
    ↓
5. Validators (constraint checking)
    ↓
Output Value
```

## Common Patterns

### Email Processing
```python
email_type = FoobaraType(
    name="email",
    python_type=str,
    casters=[StringCaster()],
    transformers=[StripWhitespaceTransformer(), LowercaseTransformer()],
    validators=[EmailValidator()]
)
```

### Bounded Number
```python
score_type = FoobaraType(
    name="score",
    python_type=int,
    casters=[IntegerCaster()],
    validators=[RangeValidator(0, 100)]
)
```

### URL Slug
```python
slug_type = FoobaraType(
    name="slug",
    python_type=str,
    transformers=[SlugifyTransformer()]
)
```

### Required Non-Empty String
```python
required_string = FoobaraType(
    name="required",
    python_type=str,
    validators=[NotEmptyValidator()]
)
```

### Clamped Float
```python
normalized = FoobaraType(
    name="normalized",
    python_type=float,
    transformers=[ClampTransformer(0.0, 1.0)]
)
```

## Error Handling

```python
try:
    result = custom_type.process(value)
except TypeError as e:
    # Casting failed
    print(f"Type error: {e}")
except ValueError as e:
    # Validation failed
    print(f"Validation error: {e}")

# Or use validate() for non-exception handling
is_valid, error = custom_type.validate(value)
if not is_valid:
    print(f"Invalid: {error}")
```

## Type Registry

```python
# Register
TypeRegistry.register(custom_type, category="custom")

# Retrieve
my_type = TypeRegistry.get("custom_type")

# List all
all_types = TypeRegistry.list_all()

# By category
string_types = TypeRegistry.by_category("string")
```

## Pydantic Models

### Generate Model
```python
UserModel = StringType.create_pydantic_model('User', {
    'email': EmailType,
    'age': PositiveIntegerType,
})
```

### Convert to Field
```python
field_type, field_obj = EmailType.to_pydantic_field()
```

### Create Validator
```python
validator_func = EmailType.to_pydantic_validator()
```

## Custom Processors

### Custom Caster
```python
class MyCaster(Caster[float]):
    def process(self, value: Any) -> float:
        # Your logic
        return float(value)
```

### Custom Validator
```python
class MyValidator(Validator[int]):
    def process(self, value: int) -> int:
        if value < 0:
            raise ValueError("Must be positive")
        return value
```

### Custom Transformer
```python
class MyTransformer(Transformer[str]):
    def process(self, value: str) -> str:
        return value.upper()
```

### Duck Typing (No Inheritance)
```python
class MyProcessor:
    def process(self, value: Any) -> str:
        return str(value)

    def __call__(self, value: Any) -> str:
        return self.process(value)
```

## Tips & Tricks

1. **Reuse types**: Define once, use everywhere
2. **Chain modifications**: Use `.with_validators()` and `.with_transformers()`
3. **Transform before validate**: Always normalize input before validation
4. **Use built-ins**: Prefer built-in processors over custom ones
5. **Add descriptions**: Document your types
6. **Leverage Pydantic**: Use models for complex structures
7. **Test your types**: Write unit tests for custom types
8. **Use type hints**: Enable IDE autocomplete and mypy checking
