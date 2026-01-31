"""
Ruby-compatible type declaration system for Foobara Python.

Provides:
- FoobaraType class for defining types with processors
- TypeRegistry for type registration and lookup
- Type processors (casters, validators, transformers)
- Common built-in types matching Ruby Foobara

This implements the Ruby Foobara type system pattern while leveraging
Python's type system and Pydantic for validation.
"""

import re
import threading
from abc import ABC, abstractmethod
from datetime import date, datetime, time
from decimal import Decimal
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

T = TypeVar("T")
S = TypeVar("S")
ProcessorValue = TypeVar("ProcessorValue")


# =============================================================================
# Type Processor Protocols
# =============================================================================


@runtime_checkable
class ProcessorProtocol(Protocol[T]):
    """
    Protocol for type processors.

    Any class implementing a process method that takes Any and returns T
    can be used as a processor. This enables duck typing for custom processors.

    Example:
        class MyCustomProcessor:
            def process(self, value: Any) -> str:
                return str(value).upper()

        # Automatically works with FoobaraType without inheritance
        custom_type = FoobaraType(
            name="upper_string",
            python_type=str,
            casters=[MyCustomProcessor()]
        )
    """

    def process(self, value: Any) -> T:
        """Process a value and return transformed result."""
        ...

    def __call__(self, value: Any) -> T:
        """Allow processor to be called as function."""
        ...


# =============================================================================
# Type Processors
# =============================================================================


class TypeProcessor(ABC, Generic[T]):
    """
    Base class for type processors.

    Processors transform or validate values during type processing.
    They form a pipeline that processes values in sequence.

    This class provides a concrete implementation of ProcessorProtocol
    with additional features like inheritance and composition.
    """

    @abstractmethod
    def process(self, value: Any) -> T:
        """
        Process a value.

        Args:
            value: The value to process

        Returns:
            The processed value

        Raises:
            TypeError: If value cannot be processed
            ValueError: If value is invalid
        """
        pass

    def __call__(self, value: Any) -> T:
        """Allow processor to be called as function"""
        return self.process(value)


class Caster(TypeProcessor[T]):
    """
    Casts/coerces values to target type.

    Casters attempt to convert values from one type to another.
    They run before validators.

    Example:
        class StringToIntCaster(Caster[int]):
            def process(self, value: Any) -> int:
                if isinstance(value, int):
                    return value
                if isinstance(value, str):
                    return int(value)
                raise TypeError(f"Cannot cast {type(value)} to int")
    """
    pass


class Validator(TypeProcessor[T]):
    """
    Validates values meet constraints.

    Validators check that values meet specific requirements.
    They run after casters and raise ValueError for invalid values.

    Example:
        class PositiveValidator(Validator[int]):
            def process(self, value: int) -> int:
                if value <= 0:
                    raise ValueError("Value must be positive")
                return value
    """
    pass


class Transformer(TypeProcessor[T]):
    """
    Transforms values after validation.

    Transformers modify valid values, such as normalizing formats.
    They run after validators.

    Example:
        class UppercaseTransformer(Transformer[str]):
            def process(self, value: str) -> str:
                return value.upper()
    """
    pass


# =============================================================================
# Built-in Casters
# =============================================================================


class StringCaster(Caster[str]):
    """Cast values to string"""

    def process(self, value: Any) -> str:
        if value is None:
            raise TypeError("Cannot cast None to string")
        return str(value)


class IntegerCaster(Caster[int]):
    """Cast values to integer"""

    def process(self, value: Any) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Empty string cannot be cast to integer")
            return int(value)
        if isinstance(value, Decimal):
            return int(value)
        raise TypeError(f"Cannot cast {type(value).__name__} to integer")


class FloatCaster(Caster[float]):
    """Cast values to float"""

    def process(self, value: Any) -> float:
        if isinstance(value, float):
            return value
        if isinstance(value, (int, Decimal)):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Empty string cannot be cast to float")
            return float(value)
        raise TypeError(f"Cannot cast {type(value).__name__} to float")


