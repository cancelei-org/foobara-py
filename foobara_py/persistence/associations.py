"""
Entity associations for Foobara Python.

Provides relationship descriptors for entities:
- has_many: One-to-many relationships
- belongs_to: Many-to-one relationships
- has_one: One-to-one relationships

Usage:
    class User(EntityBase):
        id: int
        name: str
        posts: list = has_many("Post", foreign_key="user_id")
        profile: Optional["Profile"] = has_one("Profile", foreign_key="user_id")

    class Post(EntityBase):
        id: int
        title: str
        user_id: int
        user: Optional[User] = belongs_to(User, foreign_key="user_id")
"""

import weakref
from functools import cached_property
from typing import TYPE_CHECKING, Any, Generic, List, Optional, Type, TypeVar, Union

if TYPE_CHECKING:
    from foobara_py.persistence.entity import EntityBase
    from foobara_py.persistence.repository import RepositoryProtocol

T = TypeVar("T", bound="EntityBase")


class AssociationDescriptor(Generic[T]):
    """
    Base descriptor for entity associations.

    Handles lazy loading and caching of associated entities.
    """

    def __init__(
        self,
        entity_class: Union[Type[T], str],
        foreign_key: Optional[str] = None,
        lazy: bool = True,
    ):
        """
        Initialize association descriptor.

        Args:
            entity_class: The associated entity class or class name (for forward refs)
            foreign_key: Foreign key field name
            lazy: Whether to lazy load the association
        """
        self.entity_class = entity_class
        self.foreign_key = foreign_key
        self.lazy = lazy
        self.name = None
        self._cache_attr = None

    def __set_name__(self, owner: type, name: str):
        """Called when descriptor is assigned to a class attribute"""
        self.name = name
        self._cache_attr = f"_association_cache_{name}"

        # Infer foreign key if not provided
        if self.foreign_key is None:
            self.foreign_key = self._infer_foreign_key(owner, name)

    def _infer_foreign_key(self, owner: type, name: str) -> str:
        """Infer foreign key name from association"""
        # Override in subclasses
        return f"{name}_id"

    def _get_entity_class(self) -> Type[T]:
        """Resolve entity class from string or type"""
        if isinstance(self.entity_class, str):
            # Use EntityRegistry to resolve class name
            from foobara_py.persistence.entity import EntityRegistry

            entity_cls = EntityRegistry.get(self.entity_class)
            if entity_cls:
                return entity_cls
            raise ValueError(
                f"Could not resolve entity class: {self.entity_class}. Make sure the entity is registered in EntityRegistry."
            )
        return self.entity_class

    def _get_repository(self, obj: "EntityBase") -> "RepositoryProtocol":
        """Get repository for the entity"""
        from foobara_py.persistence.repository import RepositoryRegistry

        entity_cls = self._get_entity_class()
        repo = entity_cls._repository or RepositoryRegistry.get(entity_cls)
        if not repo:
            raise ValueError(f"No repository configured for {entity_cls.__name__}")
        return repo

    def _get_cache(self, obj: "EntityBase") -> Any:
        """Get cached value"""
        return getattr(obj, self._cache_attr, None)

    def _set_cache(self, obj: "EntityBase", value: Any) -> None:
        """Set cached value"""
        setattr(obj, self._cache_attr, value)


class HasMany(AssociationDescriptor[T]):
    """
    Descriptor for one-to-many relationships.

    The owning entity has many associated entities.
    Foreign key is stored on the associated entities.

    Usage:
        class User(EntityBase):
            id: int
            posts: list = has_many("Post", foreign_key="user_id")

        user = User.find(1)
        posts = user.posts  # List[Post]
    """

    def _infer_foreign_key(self, owner: type, name: str) -> str:
        """Foreign key is on the associated entity"""
        return f"{owner.__name__.lower()}_id"

    def __get__(self, obj: Optional["EntityBase"], objtype=None) -> Union["HasMany[T]", List[T]]:
        """Get associated entities"""
        if obj is None:
            return self

        # Check cache
        if self.lazy:
            cached = self._get_cache(obj)
            if cached is not None:
                return cached

        # Load from repository
        repo = self._get_repository(obj)
        entity_cls = self._get_entity_class()

        # Find all entities where foreign_key == obj.primary_key
        entities = repo.find_by(entity_cls, **{self.foreign_key: obj.primary_key})

        # Cache the result
        if self.lazy:
            self._set_cache(obj, entities)

        return entities

    def __set__(self, obj: "EntityBase", value: List[T]) -> None:
        """Set associated entities (updates cache)"""
        self._set_cache(obj, value)


