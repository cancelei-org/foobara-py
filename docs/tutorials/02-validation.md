# Tutorial 2: Input Validation

**Time:** 20 minutes | **Difficulty:** Beginner | **[Previous](./01-basic-command.md)** | **[Next](./03-error-handling.md)**

## Learning Objectives

- Use Pydantic field constraints
- Create custom validators
- Handle validation errors gracefully
- Test validation logic

## What We'll Build

A user registration command with comprehensive validation.

## Complete Tutorial

Coming soon! This tutorial will cover:

1. Field-level validation with Pydantic
2. Custom validators with `@field_validator`
3. Cross-field validation
4. Handling validation errors
5. Testing validation scenarios

For now, see:
- [Type System Guide](../TYPE_SYSTEM_GUIDE.md)
- [Getting Started - Input Validation](../GETTING_STARTED.md#using-the-type-system)

## Quick Example

```python
from pydantic import BaseModel, Field, EmailStr, field_validator

class RegisterUserInputs(BaseModel):
    username: str = Field(min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8)
    age: int = Field(ge=18, le=150)
    
    @field_validator('password')
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v
```

**[Next: Tutorial 3 - Error Handling](./03-error-handling.md)**
