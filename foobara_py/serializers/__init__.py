"""
Serializers system for Foobara Python.

Provides rich serialization capabilities for entities, errors, and data structures.
"""

from foobara_py.serializers.base import Serializer, SerializerRegistry
from foobara_py.serializers.entity_serializers import (
    AggregateSerializer,
    AtomicSerializer,
    EntitiesToPrimaryKeysSerializer,
)
from foobara_py.serializers.error_serializer import ErrorsSerializer

__all__ = [
    "Serializer",
    "SerializerRegistry",
    "AggregateSerializer",
    "AtomicSerializer",
    "EntitiesToPrimaryKeysSerializer",
    "ErrorsSerializer",
]