class BooleanCaster(Caster[bool]):
    """Cast values to boolean"""

    TRUE_VALUES = {"true", "yes", "1", "on", "t", "y"}
    FALSE_VALUES = {"false", "no", "0", "off", "f", "n"}

    def process(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            lower = value.strip().lower()
            if lower in self.TRUE_VALUES:
                return True
            if lower in self.FALSE_VALUES:
                return False
            raise ValueError(f"Cannot interpret '{value}' as boolean")
        raise TypeError(f"Cannot cast {type(value).__name__} to boolean")


class DateCaster(Caster[date]):
    """Cast values to date"""

    def process(self, value: Any) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            value = value.strip()
            # Try ISO format first
            try:
                return date.fromisoformat(value)
            except ValueError:
                pass
            # Try common formats
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse date from '{value}'")
        raise TypeError(f"Cannot cast {type(value).__name__} to date")


class DateTimeCaster(Caster[datetime]):
    """Cast values to datetime"""

    def process(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        if isinstance(value, str):
            value = value.strip()
            # Try ISO format first
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
            # Try common formats
            for fmt in (
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S",
            ):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse datetime from '{value}'")
        if isinstance(value, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(value)
        raise TypeError(f"Cannot cast {type(value).__name__} to datetime")


class UUIDCaster(Caster[UUID]):
    """Cast values to UUID"""

    def process(self, value: Any) -> UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value.strip())
        if isinstance(value, bytes):
            return UUID(bytes=value)
        raise TypeError(f"Cannot cast {type(value).__name__} to UUID")


class ListCaster(Caster[list]):
    """
    Cast values to list with optional element processing.

    Features:
    - Converts tuples, sets, frozensets to lists
    - Splits comma-separated strings
    - Wraps single values in lists
    - Optionally processes each element with element_caster

    Example:
        # Simple list casting
        caster = ListCaster()
        caster.process("a,b,c")  # ["a", "b", "c"]

        # With element casting
        int_caster = ListCaster(element_caster=IntegerCaster())
        int_caster.process(["1", "2", "3"])  # [1, 2, 3]
    """

    def __init__(self, element_caster: Optional[Caster] = None):
        self.element_caster = element_caster

    def process(self, value: Any) -> list:
        if isinstance(value, list):
            result = value
        elif isinstance(value, (tuple, set, frozenset)):
            result = list(value)
        elif isinstance(value, str):
            # Attempt to split by comma
            result = [v.strip() for v in value.split(",")]
        else:
            # Single value to list
            result = [value]

        if self.element_caster:
            result = [self.element_caster.process(elem) for elem in result]

        return result


class DictCaster(Caster[dict]):
    """Cast values to dict"""

    def process(self, value: Any) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, BaseModel):
            return value.model_dump()
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        raise TypeError(f"Cannot cast {type(value).__name__} to dict")


# =============================================================================
# Built-in Validators
# =============================================================================


class RequiredValidator(Validator[T]):
    """Validate that value is not None"""

    def process(self, value: T) -> T:
        if value is None:
            raise ValueError("Value is required")
        return value


class MinLengthValidator(Validator[str]):
    """Validate minimum string length"""

    def __init__(self, min_length: int):
        self.min_length = min_length

    def process(self, value: str) -> str:
        if len(value) < self.min_length:
            raise ValueError(f"Value must be at least {self.min_length} characters")
        return value


class MaxLengthValidator(Validator[str]):
    """Validate maximum string length"""

    def __init__(self, max_length: int):
        self.max_length = max_length

    def process(self, value: str) -> str:
        if len(value) > self.max_length:
            raise ValueError(f"Value must be at most {self.max_length} characters")
        return value


class MinValueValidator(Validator[T]):
    """Validate minimum numeric value"""

    def __init__(self, min_value: T, exclusive: bool = False):
        self.min_value = min_value
        self.exclusive = exclusive

    def process(self, value: T) -> T:
        if self.exclusive:
            if value <= self.min_value:
                raise ValueError(f"Value must be greater than {self.min_value}")
        else:
            if value < self.min_value:
                raise ValueError(f"Value must be at least {self.min_value}")
        return value


class MaxValueValidator(Validator[T]):
    """Validate maximum numeric value"""

    def __init__(self, max_value: T, exclusive: bool = False):
        self.max_value = max_value
        self.exclusive = exclusive

    def process(self, value: T) -> T:
        if self.exclusive:
            if value >= self.max_value:
                raise ValueError(f"Value must be less than {self.max_value}")
        else:
            if value > self.max_value:
                raise ValueError(f"Value must be at most {self.max_value}")
        return value


class PatternValidator(Validator[str]):
    """Validate string matches regex pattern"""

    def __init__(self, pattern: str, message: str | None = None):
        self.pattern = re.compile(pattern)
        self.message = message or f"Value must match pattern {pattern}"

    def process(self, value: str) -> str:
        if not self.pattern.match(value):
            raise ValueError(self.message)
        return value


class OneOfValidator(Validator[T]):
    """Validate value is one of allowed values"""

    def __init__(self, allowed_values: list[T]):
        self.allowed_values = set(allowed_values)

    def process(self, value: T) -> T:
        if value not in self.allowed_values:
            raise ValueError(f"Value must be one of: {self.allowed_values}")
        return value


class EmailValidator(Validator[str]):
    """Validate email format"""

    EMAIL_PATTERN = re.compile(r"^[\w\.\-\+]+@[\w\.\-]+\.[a-zA-Z]{2,}$")

    def process(self, value: str) -> str:
        if not self.EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email format")
        return value


class URLValidator(Validator[str]):
    """Validate URL format"""

    URL_PATTERN = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    def process(self, value: str) -> str:
        if not self.URL_PATTERN.match(value):
            raise ValueError("Invalid URL format")
        return value


class RangeValidator(Validator[T]):
    """
    Validate value is within a range (inclusive).

    Example:
        validator = RangeValidator(0, 100)
        validator.process(50)  # OK
        validator.process(150)  # ValueError
    """

    def __init__(self, min_value: T, max_value: T):
        self.min_value = min_value
        self.max_value = max_value

    def process(self, value: T) -> T:
        if value < self.min_value or value > self.max_value:
            raise ValueError(
                f"Value must be between {self.min_value} and {self.max_value}"
            )
        return value


class NotEmptyValidator(Validator[Union[str, List, Dict, Set]]):
    """
    Validate that collection is not empty.

    Works with strings, lists, dicts, sets, etc.

    Example:
        validator = NotEmptyValidator()
        validator.process("hello")  # OK
        validator.process("")  # ValueError
        validator.process([1, 2])  # OK
        validator.process([])  # ValueError
    """

    def process(self, value: Union[str, List, Dict, Set]) -> Union[str, List, Dict, Set]:
        if not value:
            raise ValueError("Value cannot be empty")
        return value


class UniqueItemsValidator(Validator[List[T]]):
    """
    Validate that all items in a list are unique.

    Example:
        validator = UniqueItemsValidator()
        validator.process([1, 2, 3])  # OK
        validator.process([1, 2, 2, 3])  # ValueError
    """

    def process(self, value: List[T]) -> List[T]:
        if len(value) != len(set(value)):
            raise ValueError("All items must be unique")
        return value


class ContainsValidator(Validator[str]):
    """
    Validate that string contains specific substring.

    Example:
        validator = ContainsValidator("@", case_sensitive=False)
        validator.process("user@example.com")  # OK
        validator.process("username")  # ValueError
    """

    def __init__(self, substring: str, case_sensitive: bool = True):
        self.substring = substring
        self.case_sensitive = case_sensitive

    def process(self, value: str) -> str:
        check_value = value if self.case_sensitive else value.lower()
        check_substring = self.substring if self.case_sensitive else self.substring.lower()

        if check_substring not in check_value:
            raise ValueError(f"Value must contain '{self.substring}'")
        return value


# =============================================================================
# Built-in Transformers
# =============================================================================


class StripWhitespaceTransformer(Transformer[str]):
    """Strip whitespace from strings"""

    def process(self, value: str) -> str:
        return value.strip()


class LowercaseTransformer(Transformer[str]):
    """Convert string to lowercase"""

    def process(self, value: str) -> str:
        return value.lower()


class UppercaseTransformer(Transformer[str]):
    """Convert string to uppercase"""

    def process(self, value: str) -> str:
        return value.upper()


class TitleCaseTransformer(Transformer[str]):
    """Convert string to title case"""

    def process(self, value: str) -> str:
        return value.title()


class RoundTransformer(Transformer[float]):
    """Round float to specified decimal places"""

    def __init__(self, decimal_places: int = 2):
        self.decimal_places = decimal_places

    def process(self, value: float) -> float:
        return round(value, self.decimal_places)


class ClampTransformer(Transformer[Union[int, float]]):
    """
    Clamp numeric value to a range.

    Unlike validators which reject out-of-range values,
    this transformer adjusts them to the nearest boundary.

    Example:
        transformer = ClampTransformer(0, 100)
        transformer.process(-10)  # Returns 0
        transformer.process(150)  # Returns 100
        transformer.process(50)  # Returns 50
    """

    def __init__(self, min_value: Union[int, float], max_value: Union[int, float]):
        self.min_value = min_value
        self.max_value = max_value

    def process(self, value: Union[int, float]) -> Union[int, float]:
        return max(self.min_value, min(value, self.max_value))


class DefaultTransformer(Transformer[T]):
    """
    Replace None or empty values with a default.

    Example:
        transformer = DefaultTransformer("unknown")
        transformer.process(None)  # Returns "unknown"
        transformer.process("")  # Returns "unknown"
        transformer.process("value")  # Returns "value"
    """

    def __init__(self, default: T, replace_empty: bool = True):
        self.default = default
        self.replace_empty = replace_empty

    def process(self, value: Optional[T]) -> T:
        if value is None:
            return self.default
        if self.replace_empty and not value:
            return self.default
        return value


class TruncateTransformer(Transformer[str]):
    """
    Truncate string to maximum length with optional suffix.

    Example:
        transformer = TruncateTransformer(10, suffix="...")
        transformer.process("Hello")  # Returns "Hello"
        transformer.process("Hello World!")  # Returns "Hello W..."
    """

    def __init__(self, max_length: int, suffix: str = "..."):
        self.max_length = max_length
        self.suffix = suffix

    def process(self, value: str) -> str:
        if len(value) <= self.max_length:
            return value
        return value[: self.max_length - len(self.suffix)] + self.suffix


class SlugifyTransformer(Transformer[str]):
    """
    Convert string to URL-safe slug.

    Example:
        transformer = SlugifyTransformer()
        transformer.process("Hello World!")  # Returns "hello-world"
        transformer.process("  Product #123  ")  # Returns "product-123"
    """

    def process(self, value: str) -> str:
        # Convert to lowercase and strip
        slug = value.lower().strip()
        # Remove non-alphanumeric characters except spaces and hyphens
        slug = re.sub(r"[^\w\s-]", "", slug)
        # Replace spaces and multiple hyphens with single hyphen
        slug = re.sub(r"[-\s]+", "-", slug)
        # Remove leading/trailing hyphens
        return slug.strip("-")


class NormalizeWhitespaceTransformer(Transformer[str]):
    """
    Normalize whitespace in strings.

    Replaces multiple whitespace characters with single spaces
    and strips leading/trailing whitespace.

    Example:
        transformer = NormalizeWhitespaceTransformer()
        transformer.process("Hello    World")  # Returns "Hello World"
        transformer.process("  Text  ")  # Returns "Text"
    """

    def process(self, value: str) -> str:
        return " ".join(value.split())


# =============================================================================
# Foobara Type
# =============================================================================


class FoobaraType(Generic[T]):
    """
    Ruby-compatible type declaration.

    Defines a type with processors for casting, validating, and transforming values.

    Usage:
        # Simple type
        email_type = FoobaraType(
            name="email",
            python_type=str,
            validators=[EmailValidator()],
            transformers=[StripWhitespaceTransformer(), LowercaseTransformer()]
        )

        # Use the type
        result = email_type.process("  John@Example.COM  ")
        # Returns: "john@example.com"

        # With custom caster
        positive_int = FoobaraType(
            name="positive_integer",
            python_type=int,
            casters=[IntegerCaster()],
            validators=[MinValueValidator(1)]
        )
    """

    def __init__(
        self,
        name: str,
        python_type: Type[T],
        *,
        casters: Optional[List[Caster]] = None,
        validators: Optional[List[Validator]] = None,
        transformers: Optional[List[Transformer]] = None,
        description: Optional[str] = None,
        default: Optional[T] = None,
        has_default: bool = False,
        nullable: bool = False,
        element_type: Optional["FoobaraType"] = None,  # For arrays
        key_type: Optional["FoobaraType"] = None,  # For associative arrays (dicts)
        value_type: Optional["FoobaraType"] = None,  # For associative arrays
        gt: Optional[Union[int, float]] = None,  # Greater than (for Pydantic Field)
        ge: Optional[Union[int, float]] = None,  # Greater or equal
        lt: Optional[Union[int, float]] = None,  # Less than
        le: Optional[Union[int, float]] = None,  # Less or equal
        min_length: Optional[int] = None,  # Minimum length (strings/collections)
        max_length: Optional[int] = None,  # Maximum length
        pattern: Optional[str] = None,  # Regex pattern
        examples: Optional[List[T]] = None,  # Example values for documentation
    ):
        self.name = name
        self.python_type = python_type
        self.casters = casters or []
        self.validators = validators or []
        self.transformers = transformers or []
        self.description = description
        self.default = default
        self.has_default = has_default
        self.nullable = nullable
        self.element_type = element_type
        self.key_type = key_type
        self.value_type = value_type

        # Pydantic Field constraints
        self.gt = gt
        self.ge = ge
        self.lt = lt
        self.le = le
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.examples = examples or []

    def process(self, value: Any) -> T:
        """
        Process a value through the type's processor pipeline.

        Pipeline order:
        1. Handle None/default
        2. Casters (type conversion)
        3. Transformers (value normalization) - runs BEFORE validators
        4. Validators (constraint checking) - runs on normalized values

        NOTE: Ruby foobara v0.5.1 fixed type reference defaults handling (commit a35d1aca)
        by checking if attribute_type_declaration is a Hash before accessing allow_nil.
        In Python, we use Pydantic BaseModel which handles this automatically through
        Optional[] type hints, so no explicit fix is needed.

        Args:
            value: The value to process

        Returns:
            The processed value

        Raises:
            TypeError: If casting fails
            ValueError: If validation fails
        """
        # Handle None
        if value is None:
            # Default takes precedence over nullable
            if self.has_default:
                return self.default
            if self.nullable:
                return None
            raise ValueError(f"Value cannot be None for type {self.name}")

        # Run casters
        for caster in self.casters:
            value = caster.process(value)

        # Run transformers BEFORE validators (normalize values first)
        for transformer in self.transformers:
            value = transformer.process(value)

        # Handle nested types
        if self.element_type and isinstance(value, list):
            value = [self.element_type.process(elem) for elem in value]

        if self.key_type and self.value_type and isinstance(value, dict):
            value = {
                self.key_type.process(k): self.value_type.process(v)
                for k, v in value.items()
            }

        # Run validators on normalized values
        for validator in self.validators:
            value = validator.process(value)

        return value

    def __call__(self, value: Any) -> T:
        """Allow type to be called as function"""
        return self.process(value)

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """
        Validate a value without raising exceptions.

        Args:
            value: The value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.process(value)
            return True, None
        except (TypeError, ValueError) as e:
            return False, str(e)

    def is_valid(self, value: Any) -> bool:
        """Check if value is valid for this type"""
        valid, _ = self.validate(value)
        return valid

    def with_validators(self, *validators: Validator) -> "FoobaraType[T]":
        """Create new type with additional validators"""
        return FoobaraType(
            name=self.name,
            python_type=self.python_type,
            casters=self.casters.copy(),
            validators=self.validators + list(validators),
            transformers=self.transformers.copy(),
            description=self.description,
            default=self.default,
            has_default=self.has_default,
            nullable=self.nullable,
            element_type=self.element_type,
            key_type=self.key_type,
            value_type=self.value_type,
            gt=self.gt,
            ge=self.ge,
            lt=self.lt,
            le=self.le,
            min_length=self.min_length,
            max_length=self.max_length,
            pattern=self.pattern,
            examples=self.examples.copy() if self.examples else None,
        )

    def with_transformers(self, *transformers: Transformer) -> "FoobaraType[T]":
        """Create new type with additional transformers"""
        return FoobaraType(
            name=self.name,
            python_type=self.python_type,
            casters=self.casters.copy(),
            validators=self.validators.copy(),
            transformers=self.transformers + list(transformers),
            description=self.description,
            default=self.default,
            has_default=self.has_default,
            nullable=self.nullable,
            element_type=self.element_type,
            key_type=self.key_type,
            value_type=self.value_type,
            gt=self.gt,
            ge=self.ge,
            lt=self.lt,
            le=self.le,
            min_length=self.min_length,
            max_length=self.max_length,
            pattern=self.pattern,
            examples=self.examples.copy() if self.examples else None,
        )

    def optional(self, default: Optional[T] = None) -> "FoobaraType[Optional[T]]":
        """Create optional version of this type"""
        return FoobaraType(
            name=f"optional_{self.name}",
            python_type=self.python_type,
            casters=self.casters.copy(),
            validators=self.validators.copy(),
            transformers=self.transformers.copy(),
            description=self.description,
            default=default,
            has_default=True,
            nullable=True,
            element_type=self.element_type,
            key_type=self.key_type,
            value_type=self.value_type,
            gt=self.gt,
            ge=self.ge,
            lt=self.lt,
            le=self.le,
            min_length=self.min_length,
            max_length=self.max_length,
            pattern=self.pattern,
            examples=self.examples.copy() if self.examples else None,
        )

    def array(self) -> "FoobaraType[list[T]]":
        """Create array type containing this type"""
        return FoobaraType(
            name=f"array_of_{self.name}",
            python_type=list,
            casters=[ListCaster()],
            element_type=self,
        )

    def to_pydantic_field(self) -> tuple[Type, Field]:
        """
        Convert this FoobaraType to a Pydantic field annotation.

        Returns:
            Tuple of (type annotation, Field object)

        Example:
            email_type = EmailType
            field_type, field_obj = email_type.to_pydantic_field()

            # Use in model creation
            UserModel = create_model(
                'User',
                email=(field_type, field_obj),
            )
        """
        # Build Field constraints
        field_kwargs: Dict[str, Any] = {}

        if self.description:
            field_kwargs["description"] = self.description

        if self.has_default:
            field_kwargs["default"] = self.default
        elif self.nullable:
            field_kwargs["default"] = None

        # Add numeric constraints
        if self.gt is not None:
            field_kwargs["gt"] = self.gt
        if self.ge is not None:
            field_kwargs["ge"] = self.ge
        if self.lt is not None:
            field_kwargs["lt"] = self.lt
        if self.le is not None:
            field_kwargs["le"] = self.le

        # Add string/collection constraints
        if self.min_length is not None:
            field_kwargs["min_length"] = self.min_length
        if self.max_length is not None:
            field_kwargs["max_length"] = self.max_length
        if self.pattern is not None:
            field_kwargs["pattern"] = self.pattern

        # Add examples
        if self.examples:
            field_kwargs["examples"] = self.examples

        # Determine the type annotation
        if self.nullable or self.has_default:
            type_annotation = Optional[self.python_type]
        else:
            type_annotation = self.python_type

        return type_annotation, Field(**field_kwargs)

    def to_pydantic_validator(self) -> Optional[Callable]:
        """
        Create a Pydantic field validator from this type's processors.

        Returns:
            A validator function that can be used with @field_validator

        Example:
            email_type = EmailType

            class User(BaseModel):
                email: str

                _validate_email = field_validator('email')(
                    email_type.to_pydantic_validator()
                )
        """
        if not (self.casters or self.validators or self.transformers):
            return None

        def validator(value: Any) -> T:
            """Pydantic validator using FoobaraType processors."""
            return self.process(value)

        return validator

    def create_pydantic_model(
        self,
        model_name: str,
        fields: Dict[str, "FoobaraType"],
        *,
        config: Optional[ConfigDict] = None,
    ) -> Type[BaseModel]:
        """
        Create a Pydantic model from a dictionary of FoobaraTypes.

        Args:
            model_name: Name of the generated model
            fields: Dictionary mapping field names to FoobaraTypes
            config: Optional Pydantic ConfigDict

        Returns:
            Generated Pydantic model class

        Example:
            fields = {
                'email': EmailType,
                'age': PositiveIntegerType,
                'name': StringType,
            }

            UserModel = EmailType.create_pydantic_model('User', fields)

            user = UserModel(
                email='john@example.com',
                age=30,
                name='John Doe'
            )
        """
        # Build field definitions
        field_definitions: Dict[str, Any] = {}
        validators_dict: Dict[str, Callable] = {}

        for field_name, foobara_type in fields.items():
            type_annotation, field_obj = foobara_type.to_pydantic_field()
            field_definitions[field_name] = (type_annotation, field_obj)

            # Add validator if type has processors
            validator = foobara_type.to_pydantic_validator()
            if validator:
                validators_dict[f"validate_{field_name}"] = field_validator(field_name)(
                    validator
                )

        # Create the model
        model = create_model(
            model_name,
            **field_definitions,
            __config__=config,
            __validators__=validators_dict,
        )

        return model

    def to_manifest(self) -> Dict[str, Any]:
        """Generate type manifest for discovery"""
        manifest = {
            "name": self.name,
            "type": self.python_type.__name__,
            "nullable": self.nullable,
        }

        if self.description:
            manifest["description"] = self.description

        if self.has_default:
            manifest["default"] = self.default

        if self.element_type:
            manifest["element_type"] = self.element_type.to_manifest()

        if self.key_type and self.value_type:
            manifest["key_type"] = self.key_type.to_manifest()
            manifest["value_type"] = self.value_type.to_manifest()

        return manifest


# =============================================================================
# Type Registry
# =============================================================================


class TypeRegistry:
    """
    Global registry for Foobara types.

    Provides lookup of types by name and category.

    Usage:
        # Register a type
        TypeRegistry.register(email_type)

        # Lookup by name
        email = TypeRegistry.get("email")

        # Process value
        result = email.process("John@Example.COM")
    """

    _types: dict[str, FoobaraType] = {}
    _categories: dict[str, list[str]] = {}
    _lock = threading.Lock()

    @classmethod
    def register(
        cls, type_def: FoobaraType, category: str | None = None
    ) -> FoobaraType:
        """
        Register a type.

        Args:
            type_def: The type to register
            category: Optional category for grouping

        Returns:
            The registered type
        """
        with cls._lock:
            cls._types[type_def.name] = type_def

            if category:
                if category not in cls._categories:
                    cls._categories[category] = []
                cls._categories[category].append(type_def.name)

        return type_def

    @classmethod
    def get(cls, name: str) -> FoobaraType | None:
        """Get type by name"""
        with cls._lock:
            return cls._types.get(name)

    @classmethod
    def get_or_raise(cls, name: str) -> FoobaraType:
        """Get type by name, raising if not found"""
        type_def = cls.get(name)
        if type_def is None:
            raise KeyError(f"Type '{name}' not registered")
        return type_def

    @classmethod
    def by_category(cls, category: str) -> list[FoobaraType]:
        """Get all types in a category"""
        with cls._lock:
            names = cls._categories.get(category, [])
            return [cls._types[name] for name in names if name in cls._types]

    @classmethod
    def list_all(cls) -> dict[str, FoobaraType]:
        """List all registered types"""
        with cls._lock:
            return cls._types.copy()

    @classmethod
    def list_categories(cls) -> list[str]:
        """List all categories"""
        with cls._lock:
            return list(cls._categories.keys())

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a type"""
        with cls._lock:
            cls._types.pop(name, None)
            for cat_list in cls._categories.values():
                if name in cat_list:
                    cat_list.remove(name)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered types"""
        with cls._lock:
            cls._types.clear()
            cls._categories.clear()


# =============================================================================
# Built-in Types
# =============================================================================

# Primitive types
StringType = FoobaraType(
    name="string",
    python_type=str,
    casters=[StringCaster()],
    transformers=[StripWhitespaceTransformer()],
)

IntegerType = FoobaraType(
    name="integer",
    python_type=int,
    casters=[IntegerCaster()],
)

FloatType = FoobaraType(
    name="float",
    python_type=float,
    casters=[FloatCaster()],
)

BooleanType = FoobaraType(
    name="boolean",
    python_type=bool,
    casters=[BooleanCaster()],
)

DateType = FoobaraType(
    name="date",
    python_type=date,
    casters=[DateCaster()],
)

DateTimeType = FoobaraType(
    name="datetime",
    python_type=datetime,
    casters=[DateTimeCaster()],
)

UUIDType = FoobaraType(
    name="uuid",
    python_type=UUID,
    casters=[UUIDCaster()],
)

# String types with constraints
EmailType = FoobaraType(
    name="email",
    python_type=str,
    casters=[StringCaster()],
    validators=[EmailValidator()],
    transformers=[StripWhitespaceTransformer(), LowercaseTransformer()],
    description="Email address",
)

URLType = FoobaraType(
    name="url",
    python_type=str,
    casters=[StringCaster()],
    validators=[URLValidator()],
    transformers=[StripWhitespaceTransformer()],
    description="URL",
)

# Numeric types with constraints
PositiveIntegerType = FoobaraType(
    name="positive_integer",
    python_type=int,
    casters=[IntegerCaster()],
    validators=[MinValueValidator(1)],
    description="Positive integer (>= 1)",
)

NonNegativeIntegerType = FoobaraType(
    name="non_negative_integer",
    python_type=int,
    casters=[IntegerCaster()],
    validators=[MinValueValidator(0)],
    description="Non-negative integer (>= 0)",
)

PercentageType = FoobaraType(
    name="percentage",
    python_type=float,
    casters=[FloatCaster()],
    validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    description="Percentage (0-100)",
)

# Container types
ArrayType = FoobaraType(
    name="array",
    python_type=list,
    casters=[ListCaster()],
)

HashType = FoobaraType(
    name="hash",
    python_type=dict,
    casters=[DictCaster()],
    description="Associative array (dict)",
)


# Register built-in types
def _register_builtins():
    """Register all built-in types"""
    builtins = [
        (StringType, "primitive"),
        (IntegerType, "primitive"),
        (FloatType, "primitive"),
        (BooleanType, "primitive"),
        (DateType, "primitive"),
        (DateTimeType, "primitive"),
        (UUIDType, "primitive"),
        (EmailType, "string"),
        (URLType, "string"),
        (PositiveIntegerType, "numeric"),
        (NonNegativeIntegerType, "numeric"),
        (PercentageType, "numeric"),
        (ArrayType, "container"),
        (HashType, "container"),
    ]

    for type_def, category in builtins:
        TypeRegistry.register(type_def, category)


_register_builtins()


# =============================================================================
# Type Builder (DSL)
# =============================================================================


def type_declaration(
    name: str,
    python_type: type[T] = str,
    *,
    cast: list[Caster] | None = None,
    validate: list[Validator] | None = None,
    transform: list[Transformer] | None = None,
    description: str | None = None,
    default: T | None = None,
    nullable: bool = False,
    element_of: FoobaraType | None = None,
    register: bool = True,
    category: str | None = None,
) -> FoobaraType[T]:
    """
    DSL for declaring Foobara types.

    Provides a fluent interface for type declaration matching Ruby Foobara style.

    Usage:
        # Simple type
        phone_number = type_declaration(
            "phone_number",
            validate=[PatternValidator(r"^\\+?[0-9]{10,15}$")],
            transform=[StripWhitespaceTransformer()]
        )

        # Complex type with casting
        money = type_declaration(
            "money",
            python_type=Decimal,
            cast=[...],
            validate=[MinValueValidator(Decimal("0"))],
            description="Monetary amount"
        )
    """
    type_def = FoobaraType(
        name=name,
        python_type=python_type,
        casters=cast or [],
        validators=validate or [],
        transformers=transform or [],
        description=description,
        default=default,
        has_default=default is not None,
        nullable=nullable,
        element_type=element_of,
    )

    if register:
        TypeRegistry.register(type_def, category)

    return type_def


# Convenience function
def define_type(
    name: str,
    **kwargs
) -> FoobaraType:
    """Alias for type_declaration"""
    return type_declaration(name, **kwargs)
