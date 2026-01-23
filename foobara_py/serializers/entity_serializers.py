"""
Entity serializers for different representation needs.

Provides multiple strategies for serializing entities:
- AggregateSerializer: Full entity with all associations loaded
- AtomicSerializer: Entity with associations as primary keys only
- EntitiesToPrimaryKeysSerializer: Recursively convert all entities to PKs
"""

from typing import Any, Dict, List

from pydantic import BaseModel

from foobara_py.persistence.entity import EntityBase
from foobara_py.serializers.base import Serializer


class AggregateSerializer(Serializer[EntityBase]):
    """
    Serialize entity with all associations fully loaded.

    This serializer includes all nested entities and models
    in their full form, similar to a "detailed" or "expanded" view.

    Useful for:
    - API responses that need complete data
    - Data exports
    - Admin interfaces

    Usage:
        user = User.find(1)  # Has posts, comments, etc.
        serializer = AggregateSerializer()
        data = serializer.serialize(user)
        # Returns: {"id": 1, "name": "John", "posts": [{"id": 1, "title": "..."}, ...]}
    """

    def serialize(self, obj: EntityBase) -> Dict[str, Any]:
        """
        Serialize entity with all associations.

        Returns complete dictionary representation including
        all nested entities and models.
        """
        if not isinstance(obj, EntityBase):
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            return obj

        result = {}

        # Serialize all fields
        for field_name, field_info in obj.__class__.model_fields.items():
            value = getattr(obj, field_name)

            # Recursively serialize nested entities and models
            if isinstance(value, EntityBase):
                result[field_name] = self.serialize(value)
            elif isinstance(value, BaseModel):
                result[field_name] = value.model_dump()
            elif isinstance(value, list):
                result[field_name] = [
                    self.serialize(item) if isinstance(item, (EntityBase, BaseModel)) else item
                    for item in value
                ]
            elif isinstance(value, dict):
                result[field_name] = {
                    k: self.serialize(v) if isinstance(v, (EntityBase, BaseModel)) else v
                    for k, v in value.items()
                }
            else:
                result[field_name] = value

        return result

    @classmethod
    def can_serialize(cls, obj: Any) -> bool:
        """Can serialize EntityBase instances"""
        return isinstance(obj, EntityBase)

    @classmethod
    def priority(cls) -> int:
        """Lower priority than Atomic (use Atomic by default)"""
        return 5


class AtomicSerializer(Serializer[EntityBase]):
    """
    Serialize entity with associations as primary keys only.

    This serializer represents associations by their primary keys
    instead of full nested objects, similar to a "compact" or "reference" view.

    Useful for:
    - API responses with minimal nesting
    - Avoiding circular references
    - Reducing payload size

    Usage:
        user = User.find(1)  # Has posts with post.id = 1, 2, 3
        serializer = AtomicSerializer()
        data = serializer.serialize(user)
        # Returns: {"id": 1, "name": "John", "posts": [1, 2, 3]}
    """

    def serialize(self, obj: EntityBase) -> Dict[str, Any]:
        """
        Serialize entity with associations as PKs.

        Nested entities are represented by their primary keys,
        while other values are serialized normally.
        """
        if not isinstance(obj, EntityBase):
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            return obj

        result = {}

        # Serialize all fields
        for field_name, field_info in obj.__class__.model_fields.items():
            value = getattr(obj, field_name)

            # Convert entities to primary keys
            if isinstance(value, EntityBase):
                result[field_name] = value.primary_key
            elif isinstance(value, BaseModel):
                # Non-entity models are serialized normally
                result[field_name] = value.model_dump()
            elif isinstance(value, list):
                result[field_name] = [
                    item.primary_key
                    if isinstance(item, EntityBase)
                    else (item.model_dump() if isinstance(item, BaseModel) else item)
                    for item in value
                ]
            elif isinstance(value, dict):
                result[field_name] = {
                    k: (
                        v.primary_key
                        if isinstance(v, EntityBase)
                        else (v.model_dump() if isinstance(v, BaseModel) else v)
                    )
                    for k, v in value.items()
                }
            else:
                result[field_name] = value

        return result

    @classmethod
    def can_serialize(cls, obj: Any) -> bool:
        """Can serialize EntityBase instances"""
        return isinstance(obj, EntityBase)

    @classmethod
    def priority(cls) -> int:
        """Default priority for entity serialization"""
        return 10


class EntitiesToPrimaryKeysSerializer(Serializer[Any]):
    """
    Recursively convert ALL entities to primary keys.

    This serializer deeply traverses data structures and converts
    every entity (at any depth) to its primary key.

    Useful for:
    - Preparing data for external APIs
    - Database storage where relations are by ID
    - Preventing accidental data leakage

    Usage:
        data = {
            "user": user_entity,
            "posts": [post1_entity, post2_entity],
            "metadata": {"author": author_entity}
        }
        serializer = EntitiesToPrimaryKeysSerializer()
        result = serializer.serialize(data)
        # Returns: {
        #     "user": 1,
        #     "posts": [10, 20],
        #     "metadata": {"author": 5}
        # }
    """

    def serialize(self, obj: Any) -> Any:
        """
        Recursively convert all entities to primary keys.

        Handles:
        - Entities -> primary keys
        - Dicts -> recursively process values
        - Lists -> recursively process items
        - Pydantic models -> model_dump() then recurse
        - Primitives -> pass through
        """
        if isinstance(obj, EntityBase):
            return obj.primary_key

        if isinstance(obj, BaseModel):
            # Convert to dict first, then recurse
            return self.serialize(obj.model_dump())

        if isinstance(obj, dict):
            return {k: self.serialize(v) for k, v in obj.items()}

        if isinstance(obj, (list, tuple)):
            return [self.serialize(item) for item in obj]

        if isinstance(obj, set):
            return {self.serialize(item) for item in obj}

        # Primitive types pass through
        return obj

    @classmethod
    def can_serialize(cls, obj: Any) -> bool:
        """Can serialize any object"""
        return True

    @classmethod
    def priority(cls) -> int:
        """Low priority - only use when explicitly requested"""
        return 1


# Auto-register serializers
from foobara_py.serializers.base import SerializerRegistry

SerializerRegistry.register(AggregateSerializer)
SerializerRegistry.register(AtomicSerializer)
SerializerRegistry.register(EntitiesToPrimaryKeysSerializer)
