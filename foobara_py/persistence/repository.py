"""
Repository pattern for entity persistence.

Provides pluggable storage backends for entities.
"""

import threading
from abc import ABC, abstractmethod
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Type,
    TypeVar,
    runtime_checkable,
)

from foobara_py.persistence.entity import EntityBase, PrimaryKey


@runtime_checkable
class RepositoryProtocol(Protocol):
    """Protocol defining repository interface"""

    def find(self, entity_class: Type[EntityBase], pk: PrimaryKey) -> Optional[EntityBase]:
        """Find entity by primary key"""
        ...

    def find_all(self, entity_class: Type[EntityBase]) -> List[EntityBase]:
        """Find all entities of a type"""
        ...

    def save(self, entity: EntityBase) -> EntityBase:
        """Save entity (create or update)"""
        ...

    def delete(self, entity: EntityBase) -> bool:
        """Delete entity, returns True if deleted"""
        ...

    def exists(self, entity_class: Type[EntityBase], pk: PrimaryKey) -> bool:
        """Check if entity exists"""
        ...


class Repository(ABC):
    """
    Abstract base class for repositories.

    Provides common functionality for entity storage.
    Subclass and implement abstract methods for specific storage backends.
    """

    @abstractmethod
    def find(self, entity_class: Type[EntityBase], pk: PrimaryKey) -> Optional[EntityBase]:
        """Find entity by primary key"""
        pass

    @abstractmethod
    def find_all(self, entity_class: Type[EntityBase]) -> List[EntityBase]:
        """Find all entities of a type"""
        pass

    @abstractmethod
    def save(self, entity: EntityBase) -> EntityBase:
        """Save entity (create or update)"""
        pass

    @abstractmethod
    def delete(self, entity: EntityBase) -> bool:
        """Delete entity"""
        pass

    def exists(self, entity_class: Type[EntityBase], pk: PrimaryKey) -> bool:
        """Check if entity exists (default implementation)"""
        return self.find(entity_class, pk) is not None

    def find_by(self, entity_class: Type[EntityBase], **criteria) -> List[EntityBase]:
        """
        Find entities matching criteria.

        Default implementation filters find_all() results in O(n) time.
        For production use with large datasets, override this method
        in your repository subclass to use optimized database queries.

        Example:
            class UserRepository(Repository):
                def find_by(self, entity_class, **criteria):
                    # Use database indexes for O(log n) or O(1) lookup
                    return self.driver.find_all_by(**criteria)

        Args:
            entity_class: Entity type to query
            **criteria: Field/value pairs to match

        Returns:
            List of matching entities
        """
        results = []
        for entity in self.find_all(entity_class):
            matches = all(
                getattr(entity, field, None) == value for field, value in criteria.items()
            )
            if matches:
                results.append(entity)
        return results

    def first_by(self, entity_class: Type[EntityBase], **criteria) -> Optional[EntityBase]:
        """Find first entity matching criteria"""
        results = self.find_by(entity_class, **criteria)
        return results[0] if results else None

    def count(self, entity_class: Type[EntityBase]) -> int:
        """Count entities of a type"""
        return len(self.find_all(entity_class))