class BelongsTo(AssociationDescriptor[T]):
    """
    Descriptor for many-to-one relationships.

    The owning entity belongs to one associated entity.
    Foreign key is stored on the owning entity.

    Usage:
        class Post(EntityBase):
            id: int
            user_id: int
            user: Optional[User] = belongs_to(User, foreign_key="user_id")

        post = Post.find(1)
        user = post.user  # User
    """

    def _infer_foreign_key(self, owner: type, name: str) -> str:
        """Foreign key is on the owning entity"""
        return f"{name}_id"

    def __get__(
        self, obj: Optional["EntityBase"], objtype=None
    ) -> Union["BelongsTo[T]", Optional[T]]:
        """Get associated entity"""
        if obj is None:
            return self

        # Check cache
        if self.lazy:
            cached = self._get_cache(obj)
            if cached is not None:
                return cached

        # Get foreign key value
        fk_value = getattr(obj, self.foreign_key, None)
        if fk_value is None:
            return None

        # Load from repository
        repo = self._get_repository(obj)
        entity_cls = self._get_entity_class()
        entity = repo.find(entity_cls, fk_value)

        # Cache the result
        if self.lazy:
            self._set_cache(obj, entity)

        return entity

    def __set__(self, obj: "EntityBase", value: Optional[T]) -> None:
        """Set associated entity (updates cache and foreign key)"""
        self._set_cache(obj, value)

        # Update foreign key if entity provided
        if value is not None:
            setattr(obj, self.foreign_key, value.primary_key)
        else:
            setattr(obj, self.foreign_key, None)


class HasOne(AssociationDescriptor[T]):
    """
    Descriptor for one-to-one relationships.

    The owning entity has one associated entity.
    Foreign key is stored on the associated entity.

    Usage:
        class User(EntityBase):
            id: int
            profile: Optional["Profile"] = has_one("Profile", foreign_key="user_id")

        user = User.find(1)
        profile = user.profile  # Profile or None
    """

    def _infer_foreign_key(self, owner: type, name: str) -> str:
        """Foreign key is on the associated entity"""
        return f"{owner.__name__.lower()}_id"

    def __get__(self, obj: Optional["EntityBase"], objtype=None) -> Union["HasOne[T]", Optional[T]]:
        """Get associated entity"""
        if obj is None:
            return self

        # Check cache
        if self.lazy:
            cached = self._get_cache(obj)
            if cached is not None:
                return cached

        # Load from repository
        repo = self._get_repository(obj)
        entity_cls = self._get_entity_class()

        # Find the entity where foreign_key == obj.primary_key
        entity = repo.first_by(entity_cls, **{self.foreign_key: obj.primary_key})

        # Cache the result
        if self.lazy:
            self._set_cache(obj, entity)

        return entity

    def __set__(self, obj: "EntityBase", value: Optional[T]) -> None:
        """Set associated entity (updates cache)"""
        self._set_cache(obj, value)


# Convenience functions for creating associations


def has_many(
    entity_class: Union[Type[T], str], foreign_key: Optional[str] = None, lazy: bool = True
) -> List[T]:
    """
    Create a has_many association.

    Args:
        entity_class: The associated entity class or name
        foreign_key: Foreign key field (inferred if not provided)
        lazy: Whether to lazy load (default: True)

    Returns:
        HasMany descriptor

    Usage:
        class User(EntityBase):
            posts: list = has_many("Post")
    """
    return HasMany(entity_class, foreign_key, lazy)


def belongs_to(
    entity_class: Union[Type[T], str], foreign_key: Optional[str] = None, lazy: bool = True
) -> Optional[T]:
    """
    Create a belongs_to association.

    Args:
        entity_class: The associated entity class or name
        foreign_key: Foreign key field (inferred if not provided)
        lazy: Whether to lazy load (default: True)

    Returns:
        BelongsTo descriptor

    Usage:
        class Post(EntityBase):
            user: Optional[User] = belongs_to(User)
    """
    return BelongsTo(entity_class, foreign_key, lazy)


