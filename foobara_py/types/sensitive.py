"""
Sensitive types for Foobara Python.

Provides type wrappers for sensitive data (passwords, API keys, tokens) that:
- Automatically redact in string representations
- Prevent accidental logging of sensitive values
- Integrate with Pydantic for serialization redaction
- Work with manifest generation to exclude sensitive defaults
"""

import copy
from typing import Annotated, Any, Generic, TypeVar, get_args, get_origin

from pydantic import BaseModel, Field, GetCoreSchemaHandler, field_serializer
from pydantic_core import core_schema

T = TypeVar("T")


class Sensitive(Generic[T]):
    """
    Wrapper for sensitive values that redacts them in representations.

    Usage:
        password = Sensitive("secret123")
        print(password)  # Output: [REDACTED]
        actual = password.get()  # Get actual value: "secret123"

        # With Pydantic
        class User(BaseModel):
            email: str
            password: Sensitive[str]

        user = User(email="john@example.com", password="secret123")
        print(user)  # password shows as [REDACTED]
        print(user.model_dump())  # password is redacted
        print(user.password.get())  # Access actual value
    """

    __slots__ = ("_value",)

    def __init__(self, value: T):
        """Initialize with sensitive value"""
        object.__setattr__(self, "_value", value)

    def get(self) -> T:
        """Get the actual sensitive value"""
        return self._value

    def __repr__(self) -> str:
        """Redacted representation"""
        return "[REDACTED]"

    def __str__(self) -> str:
        """Redacted string representation"""
        return "[REDACTED]"

    def __eq__(self, other: Any) -> bool:
        """Compare sensitive values"""
        if isinstance(other, Sensitive):
            return self._value == other._value
        return self._value == other

    def __hash__(self) -> int:
        """Hash based on actual value"""
        return hash(self._value)

    def __bool__(self) -> bool:
        """Boolean conversion based on actual value"""
        return bool(self._value)

    # Pydantic v2 integration
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Pydantic core schema for validation"""
        # Get the wrapped type argument
        args = get_args(source_type)
        if args:
            inner_type = args[0]
        else:
            inner_type = str  # Default to string

        # Create schema that validates the inner type and wraps in Sensitive
        return core_schema.no_info_after_validator_function(
            lambda v: v if isinstance(v, Sensitive) else Sensitive(v), handler(inner_type)
        )

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent modification after creation"""
        raise AttributeError("Sensitive values are immutable")

    def __delattr__(self, name: str) -> None:
        """Prevent deletion"""
        raise AttributeError("Sensitive values are immutable")


# Type aliases for common sensitive data types
SensitiveStr = Sensitive[str]
Password = Annotated[Sensitive[str], Field(description="Password (redacted in logs)")]
APIKey = Annotated[Sensitive[str], Field(description="API key (redacted in logs)")]
SecretToken = Annotated[Sensitive[str], Field(description="Secret token (redacted in logs)")]
BearerToken = Annotated[Sensitive[str], Field(description="Bearer token (redacted in logs)")]


class SensitiveModel(BaseModel):
    """
    Base model that automatically handles sensitive field redaction in serialization.

    All Sensitive[T] fields are automatically redacted when calling model_dump()
    or model_dump_json() unless explicitly requested.

    Usage:
        class User(SensitiveModel):
            email: str
            password: Sensitive[str]
            api_key: Sensitive[str]

        user = User(email="john@example.com", password="secret", api_key="key123")

        # Default: redacts sensitive fields
        data = user.model_dump()
        # {'email': 'john@example.com', 'password': '[REDACTED]', 'api_key': '[REDACTED]'}

        # Include sensitive values explicitly
        data = user.model_dump_sensitive()
        # {'email': 'john@example.com', 'password': 'secret', 'api_key': 'key123'}
    """

    def model_dump(self, *, include_sensitive: bool = False, **kwargs) -> dict[str, Any]:
        """
        Dump model to dict, optionally redacting sensitive fields.

        Args:
            include_sensitive: If True, include actual sensitive values.
                              If False (default), redact sensitive fields.
            **kwargs: Passed to parent model_dump()
        """
        data = super().model_dump(**kwargs)

        if not include_sensitive:
            # Redact sensitive fields
            data = self._redact_sensitive(data)

        return data

    def model_dump_json(self, *, include_sensitive: bool = False, **kwargs) -> str:
        """
        Dump model to JSON string, optionally redacting sensitive fields.

        Args:
            include_sensitive: If True, include actual sensitive values.
                              If False (default), redact sensitive fields.
            **kwargs: Passed to parent model_dump_json()
        """
        # Use model_dump with redaction, then serialize
        data = self.model_dump(include_sensitive=include_sensitive)
        import json

        return json.dumps(data)

    def model_dump_sensitive(self, **kwargs) -> dict[str, Any]:
        """
        Dump model including actual sensitive values.

        Use with caution - only for secure storage or transmission.
        """
        return self.model_dump(include_sensitive=True, **kwargs)

    def _redact_sensitive(self, data: Any) -> Any:
        """
        Recursively redact sensitive values in data structure.

        Args:
            data: Data structure to redact

        Returns:
            Redacted data structure
        """
        if isinstance(data, dict):
            return {key: self._redact_sensitive(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._redact_sensitive(item) for item in data]
        elif isinstance(data, Sensitive):
            return "[REDACTED]"
        else:
            return data


def is_sensitive(value: Any) -> bool:
    """
    Check if a value is marked as sensitive.

    Args:
        value: Value to check

    Returns:
        True if value is Sensitive instance, False otherwise
    """
    return isinstance(value, Sensitive)


def get_sensitive_fields(model_class: type[BaseModel]) -> list[str]:
    """
    Get list of field names that are sensitive in a Pydantic model.

    Args:
        model_class: Pydantic model class to inspect

    Returns:
        List of field names with Sensitive types
    """
    sensitive_fields = []

    for field_name, field_info in model_class.model_fields.items():
        annotation = field_info.annotation

        # Check if annotation is Sensitive or Sensitive[T]
        origin = get_origin(annotation)
        if (
            origin is Sensitive
            or isinstance(annotation, type)
            and issubclass(annotation, Sensitive)
        ):
            sensitive_fields.append(field_name)
        # Check Annotated types
        elif origin is Annotated:
            args = get_args(annotation)
            if args and (
                get_origin(args[0]) is Sensitive
                or (isinstance(args[0], type) and issubclass(args[0], Sensitive))
            ):
                sensitive_fields.append(field_name)

    return sensitive_fields


def redact_dict(data: dict[str, Any], sensitive_keys: list[str] | None = None) -> dict[str, Any]:
    """
    Redact sensitive keys in a dictionary.

    Args:
        data: Dictionary to redact
        sensitive_keys: List of keys to redact. If None, redacts common sensitive keys.

    Returns:
        New dictionary with redacted values
    """
    if sensitive_keys is None:
        # Default sensitive keys
        sensitive_keys = [
            "password",
            "token",
            "api_key",
            "secret",
            "access_token",
            "refresh_token",
            "bearer_token",
            "private_key",
            "passphrase",
            "credentials",
            "auth_token",
        ]

    result = {}
    for key, value in data.items():
        # Check if key is sensitive (case-insensitive)
        if any(sens_key in key.lower() for sens_key in sensitive_keys):
            result[key] = "[REDACTED]"
        elif isinstance(value, Sensitive):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = redact_dict(value, sensitive_keys)
        elif isinstance(value, list):
            result[key] = [
                redact_dict(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result
