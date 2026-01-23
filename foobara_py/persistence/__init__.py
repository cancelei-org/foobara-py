"""
Persistence layer for foobara-py.

Provides entity system and CRUD operations similar to Ruby Foobara.
"""

from foobara_py.persistence.associations import (
    BelongsTo,
    EagerLoader,
    HasMany,
    HasOne,
    belongs_to,
    has_many,
    has_one,
)
from foobara_py.persistence.crud_driver import (
    CannotCrudError,
    CannotDeleteError,
    CannotFindError,
    CannotInsertError,
    CannotUpdateError,
    CRUDDriver,
    CRUDTable,
)
from foobara_py.persistence.detached_entity import (
    DetachedEntity,
    detached_entity,
)
from foobara_py.persistence.entity import (
    Entity,
    EntityBase,
    EntityRegistry,
    LoadSpec,
    Model,
    MutableModel,
    PrimaryKey,
    entity,
    load,
    register_entity,
)
from foobara_py.persistence.entity_callbacks import (
    EntityCallbackRegistry,
    EntityLifecycle,
    after_create,
    after_delete,
    after_save,
    after_update,
    after_validation,
    before_create,
    before_delete,
    before_save,
    before_update,
    before_validation,
)
from foobara_py.persistence.in_memory_driver import (
    InMemoryCRUDDriver,
    InMemoryCRUDTable,
)
from foobara_py.persistence.local_files_driver import (
    LocalFilesCRUDDriver,
    LocalFilesCRUDTable,
)
from foobara_py.persistence.postgresql_driver import (
    PostgreSQLCRUDDriver,
    PostgreSQLCRUDTable,
)
from foobara_py.persistence.redis_driver import (
    RedisCRUDDriver,
    RedisCRUDTable,
)
from foobara_py.persistence.repository import (
    InMemoryRepository,
    Repository,
    RepositoryProtocol,
    RepositoryRegistry,
    RepositoryTransaction,
    TransactionalInMemoryRepository,
)

__all__ = [
    "Entity",
    "EntityBase",
    "Model",
    "MutableModel",
    "PrimaryKey",
    "entity",
    "load",
    "LoadSpec",
    "EntityRegistry",
    "register_entity",
    "DetachedEntity",
    "detached_entity",
    "Repository",
    "RepositoryProtocol",
    "InMemoryRepository",
    "TransactionalInMemoryRepository",
    "RepositoryTransaction",
    "RepositoryRegistry",
    "has_many",
    "belongs_to",
    "has_one",
    "HasMany",
    "BelongsTo",
    "HasOne",
    "EagerLoader",
    "EntityLifecycle",
    "EntityCallbackRegistry",
    "before_validation",
    "after_validation",
    "before_create",
    "after_create",
    "before_save",
    "after_save",
    "before_update",
    "after_update",
    "before_delete",
    "after_delete",
    "CRUDDriver",
    "CRUDTable",
    "CannotCrudError",
    "CannotFindError",
    "CannotInsertError",
    "CannotUpdateError",
    "CannotDeleteError",
    "InMemoryCRUDDriver",
    "InMemoryCRUDTable",
    "RedisCRUDDriver",
    "RedisCRUDTable",
    "LocalFilesCRUDDriver",
    "LocalFilesCRUDTable",
    "PostgreSQLCRUDDriver",
    "PostgreSQLCRUDTable",
]
