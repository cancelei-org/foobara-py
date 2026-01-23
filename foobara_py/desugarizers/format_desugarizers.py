"""
Format-based desugarizers for parsing different data formats.

These desugarizers convert string data in various formats
(YAML, JSON, CSV) into structured dictionaries.
"""

import json
from typing import Any

from foobara_py.desugarizers.base import Desugarizer


class InputsFromYaml(Desugarizer):
    """
    Parse YAML string inputs.

    Converts YAML-formatted strings in specified keys to
    structured data (dicts/lists).

    Usage:
        desugarizer = InputsFromYaml("config", "settings")
        data = {"config": "name: John\\nemail: john@example.com"}
        result = desugarizer.desugarize(data)
        # {"config": {"name": "John", "email": "john@example.com"}}
    """

    def __init__(self, *yaml_keys: str):
        """
        Initialize with keys to parse as YAML.

        Args:
            *yaml_keys: Keys whose values should be parsed as YAML
        """
        self.yaml_keys: set[str] = set(yaml_keys)

        # Try to import yaml
        try:
            import yaml

            self.yaml = yaml
        except ImportError:
            self.yaml = None

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse YAML strings in specified keys"""
        if self.yaml is None:
            raise ImportError(
                "PyYAML is required for InputsFromYaml. Install with: pip install pyyaml"
            )

        result = dict(data)
        for key in self.yaml_keys:
            if key in result and isinstance(result[key], str):
                try:
                    result[key] = self.yaml.safe_load(result[key])
                except Exception:
                    # Leave as string if parsing fails
                    pass

        return result


class InputsFromJson(Desugarizer):
    """
    Parse JSON string inputs.

    Converts JSON-formatted strings in specified keys to
    structured data (dicts/lists).

    Usage:
        desugarizer = InputsFromJson("data", "payload")
        data = {"data": '{"name": "John", "age": 30}'}
        result = desugarizer.desugarize(data)
        # {"data": {"name": "John", "age": 30}}
    """

    def __init__(self, *json_keys: str):
        """
        Initialize with keys to parse as JSON.

        Args:
            *json_keys: Keys whose values should be parsed as JSON
        """
        self.json_keys: set[str] = set(json_keys)

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON strings in specified keys"""
        result = dict(data)
        for key in self.json_keys:
            if key in result and isinstance(result[key], str):
                try:
                    result[key] = json.loads(result[key])
                except (json.JSONDecodeError, TypeError):
                    # Leave as string if parsing fails
                    pass

        return result


class InputsFromCsv(Desugarizer):
    """
    Parse CSV string inputs into list of dicts.

    Converts CSV-formatted strings into structured lists.
    Assumes first row contains headers.

    Usage:
        desugarizer = InputsFromCsv("users")
        data = {"users": "name,email\\nJohn,john@example.com\\nJane,jane@example.com"}
        result = desugarizer.desugarize(data)
        # {"users": [{"name": "John", "email": "john@example.com"}, ...]}
    """

    def __init__(self, *csv_keys: str, delimiter: str = ","):
        """
        Initialize with keys to parse as CSV.

        Args:
            *csv_keys: Keys whose values should be parsed as CSV
            delimiter: CSV delimiter (default: ",")
        """
        self.csv_keys: set[str] = set(csv_keys)
        self.delimiter = delimiter

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse CSV strings in specified keys"""
        import csv
        from io import StringIO

        result = dict(data)
        for key in self.csv_keys:
            if key in result and isinstance(result[key], str):
                try:
                    reader = csv.DictReader(StringIO(result[key]), delimiter=self.delimiter)
                    result[key] = list(reader)
                except Exception:
                    # Leave as string if parsing fails
                    pass

        return result


class ParseBooleans(Desugarizer):
    """
    Parse boolean string values.

    Converts string representations of booleans
    ("true", "false", "yes", "no", "1", "0") to actual booleans.

    Usage:
        desugarizer = ParseBooleans("active", "verified")
        data = {"active": "true", "verified": "yes", "count": "5"}
        result = desugarizer.desugarize(data)
        # {"active": True, "verified": True, "count": "5"}
    """

    TRUE_VALUES = {"true", "yes", "1", "on", "t", "y"}
    FALSE_VALUES = {"false", "no", "0", "off", "f", "n"}

    def __init__(self, *bool_keys: str, all_keys: bool = False):
        """
        Initialize with keys to parse as booleans.

        Args:
            *bool_keys: Specific keys to parse
            all_keys: If True, parse all string values that look like booleans
        """
        self.bool_keys: set[str] = set(bool_keys)
        self.all_keys = all_keys

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse boolean strings"""
        result = {}

        for k, v in data.items():
            if not isinstance(v, str):
                result[k] = v
                continue

            # Check if we should parse this key
            should_parse = self.all_keys or k in self.bool_keys

            if should_parse:
                v_lower = v.lower().strip()
                if v_lower in self.TRUE_VALUES:
                    result[k] = True
                elif v_lower in self.FALSE_VALUES:
                    result[k] = False
                else:
                    result[k] = v
            else:
                result[k] = v

        return result


class ParseNumbers(Desugarizer):
    """
    Parse numeric string values.

    Converts string representations of numbers to int or float.

    Usage:
        desugarizer = ParseNumbers("count", "price")
        data = {"count": "42", "price": "19.99", "name": "Product"}
        result = desugarizer.desugarize(data)
        # {"count": 42, "price": 19.99, "name": "Product"}
    """

    def __init__(self, *number_keys: str, all_keys: bool = False):
        """
        Initialize with keys to parse as numbers.

        Args:
            *number_keys: Specific keys to parse
            all_keys: If True, parse all string values that look like numbers
        """
        self.number_keys: set[str] = set(number_keys)
        self.all_keys = all_keys

    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse numeric strings"""
        result = {}

        for k, v in data.items():
            if not isinstance(v, str):
                result[k] = v
                continue

            # Check if we should parse this key
            should_parse = self.all_keys or k in self.number_keys

            if should_parse:
                result[k] = self._parse_number(v)
            else:
                result[k] = v

        return result

    @staticmethod
    def _parse_number(value: str) -> Any:
        """Try to parse string as number"""
        try:
            # Try int first
            if "." not in value:
                return int(value)
            else:
                return float(value)
        except (ValueError, TypeError):
            return value


# Auto-register desugarizers
from foobara_py.desugarizers.base import DesugarizerRegistry

DesugarizerRegistry.register("from_yaml", InputsFromYaml)
DesugarizerRegistry.register("from_json", InputsFromJson)
DesugarizerRegistry.register("from_csv", InputsFromCsv)
DesugarizerRegistry.register("parse_booleans", ParseBooleans)
DesugarizerRegistry.register("parse_numbers", ParseNumbers)
