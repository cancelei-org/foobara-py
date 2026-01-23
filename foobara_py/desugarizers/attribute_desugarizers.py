"""
Attribute-based desugarizers for filtering and modifying input keys.

These desugarizers manipulate the structure of input dictionaries
by selecting, rejecting, renaming, or setting keys.
"""

from typing import Any

from foobara_py.desugarizers.base import Desugarizer


class OnlyInputs(Desugarizer):
    """
    Keep only specified input keys.

    Filters the input dictionary to include only the specified keys.
    Useful for ensuring only expected fields are passed to a command.

    Usage:
        desugarizer = OnlyInputs("name", "email")
        data = {"name": "John", "email": "john@example.com", "extra": "value"}
        result = desugarizer.desugarize(data)
        # {"name": "John", "email": "john@example.com"}
    """

    def __init__(self, *keys: str):
        """
        Initialize with keys to keep.

        Args:
            *keys: Variable number of keys to include
        """
        self.keys: set[str] = set(keys)

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Keep only specified keys"""
        return {k: v for k, v in data.items() if k in self.keys}


class RejectInputs(Desugarizer):
    """
    Remove specified input keys.

    Filters out the specified keys from the input dictionary.
    Useful for removing unwanted fields or sensitive data.

    Usage:
        desugarizer = RejectInputs("password", "secret")
        data = {"name": "John", "password": "secret123", "email": "john@example.com"}
        result = desugarizer.desugarize(data)
        # {"name": "John", "email": "john@example.com"}
    """

    def __init__(self, *keys: str):
        """
        Initialize with keys to reject.

        Args:
            *keys: Variable number of keys to exclude
        """
        self.keys: set[str] = set(keys)

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Remove specified keys"""
        return {k: v for k, v in data.items() if k not in self.keys}


class RenameKey(Desugarizer):
    """
    Rename input keys.

    Maps old key names to new key names. Useful for adapting
    external API formats to internal command schemas.

    Usage:
        desugarizer = RenameKey(old_name="name", old_email="email")
        data = {"old_name": "John", "old_email": "john@example.com"}
        result = desugarizer.desugarize(data)
        # {"name": "John", "email": "john@example.com"}
    """

    def __init__(self, **renames: str):
        """
        Initialize with rename mappings.

        Args:
            **renames: Keyword arguments mapping old_key="new_key"
        """
        self.renames: dict[str, str] = renames

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Rename keys according to mappings"""
        result = {}
        for k, v in data.items():
            new_key = self.renames.get(k, k)
            result[new_key] = v
        return result


class SetInputs(Desugarizer):
    """
    Set default values for inputs.

    Adds default values for missing keys. Existing values are preserved.
    Useful for providing defaults or injecting context.

    Usage:
        desugarizer = SetInputs(status="active", count=0)
        data = {"name": "John"}
        result = desugarizer.desugarize(data)
        # {"name": "John", "status": "active", "count": 0}
    """

    def __init__(self, **defaults):
        """
        Initialize with default values.

        Args:
            **defaults: Keyword arguments for default key-value pairs
        """
        self.defaults: dict[str, Any] = defaults

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add default values for missing keys"""
        result = dict(self.defaults)
        result.update(data)
        return result


class MergeInputs(Desugarizer):
    """
    Merge nested dictionaries into top level.

    Flattens nested dictionary structures by merging specified
    nested keys into the top level.

    Usage:
        desugarizer = MergeInputs("user", "settings")
        data = {
            "name": "John",
            "user": {"email": "john@example.com", "age": 30},
            "count": 5
        }
        result = desugarizer.desugarize(data)
        # {"name": "John", "email": "john@example.com", "age": 30, "count": 5}
    """

    def __init__(self, *keys_to_merge: str):
        """
        Initialize with keys to merge.

        Args:
            *keys_to_merge: Keys whose values (dicts) should be merged up
        """
        self.keys_to_merge: set[str] = set(keys_to_merge)

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Merge specified nested dicts into top level"""
        result = {}

        for k, v in data.items():
            if k in self.keys_to_merge and isinstance(v, dict):
                # Merge the nested dict
                result.update(v)
            else:
                result[k] = v

        return result


class SymbolsToTrue(Desugarizer):
    """
    Convert presence of keys to boolean true.

    For keys that exist (regardless of value), set them to True.
    Missing keys are not added. Useful for flag parameters.

    Usage:
        desugarizer = SymbolsToTrue("verbose", "debug")
        data = {"verbose": None, "name": "John"}
        result = desugarizer.desugarize(data)
        # {"verbose": True, "name": "John"}
    """

    def __init__(self, *symbol_keys: str):
        """
        Initialize with symbol keys.

        Args:
            *symbol_keys: Keys to convert to boolean true
        """
        self.symbol_keys: set[str] = set(symbol_keys)

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert symbol keys to True"""
        result = dict(data)
        for key in self.symbol_keys:
            if key in result:
                result[key] = True
        return result


# Auto-register desugarizers
from foobara_py.desugarizers.base import DesugarizerRegistry

DesugarizerRegistry.register("only_inputs", OnlyInputs)
DesugarizerRegistry.register("reject_inputs", RejectInputs)
DesugarizerRegistry.register("rename_key", RenameKey)
DesugarizerRegistry.register("set_inputs", SetInputs)
DesugarizerRegistry.register("merge_inputs", MergeInputs)
DesugarizerRegistry.register("symbols_to_true", SymbolsToTrue)