class InMemoryRepository(Repository):
    """
    In-memory repository for testing and development.

    Stores entities in memory using a dict keyed by (entity_class, pk).
    Thread-safe for concurrent access.
    """

    __slots__ = ("_storage", "_lock", "_auto_increment")

    def __init__(self):
        self._storage: Dict[tuple, EntityBase] = {}
        self._lock = threading.RLock()
        self._auto_increment: Dict[Type[EntityBase], int] = {}

    def find(self, entity_class: Type[EntityBase], pk: PrimaryKey) -> Optional[EntityBase]:
        """Find entity by primary key"""
        with self._lock:
            key = (entity_class.__name__, pk)
            return self._storage.get(key)

    def find_all(self, entity_class: Type[EntityBase]) -> List[EntityBase]:
        """Find all entities of a type"""
        with self._lock:
            return [
                entity
                for (cls_name, _), entity in self._storage.items()
                if cls_name == entity_class.__name__
            ]

    def save(self, entity: EntityBase) -> EntityBase:
        """Save entity (create or update)"""
        from foobara_py.persistence.entity_callbacks import EntityCallbackRegistry, EntityLifecycle

        with self._lock:
            entity_class = type(entity)
            pk_field = entity._primary_key_field

            # Determine if this is a create or update
            pk = entity.primary_key
            is_create = pk is None or not entity.is_persisted

            # Auto-increment if pk is None
            if pk is None:
                pk = self._next_id(entity_class)
                setattr(entity, pk_field, pk)

            # Run before_save callbacks
            EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.BEFORE_SAVE)

            # Run before_create or before_update callbacks
            if is_create:
                EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.BEFORE_CREATE)
            else:
                EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.BEFORE_UPDATE)

            # Perform the save
            key = (entity_class.__name__, pk)
            self._storage[key] = entity
            entity.mark_persisted()

            # Run after_create or after_update callbacks
            if is_create:
                EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.AFTER_CREATE)
            else:
                EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.AFTER_UPDATE)

            # Run after_save callbacks
            EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.AFTER_SAVE)

            return entity

    def delete(self, entity: EntityBase) -> bool:
        """Delete entity"""
        from foobara_py.persistence.entity_callbacks import EntityCallbackRegistry, EntityLifecycle

        with self._lock:
            key = (type(entity).__name__, entity.primary_key)
            if key not in self._storage:
                return False

            # Run before_delete callbacks
            EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.BEFORE_DELETE)

            # Perform the delete
            del self._storage[key]

            # Run after_delete callbacks
            EntityCallbackRegistry.run_callbacks(entity, EntityLifecycle.AFTER_DELETE)

            return True

    def exists(self, entity_class: Type[EntityBase], pk: PrimaryKey) -> bool:
        """Check if entity exists"""
        with self._lock:
            key = (entity_class.__name__, pk)
            return key in self._storage

    def _next_id(self, entity_class: Type[EntityBase]) -> int:
        """Get next auto-increment ID for entity class"""
        if entity_class not in self._auto_increment:
            self._auto_increment[entity_class] = 0
        self._auto_increment[entity_class] += 1
        return self._auto_increment[entity_class]

    def clear(self) -> None:
        """Clear all stored entities"""
        with self._lock:
            self._storage.clear()
            self._auto_increment.clear()

    def count_all(self) -> int:
        """Count all entities across all types"""
        with self._lock:
            return len(self._storage)


# ==================== Repository Registry ====================


class RepositoryRegistry:
    """
    Global registry for entity repositories.

    Allows automatic repository resolution for entity types.
    """

    _repositories: Dict[str, Repository] = {}
    _default: Optional[Repository] = None
    _lock = threading.Lock()

    @classmethod
    def register(cls, entity_class: Type[EntityBase], repository: Repository) -> None:
        """Register repository for an entity class"""
        with cls._lock:
            cls._repositories[entity_class.__name__] = repository

    @classmethod
    def set_default(cls, repository: Repository) -> None:
        """Set default repository for unregistered entities"""
        with cls._lock:
            cls._default = repository

    @classmethod
    def get(cls, entity_class: Type[EntityBase]) -> Optional[Repository]:
        """Get repository for an entity class"""
        with cls._lock:
            repo = cls._repositories.get(entity_class.__name__)
            if repo:
                return repo
            return cls._default

    @classmethod
    def clear(cls) -> None:
        """Clear all registered repositories"""
        with cls._lock:
            cls._repositories.clear()
            cls._default = None


# ==================== Convenience Functions ====================


def find(entity_class: Type[EntityBase], pk: PrimaryKey) -> Optional[EntityBase]:
    """Find entity by primary key using registered repository"""
    repo = RepositoryRegistry.get(entity_class)
    if not repo:
        raise ValueError(f"No repository registered for {entity_class.__name__}")
    return repo.find(entity_class, pk)


def save(entity: EntityBase) -> EntityBase:
    """Save entity using registered repository"""
    repo = RepositoryRegistry.get(type(entity))
    if not repo:
        raise ValueError(f"No repository registered for {type(entity).__name__}")
    return repo.save(entity)


def delete(entity: EntityBase) -> bool:
    """Delete entity using registered repository"""
    repo = RepositoryRegistry.get(type(entity))
    if not repo:
        raise ValueError(f"No repository registered for {type(entity).__name__}")
    return repo.delete(entity)


# ==================== Transactional Repository ====================


