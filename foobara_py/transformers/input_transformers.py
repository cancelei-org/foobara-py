"""
Input transformers for preprocessing command inputs.

These transformers run before input validation to normalize,
clean, or convert input data.
"""

from typing import Any

from foobara_py.transformers.base import Transformer
from foobara_py.util.case_conversion import to_camel_case, to_pascal_case, to_snake_case


class EntityToPrimaryKeyInputsTransformer(Transformer[dict[str, Any]]):
    """
    Convert entity objects in inputs to their primary keys.

    Useful for API endpoints that receive entity objects but
    need to store/pass only primary keys.

    Usage:
        transformer = EntityToPrimaryKeyInputsTransformer()
        inputs = {"user": user_entity, "name": "John"}
        result = transformer.transform(inputs)
        # {"user": 1, "name": "John"}
    """

    def transform(self, value: dict[str, Any]) -> dict[str, Any]:
        """Transform entity objects to primary keys"""
        if not isinstance(value, dict):
            return value

        result = {}
        for key, val in value.items():
            # Check if value has primary_key attribute (is an entity)
            if hasattr(val, "primary_key"):
                result[key] = val.primary_key
            # Handle list of entities
            elif isinstance(val, list) and val and hasattr(val[0], "primary_key"):
                result[key] = [v.primary_key for v in val]
            # Handle nested dict
            elif isinstance(val, dict):
                result[key] = self.transform(val)
            else:
                result[key] = val

        return result


class NormalizeKeysTransformer(Transformer[dict[str, Any]]):
    """
    Normalize dictionary keys (e.g., convert to snake_case).

    Usage:
        transformer = NormalizeKeysTransformer(to_case="snake")
        inputs = {"firstName": "John", "lastName": "Doe"}
        result = transformer.transform(inputs)
        # {"first_name": "John", "last_name": "Doe"}
    """

    def __init__(self, to_case: str = "snake"):
        """
        Initialize transformer.

        Args:
            to_case: Target case - "snake", "camel", or "pascal"
        """
        self.to_case = to_case

    def transform(self, value: dict[str, Any]) -> dict[str, Any]:
        """Normalize all keys in dictionary"""
        if not isinstance(value, dict):
            return value

        result = {}
        for key, val in value.items():
            normalized_key = self._normalize_key(key)

            # Recursively normalize nested dicts
            if isinstance(val, dict):
                result[normalized_key] = self.transform(val)
            elif isinstance(val, list):
                result[normalized_key] = [
                    self.transform(item) if isinstance(item, dict) else item for item in val
                ]
            else:
                result[normalized_key] = val

        return result

    def _normalize_key(self, key: str) -> str:
        """Convert key to target case"""
        if self.to_case == "snake":
            return to_snake_case(key)
        elif self.to_case == "camel":
            return to_camel_case(key)
        elif self.to_case == "pascal":
            return to_pascal_case(key)
        return key


class StripWhitespaceTransformer(Transformer[dict[str, Any]]):
    """
    Strip leading/trailing whitespace from string values.

    Usage:
        transformer = StripWhitespaceTransformer()
        inputs = {"name": "  John  ", "email": " john@example.com "}
        result = transformer.transform(inputs)
        # {"name": "John", "email": "john@example.com"}
    """

    def __init__(self, recursive: bool = True):
        """
        Initialize transformer.

        Args:
            recursive: Whether to strip strings in nested dicts/lists
        """
        self.recursive = recursive

    def transform(self, value: dict[str, Any]) -> dict[str, Any]:
        """Strip whitespace from all string values"""
        if not isinstance(value, dict):
            return value

        result = {}
        for key, val in value.items():
            if isinstance(val, str):
                result[key] = val.strip()
            elif self.recursive and isinstance(val, dict):
                result[key] = self.transform(val)
            elif self.recursive and isinstance(val, list):
                result[key] = [
                    item.strip()
                    if isinstance(item, str)
                    else (self.transform(item) if isinstance(item, dict) else item)
                    for item in val
                ]
            else:
                result[key] = val

        return result


class DefaultValuesTransformer(Transformer[dict[str, Any]]):
    """
    Set default values for missing keys.

    Usage:
        transformer = DefaultValuesTransformer(status="active", count=0)
        inputs = {"name": "John"}
        result = transformer.transform(inputs)
        # {"name": "John", "status": "active", "count": 0}
    """

    def __init__(self, **defaults):
        """
        Initialize with default values.

        Args:
            **defaults: Key-value pairs for default values
        """
        self.defaults = defaults

    def transform(self, value: dict[str, Any]) -> dict[str, Any]:
        """Add default values for missing keys"""
        if not isinstance(value, dict):
            return value

        result = dict(self.defaults)
        result.update(value)
        return result


class RemoveNullValuesTransformer(Transformer[dict[str, Any]]):
    """
    Remove keys with None values.

    Usage:
        transformer = RemoveNullValuesTransformer()
        inputs = {"name": "John", "age": None, "email": "john@example.com"}
        result = transformer.transform(inputs)
        # {"name": "John", "email": "john@example.com"}
    """

    def __init__(self, recursive: bool = True):
        """
        Initialize transformer.

        Args:
            recursive: Whether to remove None values in nested dicts
        """
        self.recursive = recursive

    def transform(self, value: dict[str, Any]) -> dict[str, Any]:
        """Remove keys with None values"""
        if not isinstance(value, dict):
            return value

        result = {}
        for key, val in value.items():
            if val is None:
                continue
            elif self.recursive and isinstance(val, dict):
                result[key] = self.transform(val)
            else:
                result[key] = val

        return result


# Auto-register transformers
from foobara_py.transformers.base import TransformerRegistry

TransformerRegistry.register("entity_to_pk", EntityToPrimaryKeyInputsTransformer, "input")
TransformerRegistry.register("normalize_keys", NormalizeKeysTransformer, "input")
TransformerRegistry.register("strip_whitespace", StripWhitespaceTransformer, "input")
TransformerRegistry.register("default_values", DefaultValuesTransformer, "input")
TransformerRegistry.register("remove_nulls", RemoveNullValuesTransformer, "input")
