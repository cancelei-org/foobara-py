"""
Base type extensions for foobara-py

Provides common custom types built on Pydantic's Annotated pattern,
similar to Foobara's type processors.
"""

import re
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field

# Numeric types
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
Percentage = Annotated[float, Field(ge=0, le=100)]


# String validators
def _validate_email(v: str) -> str:
    """Validate email format"""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(pattern, v):
        raise ValueError("Invalid email format")
    return v.lower()


def _validate_username(v: str) -> str:
    """Validate username format"""
    pattern = r"^[a-zA-Z0-9_]{3,30}$"
    if not re.match(pattern, v):
        raise ValueError("Username must be 3-30 alphanumeric characters or underscores")
    return v


def _validate_phone(v: str) -> str:
    """Validate phone number format"""
    # Remove common formatting
    cleaned = re.sub(r"[\s\-\(\)\.]", "", v)
    if not re.match(r"^\+?[0-9]{10,15}$", cleaned):
        raise ValueError("Invalid phone number format")
    return cleaned


def _strip_whitespace(v: str) -> str:
    """Strip whitespace from string"""
    return v.strip() if isinstance(v, str) else v


def _to_lowercase(v: str) -> str:
    """Convert to lowercase"""
    return v.lower() if isinstance(v, str) else v


def _to_title_case(v: str) -> str:
    """Convert to title case"""
    return v.title() if isinstance(v, str) else v


# String types with validation
EmailAddress = Annotated[str, BeforeValidator(_strip_whitespace), AfterValidator(_validate_email)]

Username = Annotated[str, BeforeValidator(_strip_whitespace), AfterValidator(_validate_username)]

PhoneNumber = Annotated[str, BeforeValidator(_strip_whitespace), AfterValidator(_validate_phone)]

NonEmptyStr = Annotated[str, BeforeValidator(_strip_whitespace), Field(min_length=1)]

TitleCaseStr = Annotated[str, BeforeValidator(_strip_whitespace), AfterValidator(_to_title_case)]

LowercaseStr = Annotated[str, BeforeValidator(_strip_whitespace), AfterValidator(_to_lowercase)]


# Bounded strings
def string_length(min_len: int = None, max_len: int = None):
    """Create bounded string type"""
    constraints = {}
    if min_len is not None:
        constraints["min_length"] = min_len
    if max_len is not None:
        constraints["max_length"] = max_len
    return Annotated[str, Field(**constraints)]


ShortStr = string_length(max_len=50)
MediumStr = string_length(max_len=255)
LongStr = string_length(max_len=1000)
