"""Validation helper utilities."""

from typing import Any, Type

from pydantic import BaseModel, ValidationError


def convert_validation_errors(exc: ValidationError) -> dict[str, list[str]]:
    """
    Convert Pydantic validation errors to a simple dict format.

    Args:
        exc: A Pydantic ValidationError

    Returns:
        Dict mapping field paths to error messages

    Example:
        >>> errors = convert_validation_errors(exc)
        {'name': ['field required'], 'age': ['value is not a valid integer']}
    """
    errors: dict[str, list[str]] = {}

    for error in exc.errors():
        # Build field path from loc tuple
        loc = error["loc"]
        field_path = ".".join(str(part) for part in loc)

        # Get error message
        msg = error["msg"]

        # Add to errors dict
        if field_path not in errors:
            errors[field_path] = []
        errors[field_path].append(msg)

    return errors


def validate_with_model(model: Type[BaseModel], data: dict[str, Any]) -> BaseModel:
    """
    Validate data against a Pydantic model.

    Args:
        model: A Pydantic BaseModel class
        data: Data to validate

    Returns:
        Validated model instance

    Raises:
        ValidationError: If validation fails

    Example:
        >>> instance = validate_with_model(MyInputs, {"name": "test"})
    """
    return model(**data)
