# Foobara Type System Guide

## Overview

The Foobara type system provides a powerful and flexible way to define, validate, and transform data in Python. It combines the best of Ruby Foobara's type processors with Python's type system and Pydantic's validation framework.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Type Declarations](#type-declarations)
- [Processors](#processors)
- [Pydantic Integration](#pydantic-integration)
- [Built-in Types](#built-in-types)
- [Advanced Usage](#advanced-usage)
- [Best Practices](#best-practices)

## Core Concepts

### FoobaraType

`FoobaraType` is the central class for defining types with processing pipelines. Each type can have:

- **Casters**: Convert values from one type to another
- **Transformers**: Modify values (normalize, clean, format)
- **Validators**: Ensure values meet constraints

### Processing Pipeline

The pipeline executes in this order:

1. **Handle None/Default**: Check for None values and apply defaults
2. **Casters**: Convert the value to the target type
3. **Transformers**: Normalize/modify the value
4. **Nested Types**: Process array elements or dict key/values
5. **Validators**: Verify the value meets all constraints

```python
from foobara_py.types import (
    FoobaraType,
    StringCaster,
    EmailValidator,
    StripWhitespaceTransformer,
    LowercaseTransformer,
)

email_type = FoobaraType(
    name="email",
    python_type=str,
    casters=[StringCaster()],
    transformers=[StripWhitespaceTransformer(), LowercaseTransformer()],
    validators=[EmailValidator()]
)

# Process a value through the pipeline
result = email_type.process("  USER@EXAMPLE.COM  ")
# Returns: "user@example.com"
```

## Type Declarations

### Basic Type Declaration

```python
from foobara_py.types import type_declaration, PatternValidator

phone_type = type_declaration(
    "phone_number",
    validate=[PatternValidator(r"^\+?[0-9]{10,15}$")],
    description="International phone number",
    register=True  # Register in TypeRegistry
)
```

### Type with Constraints

```python
from foobara_py.types import (
    FoobaraType,
    IntegerCaster,
    MinValueValidator,
    MaxValueValidator,
)

age_type = FoobaraType(
    name="age",
    python_type=int,
    casters=[IntegerCaster()],
    validators=[
        MinValueValidator(0),
        MaxValueValidator(150)
    ],
    description="Person's age in years",
    ge=0,  # Pydantic constraint
    le=150  # Pydantic constraint
)
```

### Optional and Nullable Types

```python
from foobara_py.types import StringType

# Optional with default
optional_name = StringType.optional(default="Anonymous")

# Nullable without default
nullable_bio = StringType.optional()

# Usage
optional_name.process(None)  # Returns: "Anonymous"
nullable_bio.process(None)   # Returns: None
```

## Processors

### Casters

Casters convert values from one type to another:

```python
from foobara_py.types import (
    StringCaster,
    IntegerCaster,
    FloatCaster,
    BooleanCaster,
    DateCaster,
    ListCaster,
)

# String to integer
int_caster = IntegerCaster()
int_caster.process("42")  # Returns: 42

# String to boolean
bool_caster = BooleanCaster()
bool_caster.process("yes")  # Returns: True

# Comma-separated string to list
list_caster = ListCaster()
list_caster.process("a,b,c")  # Returns: ["a", "b", "c"]
```

### Validators

Validators ensure values meet constraints:

```python
from foobara_py.types import (
    MinLengthValidator,
    MaxLengthValidator,
    MinValueValidator,
    MaxValueValidator,
    PatternValidator,
    OneOfValidator,
    EmailValidator,
    RangeValidator,
    NotEmptyValidator,
    UniqueItemsValidator,
    ContainsValidator,
)

# String length validation
min_length = MinLengthValidator(3)
max_length = MaxLengthValidator(50)

# Numeric range validation
range_val = RangeValidator(0, 100)
range_val.process(50)   # OK
range_val.process(150)  # ValueError

# Non-empty validation
not_empty = NotEmptyValidator()
not_empty.process("hello")  # OK
not_empty.process("")       # ValueError

# Unique items in list
unique = UniqueItemsValidator()
unique.process([1, 2, 3])  # OK
unique.process([1, 2, 2])  # ValueError

# Contains substring
contains = ContainsValidator("@", case_sensitive=False)
contains.process("user@example.com")  # OK
contains.process("username")  # ValueError
```

### Transformers

Transformers modify values:

```python
from foobara_py.types import (
    StripWhitespaceTransformer,
    LowercaseTransformer,
    UppercaseTransformer,
    RoundTransformer,
    ClampTransformer,
    DefaultTransformer,
    TruncateTransformer,
    SlugifyTransformer,
    NormalizeWhitespaceTransformer,
)

# Clamp numeric values to range
clamp = ClampTransformer(0, 100)
clamp.process(-10)  # Returns: 0
clamp.process(150)  # Returns: 100

# Default for None/empty values
default = DefaultTransformer("unknown")
default.process(None)  # Returns: "unknown"
default.process("")    # Returns: "unknown"

# Truncate string with suffix
truncate = TruncateTransformer(10, suffix="...")
truncate.process("Hello World!")  # Returns: "Hello W..."

# Create URL slug
slugify = SlugifyTransformer()
slugify.process("Hello World!")  # Returns: "hello-world"

# Normalize whitespace
normalize = NormalizeWhitespaceTransformer()
normalize.process("hello    world")  # Returns: "hello world"
```

### Custom Processors

Create custom processors by inheriting from base classes:

```python
from foobara_py.types import Caster, Validator, Transformer
from typing import Any

class CurrencyCaster(Caster[float]):
    """Cast currency strings to float"""
    def process(self, value: Any) -> float:
        if isinstance(value, str):
            # Remove currency symbols and commas
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)

class EvenValidator(Validator[int]):
    """Validate number is even"""
    def process(self, value: int) -> int:
        if value % 2 != 0:
            raise ValueError("Value must be even")
        return value

class DoubleTransformer(Transformer[int]):
    """Double the value"""
    def process(self, value: int) -> int:
        return value * 2

# Use custom processors
money_type = FoobaraType(
    name="money",
    python_type=float,
    casters=[CurrencyCaster()],
    validators=[MinValueValidator(0.0)]
)

result = money_type.process("$1,234.56")  # Returns: 1234.56
```

### Duck Typing with ProcessorProtocol

You can also create processors without inheritance using the `ProcessorProtocol`:

```python
class MyProcessor:
    """Any class with a process method works"""
    def process(self, value: Any) -> str:
        return str(value).upper()

    def __call__(self, value: Any) -> str:
        return self.process(value)

# Works with FoobaraType automatically
custom_type = FoobaraType(
    name="upper",
    python_type=str,
    casters=[MyProcessor()]
)
```

## Pydantic Integration

### Converting Types to Pydantic Fields

```python
from foobara_py.types import EmailType

# Convert FoobaraType to Pydantic Field
field_type, field_obj = EmailType.to_pydantic_field()

# Use in Pydantic model manually
from pydantic import BaseModel

class User(BaseModel):
    email: field_type = field_obj
```

### Automatic Model Generation

```python
from foobara_py.types import (
    EmailType,
    PositiveIntegerType,
    StringType,
)

# Define fields using FoobaraTypes
fields = {
    'email': EmailType,
    'age': PositiveIntegerType,
    'name': StringType,
}

# Create Pydantic model automatically
UserModel = StringType.create_pydantic_model('User', fields)

# Use the model
user = UserModel(
    email='  JOHN@EXAMPLE.COM  ',  # Will be normalized
    age='30',  # Will be cast to int
    name='John Doe'
)

print(user.email)  # Output: "john@example.com"
print(user.age)    # Output: 30
```

### Field Validators

```python
from pydantic import field_validator

# Get validator function from FoobaraType
email_validator = EmailType.to_pydantic_validator()

class User(BaseModel):
    email: str

    # Apply FoobaraType validation
    _validate_email = field_validator('email')(email_validator)
```

### Pydantic Field Constraints

FoobaraType supports Pydantic field constraints directly:

```python
from foobara_py.types import FoobaraType, IntegerCaster

age_type = FoobaraType(
    name="age",
    python_type=int,
    casters=[IntegerCaster()],
    description="Person's age",
    ge=0,        # Greater than or equal
    le=150,      # Less than or equal
    examples=[25, 30, 45]  # Example values
)

username_type = FoobaraType(
    name="username",
    python_type=str,
    min_length=3,
    max_length=20,
    pattern=r"^[a-zA-Z0-9_]+$",
    description="Alphanumeric username"
)
```

## Built-in Types

### Primitive Types

```python
from foobara_py.types import (
    StringType,
    IntegerType,
    FloatType,
    BooleanType,
    DateType,
    DateTimeType,
    UUIDType,
)

# Use directly
name = StringType.process("  John  ")  # Returns: "John" (stripped)
age = IntegerType.process("42")  # Returns: 42
price = FloatType.process("19.99")  # Returns: 19.99
active = BooleanType.process("yes")  # Returns: True
```

### String Types

```python
from foobara_py.types import (
    EmailType,
    URLType,
)

email = EmailType.process("  USER@EXAMPLE.COM  ")
# Returns: "user@example.com"

url = URLType.process("  https://example.com  ")
# Returns: "https://example.com"
```

### Numeric Types

```python
from foobara_py.types import (
    PositiveIntegerType,
    NonNegativeIntegerType,
    PercentageType,
)

positive = PositiveIntegerType.process("5")  # OK
positive = PositiveIntegerType.process("0")  # ValueError (must be >= 1)

non_negative = NonNegativeIntegerType.process("0")  # OK

percentage = PercentageType.process("50.5")  # OK (0-100)
```

### Container Types

```python
from foobara_py.types import ArrayType, HashType

# Array (list)
tags = ArrayType.process("tag1,tag2,tag3")
# Returns: ["tag1", "tag2", "tag3"]

# Hash (dict)
data = HashType.process({"key": "value"})
# Returns: {"key": "value"}
```

### Pydantic Type Aliases

```python
from foobara_py.types import (
    EmailAddress,
    PhoneNumber,
    Username,
    PositiveInt,
    NonNegativeInt,
    Percentage,
    ShortStr,
    MediumStr,
    LongStr,
)

from pydantic import BaseModel

class User(BaseModel):
    email: EmailAddress
    phone: PhoneNumber
    username: Username
    age: PositiveInt
    score: Percentage
    bio: LongStr
```

## Advanced Usage

### Array of Custom Types

```python
from foobara_py.types import EmailType

# Create array of emails
email_list_type = EmailType.array()

emails = email_list_type.process([
    "  USER1@EXAMPLE.COM  ",
    "  USER2@EXAMPLE.COM  "
])
# Returns: ["user1@example.com", "user2@example.com"]
```

### Chaining Type Modifications

```python
from foobara_py.types import (
    StringType,
    MinLengthValidator,
    LowercaseTransformer,
)

# Start with base type and chain modifications
username_type = (
    StringType
    .with_transformers(LowercaseTransformer())
    .with_validators(MinLengthValidator(3))
)

result = username_type.process("  JOHN  ")
# Returns: "john"
```

### Type Registry

```python
from foobara_py.types import TypeRegistry, type_declaration

# Register a custom type
custom_type = type_declaration(
    "slug",
    python_type=str,
    transform=[SlugifyTransformer()],
    register=True,  # Add to registry
    category="string"
)

# Retrieve from registry
slug_type = TypeRegistry.get("slug")

# List all types
all_types = TypeRegistry.list_all()

# Get types by category
string_types = TypeRegistry.by_category("string")
```

### Nested Type Validation

```python
from foobara_py.types import FoobaraType, IntegerType, StringType

# Define value type for dict
int_type = IntegerType
str_type = StringType

# Create dict type with typed keys and values
scores_type = FoobaraType(
    name="scores",
    python_type=dict,
    key_type=str_type,
    value_type=int_type
)

result = scores_type.process({
    "math": "95",
    "english": "87"
})
# Returns: {"math": 95, "english": 87}
```

### Complex Processing Pipeline

```python
from foobara_py.types import (
    FoobaraType,
    StringCaster,
    SlugifyTransformer,
    TruncateTransformer,
    NotEmptyValidator,
)

# Create a type for short URL slugs
short_slug_type = FoobaraType(
    name="short_slug",
    python_type=str,
    casters=[StringCaster()],
    transformers=[
        SlugifyTransformer(),
        TruncateTransformer(20, suffix="")
    ],
    validators=[NotEmptyValidator()],
    description="Short URL-safe slug (max 20 chars)"
)

result = short_slug_type.process("This Is A Very Long Product Title!")
# Returns: "this-is-a-very-long" (slugified and truncated)
```

## Best Practices

### 1. Type Reusability

Define types once and reuse them:

```python
# Define once
from foobara_py.types import EmailType

# Use everywhere
user_email = EmailType.process(user_input)
contact_email = EmailType.process(contact_input)
```

### 2. Composition Over Inheritance

Build complex types by composing simple ones:

```python
# Base types
email_type = EmailType
age_type = PositiveIntegerType

# Compose into model
fields = {
    'email': email_type,
    'age': age_type,
}

UserModel = email_type.create_pydantic_model('User', fields)
```

### 3. Transformers Before Validators

Always apply transformers before validators to normalize input:

```python
# Good: Transform then validate
good_type = FoobaraType(
    name="email",
    python_type=str,
    transformers=[LowercaseTransformer()],  # Normalize first
    validators=[EmailValidator()]  # Then validate
)

# Bad: Validate before transform
# Email might fail validation due to uppercase
```

### 4. Use Type Hints

Leverage Python's type system with FoobaraType:

```python
from typing import Optional
from foobara_py.types import FoobaraType

def process_email(email: str) -> str:
    """Process email using type system"""
    return EmailType.process(email)

def get_user_age(age_str: Optional[str]) -> int:
    """Convert age string to int with validation"""
    return PositiveIntegerType.process(age_str)
```

### 5. Clear Error Messages

Provide helpful error messages in custom validators:

```python
class AgeValidator(Validator[int]):
    def process(self, value: int) -> int:
        if value < 18:
            raise ValueError(
                f"Age must be at least 18. Got: {value}"
            )
        return value
```

### 6. Document Custom Types

Always add descriptions to custom types:

```python
custom_type = FoobaraType(
    name="employee_id",
    python_type=str,
    pattern=r"^EMP\d{6}$",
    description="Employee ID in format EMP######"
)
```

### 7. Leverage Pydantic Integration

Use Pydantic models for complex data structures:

```python
# Better than manually validating each field
fields = {
    'email': EmailType,
    'age': PositiveIntegerType,
    'phone': PhoneType,
    'address': AddressType,
}

UserModel = StringType.create_pydantic_model('User', fields)

# Validates all fields at once
user = UserModel(**user_data)
```

### 8. Test Your Types

Write tests for custom types:

```python
def test_custom_type():
    result = custom_type.process(valid_input)
    assert result == expected_output

    with pytest.raises(ValueError):
        custom_type.process(invalid_input)
```

## Examples

### Example 1: User Registration

```python
from foobara_py.types import (
    EmailType,
    FoobaraType,
    StringCaster,
    MinLengthValidator,
    PatternValidator,
    PositiveIntegerType,
)

# Define types
email_type = EmailType

password_type = FoobaraType(
    name="password",
    python_type=str,
    casters=[StringCaster()],
    validators=[MinLengthValidator(8)],
    description="Password (min 8 characters)"
)

username_type = FoobaraType(
    name="username",
    python_type=str,
    min_length=3,
    max_length=20,
    pattern=r"^[a-zA-Z0-9_]+$"
)

# Create model
fields = {
    'email': email_type,
    'password': password_type,
    'username': username_type,
    'age': PositiveIntegerType.optional(),
}

RegistrationModel = email_type.create_pydantic_model(
    'Registration',
    fields
)

# Use it
registration = RegistrationModel(
    email='user@example.com',
    password='secretpass123',
    username='john_doe',
    age='25'
)
```

### Example 2: Product Catalog

```python
from foobara_py.types import (
    FoobaraType,
    StringType,
    PositiveIntegerType,
    FloatCaster,
    MinValueValidator,
    SlugifyTransformer,
)

# Product SKU
sku_type = FoobaraType(
    name="sku",
    python_type=str,
    pattern=r"^[A-Z]{3}\d{6}$",
    description="Product SKU (ABC123456)"
)

# Product name -> slug
slug_type = FoobaraType(
    name="slug",
    python_type=str,
    transformers=[SlugifyTransformer()]
)

# Price
price_type = FoobaraType(
    name="price",
    python_type=float,
    casters=[FloatCaster()],
    validators=[MinValueValidator(0.01)],
    ge=0.01,
    description="Price in USD"
)

# Quantity
quantity_type = PositiveIntegerType

# Build model
ProductModel = StringType.create_pydantic_model('Product', {
    'sku': sku_type,
    'name': StringType,
    'slug': slug_type,
    'price': price_type,
    'quantity': quantity_type,
})

# Create product
product = ProductModel(
    sku='ABC123456',
    name='Awesome Product',
    slug='Awesome Product',  # Will be slugified
    price='29.99',
    quantity='100'
)

print(product.slug)  # Output: "awesome-product"
```

### Example 3: API Configuration

```python
from foobara_py.types import (
    FoobaraType,
    URLType,
    PositiveIntegerType,
    OneOfValidator,
)

api_url_type = URLType

timeout_type = FoobaraType(
    name="timeout",
    python_type=int,
    ge=1,
    le=300,
    description="Timeout in seconds (1-300)"
)

env_type = FoobaraType(
    name="environment",
    python_type=str,
    validators=[OneOfValidator(['dev', 'staging', 'prod'])],
    default='dev',
    has_default=True
)

ConfigModel = URLType.create_pydantic_model('APIConfig', {
    'base_url': api_url_type,
    'timeout': timeout_type,
    'environment': env_type,
    'max_retries': PositiveIntegerType.optional(default=3),
})

config = ConfigModel(
    base_url='https://api.example.com',
    timeout='30',
    environment='prod'
)
```

## Summary

The Foobara type system provides:

- **Flexible type definitions** with casters, validators, and transformers
- **Seamless Pydantic integration** for model generation
- **Protocol-based design** for duck typing
- **Rich built-in types** for common use cases
- **Composable and reusable** type components
- **Clear error messages** for validation failures

Use it to build robust, type-safe Python applications with automatic validation and transformation.
