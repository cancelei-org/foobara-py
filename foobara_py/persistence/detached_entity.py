"""
Detached entities for Foobara Python.

Represents immutable entities fetched from remote systems.
Unlike regular entities, detached entities:
- Cannot be persisted locally (no CRUD operations)
- Are immutable (frozen)
- Track their source system
- Used for data imported from external Foobara services

Usage:
    class RemoteUser(DetachedEntity):
        _primary_key_field = 'id'
        _source_system = 'external-api'

        id: int
        name: str
        email: str

    # Create from remote data
    user = RemoteUser.from_remote(
        {'id': 1, 'name': 'John', 'email': 'john@example.com'},
        source='api.example.com'
    )

    # Access data
    print(user.name)  # "John"
    print(user.primary_key)  # 1
    print(user.source_system)  # "api.example.com"

    # Cannot modify (frozen)
    user.name = "Jane"  # Raises ValidationError

    # Cannot persist
    user.save()  # Raises NotImplementedError
"""

from typing import Any, ClassVar, Optional

from pydantic import BaseModel, ConfigDict, PrivateAttr


class DetachedEntity(BaseModel):
    """
    Immutable entity from remote system.

    DetachedEntities represent data fetched from external systems that:
    - Should not be modified locally
    - Cannot be persisted to local storage
    - Maintain reference to their source system

    This is useful for:
    - Remote imports from other Foobara services
    - Read-only data from external APIs
    - Cached data that should not be modified
    - Data from systems where you don't have write access
    """

    model_config = ConfigDict(
        frozen=True,  # Makes entity immutable
        extra="forbid",
        validate_assignment=True,
    )

    # Class-level configuration
    _primary_key_field: ClassVar[str] = "id"
    _source_system: ClassVar[Optional[str]] = None

    # Instance-level tracking (private)
    _instance_source: Optional[str] = PrivateAttr(default=None)

    @property
    def primary_key(self) -> Any:
        """Get the primary key value"""
        return getattr(self, self._primary_key_field)

    @property
    def source_system(self) -> Optional[str]:
        """Get the source system this entity was loaded from"""
        # Instance source takes precedence over class-level
        if self._instance_source:
            return self._instance_source
        return self._source_system

    @classmethod
    def from_remote(cls, data: dict, source: str) -> "DetachedEntity":
        """
        Create detached entity from remote system data.

        Args:
            data: Entity data from remote system
            source: Source system identifier (e.g., "api.example.com")

        Returns:
            Detached entity instance with source tracking

        Usage:
            user = RemoteUser.from_remote(
                {'id': 1, 'name': 'John'},
                source='external-api'
            )
        """
        instance = cls(**data)
        # Set private attribute on frozen model using object.__setattr__
        object.__setattr__(instance, "_instance_source", source)
        return instance

    def __hash__(self) -> int:
        """
        Hash based on class and primary key.

        This allows detached entities to be used in sets and as dict keys.
        """
        return hash((self.__class__.__name__, self.primary_key))

    def __eq__(self, other: object) -> bool:
        """
        Compare detached entities by class and primary key.

        Two detached entities are equal if they have the same class
        and primary key, regardless of source system.
        """
        if not isinstance(other, DetachedEntity):
            return False
        return self.__class__ == other.__class__ and self.primary_key == other.primary_key

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation of entity
        """
        return self.model_dump()

    def to_json(self) -> str:
        """
        Convert to JSON string.

        Returns:
            JSON representation of entity
        """
        return self.model_dump_json()

    # Block persistence operations

    def save(self) -> "DetachedEntity":
        """
        Detached entities cannot be saved.

        Raises:
            NotImplementedError: Always - detached entities are read-only
        """
        raise NotImplementedError(
            f"DetachedEntity {self.__class__.__name__} cannot be saved. "
            "It represents immutable data from remote system "
            f"'{self.source_system or 'unknown'}'."
        )

    def delete(self) -> bool:
        """
        Detached entities cannot be deleted.

        Raises:
            NotImplementedError: Always - detached entities are read-only
        """
        raise NotImplementedError(
            f"DetachedEntity {self.__class__.__name__} cannot be deleted. "
            "It represents immutable data from remote system "
            f"'{self.source_system or 'unknown'}'."
        )

    def reload(self) -> "DetachedEntity":
        """
        Detached entities cannot be reloaded.

        Raises:
            NotImplementedError: Always - detached entities have no repository
        """
        raise NotImplementedError(
            f"DetachedEntity {self.__class__.__name__} cannot be reloaded. "
            "It represents immutable data from remote system "
            f"'{self.source_system or 'unknown'}'."
        )

    @classmethod
    def create(cls, **data) -> "DetachedEntity":
        """
        Detached entities cannot be created via CRUD.

        Use from_remote() instead to create from external data.

        Raises:
            NotImplementedError: Always - use from_remote() instead
        """
        raise NotImplementedError(
            f"DetachedEntity {cls.__name__} cannot be created via create(). "
            "Use from_remote() to create from external system data."
        )

    @classmethod
    def find(cls, pk: Any) -> Optional["DetachedEntity"]:
        """
        Detached entities cannot be found via repository.

        Raises:
            NotImplementedError: Always - no repository available
        """
        raise NotImplementedError(
            f"DetachedEntity {cls.__name__} cannot be found via find(). "
            "Detached entities have no local repository."
        )

    @classmethod
    def find_all(cls) -> list["DetachedEntity"]:
        """
        Detached entities cannot be queried.

        Raises:
            NotImplementedError: Always - no repository available
        """
        raise NotImplementedError(
            f"DetachedEntity {cls.__name__} cannot be queried via find_all(). "
            "Detached entities have no local repository."
        )


def detached_entity(primary_key: str = "id", source_system: Optional[str] = None) -> type:
    """
    Decorator to configure a detached entity class.

    Args:
        primary_key: Primary key field name (default: 'id')
        source_system: Source system identifier (optional)

    Returns:
        Decorator function

    Usage:
        @detached_entity(primary_key='user_id', source_system='external-api')
        class RemoteUser(DetachedEntity):
            user_id: int
            name: str
            email: str
    """

    def decorator(cls: type[DetachedEntity]) -> type[DetachedEntity]:
        cls._primary_key_field = primary_key
        if source_system:
            cls._source_system = source_system
        return cls

    return decorator
