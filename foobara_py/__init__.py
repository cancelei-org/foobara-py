"""
foobara-py: Python implementation of the Foobara command pattern.

A high-performance command-centric framework with full Ruby Foobara parity.

Features:
- Command pattern with 8-state execution flow
- Lifecycle callbacks (before/after/around)
- Subcommand execution with error propagation
- Transaction management
- Domain dependencies
- Entity system
- MCP (Model Context Protocol) integration

Basic Usage:
    from pydantic import BaseModel
    from foobara_py import Command, Domain, CommandOutcome

    class CreateUserInputs(BaseModel):
        name: str
        email: str

    class User(BaseModel):
        id: int
        name: str
        email: str

    users = Domain("Users", organization="MyApp")

    @users.command
    class CreateUser(Command[CreateUserInputs, User]):
        def execute(self) -> User:
            return User(id=1, name=self.inputs.name, email=self.inputs.email)

    # Run command
    outcome = CreateUser.run(name="John", email="john@example.com")
    if outcome.is_success():
        user = outcome.unwrap()
"""

__version__ = "0.2.0"

# Core - New high-performance implementation
# Caching
from foobara_py.caching import (
    CacheBackend,
    CacheStats,
    InMemoryCache,
    cache_key,
    cached,
    generate_cache_key,
    get_default_cache,
    set_default_cache,
)

# Connectors
from foobara_py.connectors.mcp import (
    MCPConnector,
    create_mcp_server,
)
from foobara_py.core.callbacks import (
    CallbackPhase,
    CallbackRegistry,
    CallbackType,
    after,
    after_execute,
    after_validate,
    around,
    around_execute,
    before,
    before_execute,
    before_validate,
)
from foobara_py.core.command import (
    AsyncCommand,
    Command,
    async_command,
    command,
)
from foobara_py.core.errors import (
    DataError,  # Backward compatibility alias
    ErrorCollection,
    FoobaraError,
)
from foobara_py.core.errors import (
    Symbols as ErrorSymbols,
)
from foobara_py.core.outcome import (
    CommandOutcome,
    Failure,
    Outcome,
    Success,
)

# Registry
from foobara_py.core.registry import (
    CommandRegistry,
    DomainRegistry,
    TypeRegistry,
    get_default_registry,
    register,
)
from foobara_py.core.state_machine import (
    CommandState,
    CommandStateMachine,
    Halt,
)
from foobara_py.core.transactions import (
    TransactionConfig,
    TransactionContext,
    TransactionRegistry,
    transaction,
)

# Domain
from foobara_py.domain.domain import (
    Domain,
    DomainDependencyError,
    GlobalDomain,
    Organization,
    create_domain,
    foobara_domain,
    foobara_organization,
    get_domain,
    get_organization,
)

# Drivers
from foobara_py.drivers import (
    LocalFilesDriver,
)

# Persistence
from foobara_py.persistence import (
    DetachedEntity,
    Entity,
    EntityBase,
    EntityCallbackRegistry,
    # Entity callbacks
    EntityLifecycle,
    EntityRegistry,
    InMemoryRepository,
    LoadSpec,
    Model,
    MutableModel,
    PrimaryKey,
    Repository,
    RepositoryProtocol,
    RepositoryRegistry,
    RepositoryTransaction,
    TransactionalInMemoryRepository,
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
    detached_entity,
    entity,
    load,
    register_entity,
)

# Remote Imports
from foobara_py.remote import (
    AsyncRemoteCommand,
    ManifestCache,
    RemoteCommand,
    RemoteImporter,
    RemoteNamespace,
    get_manifest_cache,
    import_remote,
    set_manifest_cache,
)

# Types
from foobara_py.types import (
    APIKey,
    BearerToken,
    Password,
    SecretToken,
    Sensitive,
    SensitiveModel,
    SensitiveStr,
    get_sensitive_fields,
    is_sensitive,
    redact_dict,
)

__all__ = [
    # Version
    "__version__",
    # Core Command
    "Command",
    "AsyncCommand",
    "command",
    "async_command",
    # Outcome
    "CommandOutcome",
    "Success",
    "Failure",
    "Outcome",
    # Errors
    "FoobaraError",
    "DataError",
    "ErrorCollection",
    "ErrorSymbols",
    # State Machine
    "CommandState",
    "CommandStateMachine",
    "Halt",
    # Callbacks
    "CallbackPhase",
    "CallbackType",
    "CallbackRegistry",
    "before",
    "after",
    "around",
    "before_validate",
    "after_validate",
    "before_execute",
    "after_execute",
    "around_execute",
    # Transactions
    "TransactionContext",
    "TransactionConfig",
    "TransactionRegistry",
    "transaction",
    # Domain
    "Domain",
    "Organization",
    "GlobalDomain",
    "DomainDependencyError",
    "foobara_domain",
    "foobara_organization",
    "create_domain",
    "get_domain",
    "get_organization",
    # Registry
    "CommandRegistry",
    "TypeRegistry",
    "DomainRegistry",
    "get_default_registry",
    "register",
    # Connectors
    "MCPConnector",
    "create_mcp_server",
    # Persistence
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
    # Entity callbacks
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
    # Drivers
    "LocalFilesDriver",
    # Types
    "Sensitive",
    "SensitiveStr",
    "Password",
    "APIKey",
    "SecretToken",
    "BearerToken",
    "SensitiveModel",
    "is_sensitive",
    "get_sensitive_fields",
    "redact_dict",
    # Caching
    "CacheBackend",
    "InMemoryCache",
    "get_default_cache",
    "set_default_cache",
    "cached",
    "cache_key",
    "generate_cache_key",
    "CacheStats",
    # Remote Imports
    "RemoteCommand",
    "AsyncRemoteCommand",
    "RemoteImporter",
    "RemoteNamespace",
    "import_remote",
    "ManifestCache",
    "get_manifest_cache",
    "set_manifest_cache",
]
