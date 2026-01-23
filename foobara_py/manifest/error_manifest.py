"""
Error manifest for Foobara introspection.
"""

import re
from typing import Any, Dict, Optional, Type

from pydantic import Field

from foobara_py.manifest.base import BaseManifest


class ErrorManifest(BaseManifest):
    """
    Manifest for a Foobara error type.

    Errors represent failure conditions in command execution.
    """

    name: str = Field(description="Error class name")
    code: str = Field(description="Error code")
    description: Optional[str] = Field(default=None, description="Error description")

    # Error details
    category: str = Field(
        default="runtime", description="Error category (input, runtime, not_found, etc.)"
    )
    is_retryable: bool = Field(default=False, description="Whether error is retryable")

    # Context schema
    context_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema for error context"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "category": self.category,
            "is_retryable": self.is_retryable,
            "context_schema": self.context_schema,
        }

    @classmethod
    def from_error_class(cls, error_class: Type[Exception]) -> "ErrorManifest":
        """
        Create manifest from an error class.

        Args:
            error_class: The error class to create manifest for.

        Returns:
            ErrorManifest instance.
        """
        import inspect

        name = error_class.__name__

        # Convert class name to error code (snake_case)
        code = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        if code.endswith("_error"):
            code = code[:-6]

        description = inspect.getdoc(error_class)

        # Determine category from class name
        category = "runtime"
        if "NotFound" in name:
            category = "not_found"
        elif "Input" in name or "Validation" in name:
            category = "input"
        elif "Auth" in name or "Permission" in name:
            category = "authorization"

        # Check if retryable
        is_retryable = getattr(error_class, "_retryable", False)

        return cls(
            name=name,
            code=code,
            description=description,
            category=category,
            is_retryable=is_retryable,
        )
