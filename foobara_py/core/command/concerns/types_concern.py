"""
TypesConcern - Type extraction and caching for Command inputs and results.

Handles:
- Extracting InputT and ResultT from Generic parameters
- Caching type information at class level
- JSON Schema generation for inputs

Pattern: Ruby Foobara's InputsType and ResultType concerns
"""

from typing import Any, ClassVar, Optional, Type, get_args, get_origin

from pydantic import BaseModel


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

        # Import Command here to avoid circular dependency
        from foobara_py.core.command.base import Command

        # Extract from Generic parameters
        for base in getattr(cls, "__orig_bases__", []):
            origin = get_origin(base)
            if origin is Command or (isinstance(origin, type) and issubclass(origin, Command)):
                args = get_args(base)
                if args and len(args) >= 1:
                    inputs_cls = args[0]
                    if isinstance(inputs_cls, type) and issubclass(inputs_cls, BaseModel):
                        cls._cached_inputs_type = inputs_cls
                        return inputs_cls

        raise TypeError(f"Could not determine inputs type for {cls.__name__}")

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

        from foobara_py.core.command.base import Command

        for base in getattr(cls, "__orig_bases__", []):
            origin = get_origin(base)
            if origin is Command or (isinstance(origin, type) and issubclass(origin, Command)):
                args = get_args(base)
                if args and len(args) >= 2:
                    cls._cached_result_type = args[1]
                    return args[1]

        cls._cached_result_type = Any
        return Any

    @classmethod
    def inputs_schema(cls) -> dict:
        """
        Get JSON Schema for inputs (for MCP integration).

        Returns:
            JSON Schema dict compatible with MCP protocol
        """
        return cls.inputs_type().model_json_schema()
