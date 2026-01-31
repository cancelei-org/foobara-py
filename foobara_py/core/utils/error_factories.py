"""Error factory configuration and utilities."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorFactoryConfig:
    """
    Configuration for creating error instances.

    Attributes:
        error_class: The error class to instantiate
        default_message: Default message if none provided
        category: Error category (data, runtime, logic, etc.)
        context_keys: Expected context keys for this error
    """

    error_class: type
    default_message: str
    category: str
    context_keys: list[str] | None = None


# Standard error categories
ERROR_CATEGORIES = {
    "data": "Data validation or format errors",
    "runtime": "Runtime execution errors",
    "logic": "Business logic errors",
    "system": "System-level errors",
    "network": "Network communication errors",
    "auth": "Authentication/authorization errors",
}
