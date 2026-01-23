"""
Base serializer class and registry for Foobara Python.

Provides the foundation for all serialization strategies.
"""

import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar

T = TypeVar("T")


class Serializer(ABC, Generic[T]):
    """
    Base class for all serializers.

    Serializers transform data structures into specific formats
    for storage, transmission, or display.

    Features:
    - Generic type safety with TypeVar T
    - Bidirectional serialization (to/from)
    - Registry integration for automatic selection
    - Extensible for custom serialization logic

    Usage:
        class MySerializer(Serializer[MyModel]):
            def serialize(self, obj: MyModel) -> dict:
                return {"id": obj.id, "name": obj.name}

            def deserialize(self, data: dict) -> MyModel:
                return MyModel(**data)
    """

    @abstractmethod
    def serialize(self, obj: T) -> Any:
        """
        Serialize object to target format.

        Args:
            obj: The object to serialize

        Returns:
            Serialized representation (typically dict or JSON-compatible)
        """
        pass

    def deserialize(self, data: Any) -> T:
        """
        Deserialize data back to object.

        Optional - not all serializers support deserialization.

        Args:
            data: Serialized data

        Returns:
            Deserialized object

        Raises:
            NotImplementedError: If deserialization not supported
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support deserialization")

    @classmethod
    def can_serialize(cls, obj: Any) -> bool:
        """
        Check if this serializer can handle the given object.

        Override to implement custom type checking.

        Args:
            obj: Object to check

        Returns:
            True if this serializer can handle the object
        """
        return True

    @classmethod
    def priority(cls) -> int:
        """
        Priority for serializer selection (higher = higher priority).

        When multiple serializers can handle an object, the one
        with highest priority is selected.

        Returns:
            Priority value (default: 0)
        """
        return 0


class SerializerRegistry:
    """
    Global registry for serializers.

    Manages serializer registration and automatic selection
    based on object type.

    Usage:
        # Register serializer
        SerializerRegistry.register(MySerializer)

        # Find serializer for object
        serializer = SerializerRegistry.find_serializer(my_obj)

        # Serialize with automatic selection
        data = SerializerRegistry.serialize(my_obj)
    """

    _serializers: Dict[str, Type[Serializer]] = {}
    _serializer_list: list[Type[Serializer]] = []
    _lock = threading.Lock()

    @classmethod
    def register(cls, serializer_class: Type[Serializer]) -> Type[Serializer]:
        """
        Register a serializer class.

        Args:
            serializer_class: The serializer class to register

        Returns:
            The serializer class (for decorator usage)
        """
        with cls._lock:
            name = serializer_class.__name__
            cls._serializers[name] = serializer_class
            cls._serializer_list.append(serializer_class)
            # Sort by priority (descending)
            cls._serializer_list.sort(key=lambda s: s.priority(), reverse=True)
        return serializer_class

    @classmethod
    def unregister(cls, serializer_class: Type[Serializer]) -> None:
        """Unregister a serializer"""
        with cls._lock:
            name = serializer_class.__name__
            cls._serializers.pop(name, None)
            if serializer_class in cls._serializer_list:
                cls._serializer_list.remove(serializer_class)

    @classmethod
    def get(cls, name: str) -> Optional[Type[Serializer]]:
        """Get serializer by name"""
        with cls._lock:
            return cls._serializers.get(name)

    @classmethod
    def find_serializer(cls, obj: Any) -> Optional[Type[Serializer]]:
        """
        Find the best serializer for an object.

        Selects the highest-priority serializer that can handle the object.

        Args:
            obj: Object to serialize

        Returns:
            Serializer class, or None if no serializer found
        """
        with cls._lock:
            for serializer_class in cls._serializer_list:
                if serializer_class.can_serialize(obj):
                    return serializer_class
            return None

    @classmethod
    def serialize(cls, obj: Any, serializer_class: Type[Serializer] = None) -> Any:
        """
        Serialize object with automatic or explicit serializer selection.

        Args:
            obj: Object to serialize
            serializer_class: Optional explicit serializer class

        Returns:
            Serialized data

        Raises:
            ValueError: If no serializer found
        """
        if serializer_class is None:
            serializer_class = cls.find_serializer(obj)
            if serializer_class is None:
                raise ValueError(f"No serializer found for {type(obj).__name__}")

        serializer = serializer_class()
        return serializer.serialize(obj)

    @classmethod
    def deserialize(cls, data: Any, serializer_class: Type[Serializer]) -> Any:
        """
        Deserialize data using specified serializer.

        Args:
            data: Serialized data
            serializer_class: Serializer class to use

        Returns:
            Deserialized object
        """
        serializer = serializer_class()
        return serializer.deserialize(data)

    @classmethod
    def list_serializers(cls) -> list[Type[Serializer]]:
        """List all registered serializers"""
        with cls._lock:
            return cls._serializer_list.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered serializers (for testing)"""
        with cls._lock:
            cls._serializers.clear()
            cls._serializer_list.clear()


def serializer(priority: int = 0):
    """
    Decorator to register a serializer with optional priority.

    Usage:
        @serializer(priority=10)
        class MySerializer(Serializer[MyModel]):
            def serialize(self, obj: MyModel) -> dict:
                ...
    """

    def decorator(cls: Type[Serializer]) -> Type[Serializer]:
        # Set priority
        original_priority = cls.priority

        @classmethod
        def new_priority(cls) -> int:
            return priority

        cls.priority = new_priority

        # Auto-register
        SerializerRegistry.register(cls)

        return cls

    return decorator
