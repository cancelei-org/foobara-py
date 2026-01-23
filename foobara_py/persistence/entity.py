"""
Entity system for foobara-py.

Provides database-backed entities similar to Ruby Foobara's Entity class.

Features:
- Primary key handling
- Attribute tracking (persisted vs dirty)
- Load declarations for commands
- Serialization to primary key only
"""

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

if TYPE_CHECKING:
    from foobara_py.persistence.repository import RepositoryProtocol
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

T = TypeVar("T")
PK = TypeVar("PK")  # Primary key type


class EntityMeta(type(BaseModel)):
    """
    Metaclass for Entity classes.

    Handles:
    - Primary key field detection
    - Attribute tracking setup
    - Association descriptor setup
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        # Find primary key field
        primary_key_field = namespace.get("_primary_key_field", "id")

        # Store association descriptors before Pydantic processes them
        associations = {}
        for key, value in list(namespace.items()):
            # Import here to avoid circular dependency
            try:
                from foobara_py.persistence.associations import AssociationDescriptor

                if isinstance(value, AssociationDescriptor):
                    associations[key] = value
                    # Remove from namespace so Pydantic doesn't process them
                    del namespace[key]
            except ImportError:
                # associations module not available yet
                pass

        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Store primary key field name
        cls._primary_key_field = primary_key_field

        # Re-add association descriptors to the class after Pydantic setup
        # and ensure __set_name__ is called
        for key, descriptor in associations.items():
            descriptor.__set_name__(cls, key)
            setattr(cls, key, descriptor)

        # Auto-register entity in EntityRegistry (if not EntityBase itself)
        # Check if this class inherits from EntityBase (but is not EntityBase itself)
        if name != "EntityBase":
            try:
                # Check if cls is a subclass of EntityBase (this will work after cls is created)
                if bases and any(
                    hasattr(base, "__mro__") and "EntityBase" in [c.__name__ for c in base.__mro__]
                    for base in bases
                ):
                    EntityRegistry.register(cls)

                    # Register entity callbacks
                    from foobara_py.persistence.entity_callbacks import register_entity_callbacks

                    register_entity_callbacks(cls)
            except (ImportError, AttributeError, TypeError):
                # Skip registration if callbacks module unavailable or type check fails
                pass

        return cls


class EntityBase(BaseModel, metaclass=EntityMeta):
    """
    Base class for all entities.

    Entities are database-backed models with:
    - Primary key tracking
    - Dirty attribute tracking
    - Load/save lifecycle
    - Serialization to primary key

    Usage:
        class User(EntityBase):
            _primary_key_field = 'id'

            id: int
            name: str
            email: str

        # Create entity
        user = User(id=1, name="John", email="john@example.com")

        # Get primary key
        pk = user.primary_key  # 1

        # Check if persisted
        if user.is_persisted:
            ...
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    # Class-level configuration
    _primary_key_field: ClassVar[str] = "id"
    _repository: ClassVar[Optional["RepositoryProtocol"]] = None

    # Instance tracking
    _persisted: bool = PrivateAttr(default=False)
    _dirty_attributes: Set[str] = PrivateAttr(default_factory=set)
    _original_values: Dict[str, Any] = PrivateAttr(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        self._persisted = False
        self._dirty_attributes = set()
        self._original_values = {}

    @property
    def primary_key(self) -> Any:
        """Get the primary key value"""
        return getattr(self, self._primary_key_field)

    @property
    def is_persisted(self) -> bool:
        """Check if entity has been persisted to database"""
        return self._persisted

    @property
    def is_new(self) -> bool:
        """Check if entity is new (not persisted)"""
        return not self._persisted

    @property
    def is_dirty(self) -> bool:
        """Check if entity has unsaved changes"""
        return len(self._dirty_attributes) > 0

    @property
    def dirty_attributes(self) -> Set[str]:
        """Get set of dirty attribute names"""
        return self._dirty_attributes.copy()

    def mark_persisted(self) -> None:
        """Mark entity as persisted"""
        self._persisted = True
        self._dirty_attributes.clear()
        self._original_values.clear()

    def mark_dirty(self, *attrs: str) -> None:
        """Mark attributes as dirty"""
        for attr in attrs:
            self._dirty_attributes.add(attr)

    def to_primary_key(self) -> Any:
        """Serialize to primary key only (for API responses)"""
        return self.primary_key

    def __setattr__(self, name: str, value: Any) -> None:
        # Track dirty attributes (only for model fields)
        # Access model_fields from class, not instance (Pydantic v2.11+)
        if name in self.__class__.model_fields and self._persisted:
            current = getattr(self, name, None)
            if current != value:
                if name not in self._original_values:
                    self._original_values[name] = current
                self._dirty_attributes.add(name)
        super().__setattr__(name, value)

    @classmethod
    def from_persisted(cls, **data) -> "EntityBase":
        """Create entity instance marked as persisted"""
        instance = cls(**data)
        instance._persisted = True
        return instance

    # ==================== CRUD Instance Methods ====================

    def save(self) -> "EntityBase":
        """
        Save this entity to the repository.

        Creates new record if not persisted, updates if persisted.
        Uses the class-level _repository or global RepositoryRegistry.

        Returns:
            Self, with updated state (e.g., auto-generated primary key)

        Raises:
            ValueError: If no repository is configured

        Usage:
            user = User(name="John", email="john@example.com")
            user.save()  # Creates in database
            user.name = "Jane"
            user.save()  # Updates in database
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = self._repository or RepositoryRegistry.get(type(self))
        if not repo:
            raise ValueError(f"No repository configured for {type(self).__name__}")
        return repo.save(self)

    def delete(self) -> bool:
        """
        Delete this entity from the repository.

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If no repository is configured

        Usage:
            user = User.find(1)
            user.delete()  # Removes from database
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = self._repository or RepositoryRegistry.get(type(self))
        if not repo:
            raise ValueError(f"No repository configured for {type(self).__name__}")
        return repo.delete(self)

    def reload(self) -> "EntityBase":
        """
        Reload entity from repository, discarding unsaved changes.

        Returns:
            Self with refreshed data

        Raises:
            ValueError: If entity not persisted or not found
        """
        if not self._persisted:
            raise ValueError("Cannot reload unpersisted entity")
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = self._repository or RepositoryRegistry.get(type(self))
        if not repo:
            raise ValueError(f"No repository configured for {type(self).__name__}")
        fresh = repo.find(type(self), self.primary_key)
        if not fresh:
            raise ValueError(f"{type(self).__name__} with pk={self.primary_key} not found")
        # Update all fields from fresh data
        for field in self.__class__.model_fields:
            setattr(self, field, getattr(fresh, field))
        self._dirty_attributes.clear()
        self._original_values.clear()
        return self

    # ==================== CRUD Class Methods ====================

    @classmethod
    def create(cls, **data) -> "EntityBase":
        """
        Create and save a new entity.

        Usage:
            user = User.create(name="John", email="john@example.com")
        """
        entity = cls(**data)
        return entity.save()

    @classmethod
    def find(cls, pk: Any) -> Optional["EntityBase"]:
        """
        Find entity by primary key.

        Returns:
            Entity if found, None otherwise

        Usage:
            user = User.find(1)
            if user:
                print(user.name)
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = cls._repository or RepositoryRegistry.get(cls)
        if not repo:
            raise ValueError(f"No repository configured for {cls.__name__}")
        return repo.find(cls, pk)

    @classmethod
    def find_all(cls) -> List["EntityBase"]:
        """
        Find all entities of this type.

        Usage:
            users = User.find_all()
            for user in users:
                print(user.name)
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = cls._repository or RepositoryRegistry.get(cls)
        if not repo:
            raise ValueError(f"No repository configured for {cls.__name__}")
        return repo.find_all(cls)

    @classmethod
    def find_by(cls, **criteria) -> List["EntityBase"]:
        """
        Find entities matching criteria.

        Usage:
            users = User.find_by(role="admin")
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = cls._repository or RepositoryRegistry.get(cls)
        if not repo:
            raise ValueError(f"No repository configured for {cls.__name__}")
        return repo.find_by(cls, **criteria)

    @classmethod
    def first_by(cls, **criteria) -> Optional["EntityBase"]:
        """
        Find first entity matching criteria.

        Usage:
            admin = User.first_by(role="admin")
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = cls._repository or RepositoryRegistry.get(cls)
        if not repo:
            raise ValueError(f"No repository configured for {cls.__name__}")
        return repo.first_by(cls, **criteria)

    @classmethod
    def exists(cls, pk: Any) -> bool:
        """
        Check if entity with given primary key exists.

        Usage:
            if User.exists(1):
                print("User found")
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = cls._repository or RepositoryRegistry.get(cls)
        if not repo:
            raise ValueError(f"No repository configured for {cls.__name__}")
        return repo.exists(cls, pk)

    @classmethod
    def count(cls) -> int:
        """
        Count all entities of this type.

        Usage:
            total = User.count()
        """
        from foobara_py.persistence.repository import RepositoryRegistry

        repo = cls._repository or RepositoryRegistry.get(cls)
        if not repo:
            raise ValueError(f"No repository configured for {cls.__name__}")
        return repo.count(cls)


# Type alias for primary key
PrimaryKey = Any


# ==================== Entity Registry ====================


class EntityRegistry:
    """
    Global registry for entity types.

    Tracks all entity classes for discovery and manifest generation.
    Similar to Ruby Foobara's entity registration system.

    Usage:
        @EntityRegistry.register
        class User(EntityBase):
            id: int
            name: str

        # Or register manually
        EntityRegistry.register(User)

        # List all entities
        entities = EntityRegistry.list_entities()

        # Get manifest
        manifest = EntityRegistry.get_manifest()
    """

    _entities: Dict[str, Type[EntityBase]] = {}
    _lock = __import__("threading").Lock()

    @classmethod
    def register(cls, entity_class: Type[EntityBase]) -> Type[EntityBase]:
        """
        Register an entity class.

        Can be used as a decorator or called directly.

        Usage:
            @EntityRegistry.register
            class User(EntityBase):
                ...

            # Or
            EntityRegistry.register(User)
        """
        with cls._lock:
            name = entity_class.__name__
            cls._entities[name] = entity_class
        return entity_class

    @classmethod
    def unregister(cls, entity_class: Type[EntityBase]) -> None:
        """Unregister an entity class"""
        with cls._lock:
            name = entity_class.__name__
            cls._entities.pop(name, None)

    @classmethod
    def get(cls, name: str) -> Optional[Type[EntityBase]]:
        """Get entity class by name"""
        with cls._lock:
            return cls._entities.get(name)

    @classmethod
    def list_entities(cls) -> List[Type[EntityBase]]:
        """List all registered entity classes"""
        with cls._lock:
            return list(cls._entities.values())

    @classmethod
    def list_names(cls) -> List[str]:
        """List all registered entity names"""
        with cls._lock:
            return list(cls._entities.keys())

    @classmethod
    def get_manifest(cls) -> Dict[str, Any]:
        """
        Generate manifest for all registered entities.

        Returns dictionary with entity metadata for discovery.
        """
        with cls._lock:
            entities = {}
            for name, entity_class in cls._entities.items():
                entities[name] = cls._entity_manifest(entity_class)
            return {"entities": entities, "count": len(entities)}

    @classmethod
    def _entity_manifest(cls, entity_class: Type[EntityBase]) -> Dict[str, Any]:
        """Generate manifest for a single entity"""
        # Get field information
        fields = {}
        for field_name, field_info in entity_class.model_fields.items():
            field_type = field_info.annotation
            fields[field_name] = {
                "type": str(field_type),
                "required": field_info.is_required(),
                "default": field_info.default if field_info.default is not None else None,
            }

        return {
            "name": entity_class.__name__,
            "primary_key_field": entity_class._primary_key_field,
            "fields": fields,
            "schema": entity_class.model_json_schema(),
        }

    @classmethod
    def clear(cls) -> None:
        """Clear all registered entities"""
        with cls._lock:
            cls._entities.clear()


def register_entity(entity_class: Type[EntityBase]) -> Type[EntityBase]:
    """
    Decorator to register an entity class.

    Usage:
        @register_entity
        class User(EntityBase):
            id: int
            name: str
    """
    return EntityRegistry.register(entity_class)


# ==================== Load Declarations ====================


@dataclass(slots=True)
class LoadSpec:
    """
    Specification for loading an entity in a command.

    Similar to Ruby Foobara's `load Entity, from: :input, into: :var`

    Usage:
        class UpdateUser(Command[...]):
            _loads = [
                LoadSpec(User, from_input='user_id', into='user')
            ]
    """

    entity_class: Type[EntityBase]
    from_input: str  # Input field containing primary key
    into: str  # Attribute name to store loaded entity
    required: bool = True  # Fail if not found


def load(
    entity_class: Type[EntityBase], from_input: str, into: str, required: bool = True
) -> LoadSpec:
    """
    Declare entity loading for a command.

    Usage:
        @command(domain="Users")
        class UpdateUser(Command[...]):
            _loads = [
                load(User, from_input='user_id', into='user'),
                load(Account, from_input='account_id', into='account', required=False),
            ]
    """
    return LoadSpec(entity_class=entity_class, from_input=from_input, into=into, required=required)


# ==================== Entity Decorator ====================


def entity(primary_key: str = "id", repository: "RepositoryProtocol" = None) -> Callable:
    """
    Decorator to configure an entity class.

    Usage:
        @entity(primary_key='id')
        class User(EntityBase):
            id: int
            name: str
            email: str
    """

    def decorator(cls: Type[EntityBase]) -> Type[EntityBase]:
        cls._primary_key_field = primary_key
        if repository:
            cls._repository = repository
        return cls

    return decorator


# ==================== Entity for Generics ====================

Entity = EntityBase  # Alias for backward compatibility


# ==================== Model (Value Objects) ====================


class Model(BaseModel):
    """
    Base class for value objects (models without identity).

    Models are embedded data structures that:
    - Have no primary key
    - Are compared by value (all attributes)
    - Are typically embedded within entities
    - Are immutable by default

    Unlike Entities, Models:
    - Cannot be persisted independently
    - Have no dirty tracking
    - Are identified by their attribute values, not a primary key

    Usage:
        class Address(Model):
            street: str
            city: str
            country: str
            postal_code: str

        class User(EntityBase):
            id: int
            name: str
            address: Address  # Embedded model

        # Create model
        addr = Address(street="123 Main St", city="NYC", country="USA", postal_code="10001")

        # Models are compared by value
        addr2 = Address(street="123 Main St", city="NYC", country="USA", postal_code="10001")
        assert addr == addr2  # True - same values

        # Models are hashable (can be used in sets/dicts)
        addresses = {addr, addr2}  # Only one entry
    """

    model_config = ConfigDict(
        frozen=True,  # Immutable by default
        validate_assignment=True,
        extra="forbid",
    )

    def __hash__(self) -> int:
        """Hash based on all field values"""
        return hash(tuple(sorted(self.model_dump().items())))

    def with_updates(self, **updates) -> "Model":
        """
        Create a new Model instance with updated values.

        Since Models are immutable, this returns a new instance.

        Usage:
            new_addr = addr.with_updates(city="Boston")
        """
        current = self.model_dump()
        current.update(updates)
        return self.__class__(**current)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Model":
        """Create model from dictionary"""
        return cls(**data)


class MutableModel(BaseModel):
    """
    Mutable variant of Model for cases where immutability is not desired.

    Use this for embedded objects that need to be modified in place.

    Usage:
        class Settings(MutableModel):
            theme: str = "light"
            notifications: bool = True

        settings = Settings()
        settings.theme = "dark"  # Allowed
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True, extra="forbid")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MutableModel":
        """Create model from dictionary"""
        return cls(**data)