def has_one(
    entity_class: Union[Type[T], str], foreign_key: Optional[str] = None, lazy: bool = True
) -> Optional[T]:
    """
    Create a has_one association.

    Args:
        entity_class: The associated entity class or name
        foreign_key: Foreign key field (inferred if not provided)
        lazy: Whether to lazy load (default: True)

    Returns:
        HasOne descriptor

    Usage:
        class User(EntityBase):
            profile: Optional[Profile] = has_one("Profile")
    """
    return HasOne(entity_class, foreign_key, lazy)


# Eager loading support


class EagerLoader:
    """
    Eager load associations to avoid N+1 queries.

    Usage:
        users = User.find_all()
        users_with_posts = EagerLoader.load(users, "posts")
    """

    @staticmethod
    def load(entities: List["EntityBase"], *association_names: str) -> List["EntityBase"]:
        """
        Eager load specified associations.

        Args:
            entities: List of entities
            *association_names: Association names to load

        Returns:
            Same list of entities with associations loaded
        """
        if not entities:
            return entities

        for assoc_name in association_names:
            # Get the association descriptor
            entity_class = type(entities[0])
            descriptor = getattr(entity_class, assoc_name, None)

            if descriptor is None:
                raise ValueError(f"Association {assoc_name} not found on {entity_class.__name__}")

            # Load associations based on type
            if isinstance(descriptor, HasMany):
                EagerLoader._eager_load_has_many(entities, assoc_name, descriptor)
            elif isinstance(descriptor, BelongsTo):
                EagerLoader._eager_load_belongs_to(entities, assoc_name, descriptor)
            elif isinstance(descriptor, HasOne):
                EagerLoader._eager_load_has_one(entities, assoc_name, descriptor)

        return entities

    @staticmethod
    def _eager_load_has_many(
        entities: List["EntityBase"], assoc_name: str, descriptor: HasMany
    ) -> None:
        """Eager load has_many association"""
        from foobara_py.persistence.repository import RepositoryRegistry

        entity_cls = descriptor._get_entity_class()
        repo = entity_cls._repository or RepositoryRegistry.get(entity_cls)

        # Collect all IDs
        entity_ids = [e.primary_key for e in entities]

        # Load all associated records in one query
        # Note: This requires repository support for IN queries
        all_associated = []
        for entity_id in entity_ids:
            associated = repo.find_by(entity_cls, **{descriptor.foreign_key: entity_id})
            all_associated.extend([(entity_id, a) for a in associated])

        # Group by parent ID
        grouped = {}
        for parent_id, associated in all_associated:
            if parent_id not in grouped:
                grouped[parent_id] = []
            grouped[parent_id].append(associated)

        # Set cached values
        for entity in entities:
            associated_list = grouped.get(entity.primary_key, [])
            descriptor._set_cache(entity, associated_list)

    @staticmethod
    def _eager_load_belongs_to(
        entities: List["EntityBase"], assoc_name: str, descriptor: BelongsTo
    ) -> None:
        """Eager load belongs_to association"""
        from foobara_py.persistence.repository import RepositoryRegistry

        entity_cls = descriptor._get_entity_class()
        repo = entity_cls._repository or RepositoryRegistry.get(entity_cls)

        # Collect all foreign key values
        fk_values = {
            getattr(e, descriptor.foreign_key)
            for e in entities
            if getattr(e, descriptor.foreign_key) is not None
        }

        # Load all associated records
        associated_map = {}
        for fk_value in fk_values:
            associated = repo.find(entity_cls, fk_value)
            if associated:
                associated_map[fk_value] = associated

        # Set cached values
        for entity in entities:
            fk_value = getattr(entity, descriptor.foreign_key)
            if fk_value:
                descriptor._set_cache(entity, associated_map.get(fk_value))

    @staticmethod
    def _eager_load_has_one(
        entities: List["EntityBase"], assoc_name: str, descriptor: HasOne
    ) -> None:
        """Eager load has_one association"""
        # Similar to has_many but only one result per parent
        from foobara_py.persistence.repository import RepositoryRegistry

        entity_cls = descriptor._get_entity_class()
        repo = entity_cls._repository or RepositoryRegistry.get(entity_cls)

        # Collect all IDs
        entity_ids = [e.primary_key for e in entities]

        # Load all associated records
        associated_map = {}
        for entity_id in entity_ids:
            associated = repo.first_by(entity_cls, **{descriptor.foreign_key: entity_id})
            if associated:
                associated_map[entity_id] = associated

        # Set cached values
        for entity in entities:
            descriptor._set_cache(entity, associated_map.get(entity.primary_key))
