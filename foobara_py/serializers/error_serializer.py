"""
ErrorsSerializer for Ruby Foobara-compatible error formatting.

Serializes Foobara errors into the format expected by Ruby Foobara clients.
"""

from typing import Any, Dict, List

from foobara_py.core.errors import ErrorCollection, FoobaraError
from foobara_py.serializers.base import Serializer


class ErrorsSerializer(Serializer[ErrorCollection]):
    """
    Serialize errors to Ruby Foobara-compatible format.

    Converts Foobara errors into a structure that matches
    Ruby Foobara's error format for cross-platform compatibility.

    Format:
        {
            "errors": [
                {
                    "key": "runtime_path.symbol",
                    "path": ["field", "nested"],
                    "runtime_path": ["command1", "command2"],
                    "category": "data",
                    "symbol": "invalid_value",
                    "message": "Value is invalid",
                    "context": {"...": "..."}
                },
                ...
            ]
        }

    Usage:
        errors = ErrorCollection()
        errors.add(FoobaraError.data_error("invalid_email", ["email"], "Invalid email"))

        serializer = ErrorsSerializer()
        data = serializer.serialize(errors)
        # Returns Ruby-compatible error format
    """

    def serialize(self, obj: ErrorCollection) -> Dict[str, Any]:
        """
        Serialize error collection to Ruby format.

        Args:
            obj: ErrorCollection to serialize

        Returns:
            Dict with "errors" key containing list of error dicts
        """
        if isinstance(obj, ErrorCollection):
            return {"errors": [self._serialize_error(error) for error in obj.all()]}
        elif isinstance(obj, FoobaraError):
            return {"errors": [self._serialize_error(obj)]}
        elif isinstance(obj, list):
            # List of errors
            return {
                "errors": [
                    self._serialize_error(error) for error in obj if isinstance(error, FoobaraError)
                ]
            }
        else:
            return {"errors": []}

    def _serialize_error(self, error: FoobaraError) -> Dict[str, Any]:
        """Serialize a single error to Ruby format"""
        # Build the error key (runtime_path.symbol)
        key_parts = list(error.runtime_path) if error.runtime_path else []
        key_parts.append(error.symbol)
        key = ".".join(key_parts)

        return {
            "key": key,
            "path": list(error.path) if error.path else [],
            "runtime_path": list(error.runtime_path) if error.runtime_path else [],
            "category": error.category,
            "symbol": error.symbol,
            "message": error.message,
            "context": error.context or {},
            "is_fatal": error.is_fatal,
        }

    @classmethod
    def can_serialize(cls, obj: Any) -> bool:
        """Can serialize ErrorCollection or FoobaraError"""
        return isinstance(obj, (ErrorCollection, FoobaraError, list))

    @classmethod
    def priority(cls) -> int:
        """High priority for error serialization"""
        return 20


# Auto-register
from foobara_py.serializers.base import SerializerRegistry

SerializerRegistry.register(ErrorsSerializer)
