"""
Case conversion utilities for foobara-py.

Provides functions to convert strings between different naming conventions:
- snake_case
- camelCase
- PascalCase
- kebab-case
"""

import re

# Compile regex patterns at module level for performance
_LOWER_TO_UPPER = re.compile(r"([a-z0-9])([A-Z])")
_UPPER_SEQ_TO_WORD = re.compile(r"([A-Z]+)([A-Z][a-z])")
_MULTIPLE_UNDERSCORES = re.compile(r"_+")
_HAS_SEPARATORS = re.compile(r"[_\-\s]")
_SEPARATOR_SPLIT = re.compile(r"[_\-\s]+")


def to_snake_case(text: str) -> str:
    """
    Convert string to snake_case.

    Handles various input formats:
    - Spaces and hyphens are converted to underscores
    - Uppercase letters following lowercase are separated
    - Acronyms are handled correctly (APIKey -> api_key)

    Args:
        text: Input string in any case format

    Returns:
        snake_case string

    Examples:
        >>> to_snake_case("HelloWorld")
        'hello_world'
        >>> to_snake_case("APIKey")
        'api_key'
        >>> to_snake_case("hello-world")
        'hello_world'
    """
    # First, replace spaces and hyphens with underscores
    result = text.replace(" ", "_").replace("-", "_")

    # Handle sequences of capitals (like API_KEY or APIKey)
    # Insert underscore before uppercase letter that follows a lowercase
    result = _LOWER_TO_UPPER.sub(r"\1_\2", result)

    # Handle acronyms followed by words (like APIKey -> API_Key)
    result = _UPPER_SEQ_TO_WORD.sub(r"\1_\2", result)

    # Clean up multiple underscores
    result = _MULTIPLE_UNDERSCORES.sub("_", result)

    # Convert to lowercase
    return result.lower()


def to_pascal_case(text: str) -> str:
    """
    Convert string to PascalCase.

    Args:
        text: Input string in any case format

    Returns:
        PascalCase string

    Examples:
        >>> to_pascal_case("hello_world")
        'HelloWorld'
        >>> to_pascal_case("hello-world")
        'HelloWorld'
        >>> to_pascal_case("helloWorld")
        'HelloWorld'
    """
    # If value has no separators (underscores, hyphens, spaces),
    # it might be camelCase or PascalCase already - convert to snake_case first
    if not _HAS_SEPARATORS.search(text):
        text = to_snake_case(text)

    # Split on underscores, hyphens, and spaces
    words = _SEPARATOR_SPLIT.split(text)
    # Capitalize each word
    return "".join(word.capitalize() for word in words if word)


def to_camel_case(text: str) -> str:
    """
    Convert string to camelCase.

    Args:
        text: Input string in any case format

    Returns:
        camelCase string

    Examples:
        >>> to_camel_case("hello_world")
        'helloWorld'
        >>> to_camel_case("HelloWorld")
        'helloWorld'
        >>> to_camel_case("hello-world")
        'helloWorld'
    """
    # Check if already in camelCase or PascalCase (no separators)
    if not _HAS_SEPARATORS.search(text):
        # Just lowercase the first character
        return text[0].lower() + text[1:] if text else ""

    # Otherwise convert through PascalCase first
    pascal = to_pascal_case(text)
    return pascal[0].lower() + pascal[1:] if pascal else ""


def to_kebab_case(text: str) -> str:
    """
    Convert string to kebab-case.

    Args:
        text: Input string in any case format

    Returns:
        kebab-case string

    Examples:
        >>> to_kebab_case("HelloWorld")
        'hello-world'
        >>> to_kebab_case("hello_world")
        'hello-world'
        >>> to_kebab_case("helloWorld")
        'hello-world'
    """
    snake = to_snake_case(text)
    return snake.replace("_", "-")