class TransactionalInMemoryRepository(InMemoryRepository):
    """
    In-memory repository with transaction support.

    Tracks changes during transactions and can rollback to previous state.
    Works with the foobara_py transaction system.

    Usage:
        from foobara_py import transaction
        from foobara_py.persistence import TransactionalInMemoryRepository

        repo = TransactionalInMemoryRepository()

        with repo.transaction():
            user = User(name="John")
            repo.save(user)
            # If exception occurs, changes are rolled back

    Or with context:
        with repo.transaction():
            User.create(name="John")
            User.create(name="Jane")
            raise ValueError("oops")  # Both users are rolled back
    """

    __slots__ = ("_storage", "_lock", "_auto_increment", "_transaction_log", "_in_transaction")

    def __init__(self):
        super().__init__()
        self._transaction_log: List[Dict[str, Any]] = []
        self._in_transaction: bool = False

    def begin_transaction(self) -> None:
        """Begin a new transaction"""
        with self._lock:
            if self._in_transaction:
                raise ValueError("Already in a transaction")
            self._in_transaction = True
            self._transaction_log = []

    def commit_transaction(self) -> None:
        """Commit the current transaction"""
        with self._lock:
            if not self._in_transaction:
                raise ValueError("No transaction to commit")
            self._transaction_log = []
            self._in_transaction = False

    def rollback_transaction(self) -> None:
        """Rollback the current transaction"""
        with self._lock:
            if not self._in_transaction:
                raise ValueError("No transaction to rollback")

            # Replay log in reverse to undo changes
            for entry in reversed(self._transaction_log):
                action = entry["action"]
                key = entry["key"]

                if action == "save":
                    # Restore previous value or remove
                    if entry.get("previous") is not None:
                        self._storage[key] = entry["previous"]
                    else:
                        self._storage.pop(key, None)
                    # Restore auto-increment counter
                    if "prev_counter" in entry:
                        entity_class = entry["entity_class"]
                        self._auto_increment[entity_class] = entry["prev_counter"]

                elif action == "delete":
                    # Restore deleted entity
                    self._storage[key] = entry["previous"]

            self._transaction_log = []
            self._in_transaction = False

    def save(self, entity: EntityBase) -> EntityBase:
        """Save entity with transaction logging"""
        with self._lock:
            entity_class = type(entity)
            pk_field = entity._primary_key_field
            pk = entity.primary_key

            # Track previous state for rollback
            if self._in_transaction:
                # Capture auto-increment counter before change
                prev_counter = self._auto_increment.get(entity_class, 0)

                if pk is None:
                    pk = self._next_id(entity_class)
                    setattr(entity, pk_field, pk)

                key = (entity_class.__name__, pk)
                previous = self._storage.get(key)

                self._transaction_log.append(
                    {
                        "action": "save",
                        "key": key,
                        "previous": previous,
                        "entity_class": entity_class,
                        "prev_counter": prev_counter,
                    }
                )

                self._storage[key] = entity
                entity.mark_persisted()
                return entity
            else:
                return super().save(entity)

    def delete(self, entity: EntityBase) -> bool:
        """Delete entity with transaction logging"""
        with self._lock:
            key = (type(entity).__name__, entity.primary_key)

            if self._in_transaction:
                previous = self._storage.get(key)
                if previous is not None:
                    self._transaction_log.append(
                        {"action": "delete", "key": key, "previous": previous}
                    )
                    del self._storage[key]
                    return True
                return False
            else:
                return super().delete(entity)

    def transaction(self) -> "RepositoryTransaction":
        """Get a context manager for transactions"""
        return RepositoryTransaction(self)


class RepositoryTransaction:
    """Context manager for repository transactions"""

    __slots__ = ("_repo", "_committed")

    def __init__(self, repo: TransactionalInMemoryRepository):
        self._repo = repo
        self._committed = False

    def __enter__(self) -> "RepositoryTransaction":
        self._repo.begin_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self._repo.rollback_transaction()
        else:
            self._repo.commit_transaction()
        return False  # Don't suppress exceptions

    def commit(self) -> None:
        """Explicitly commit"""
        self._repo.commit_transaction()
        self._committed = True

    def rollback(self) -> None:
        """Explicitly rollback"""
        self._repo.rollback_transaction()
