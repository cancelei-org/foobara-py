"""
TypesConcern - Type extraction and caching for Command inputs and results.

Handles:
- Extracting InputT and ResultT from Generic parameters
- Caching type information at class level
- JSON Schema generation for inputs

Pattern: Ruby Foobara's InputsType and ResultType concerns
"""

from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel

from foobara_py.core.utils import extract_inputs_type, extract_result_type


class TypesConcern:
    """Mixin for type extraction and caching."""

    # Type caching (class-level)
    _cached_inputs_type: ClassVar[Optional[Type[BaseModel]]] = None
    _cached_result_type: ClassVar[Optional[Type]] = None

    @classmethod
    def inputs_type(cls) -> Type[BaseModel]:
        """
        Get the inputs Pydantic model class (cached).

        Extracts from Generic[InputT, ResultT] parameters.

        Returns:
            The InputT type (must be BaseModel subclass)

        Raises:
            TypeError: If inputs type cannot be determined
        """
        if cls._cached_inputs_type is not None:
            return cls._cached_inputs_type

        inputs_cls = extract_inputs_type(cls)
        if inputs_cls is None or not (
            isinstance(inputs_cls, type) and issubclass(inputs_cls, BaseModel)
        ):
            raise TypeError(f"Could not determine inputs type for {cls.__name__}")

        cls._cached_inputs_type = inputs_cls
        return inputs_cls

    @classmethod
    def result_type(cls) -> Type[Any]:
        """
        Get the result type (cached).

        Extracts from Generic[InputT, ResultT] parameters.

        Returns:
            The ResultT type (can be Any)
        """
        if cls._cached_result_type is not None:
            return cls._cached_result_type

        result_cls = extract_result_type(cls)
        if result_cls is None:
            result_cls = Any

        cls._cached_result_type = result_cls
        return result_cls

    @classmethod
    def inputs_schema(cls) -> dict:
        """
        Get JSON Schema for inputs (for MCP integration).

        Returns:
            JSON Schema dict compatible with MCP protocol
        """
        return cls.inputs_type().model_json_schema()
