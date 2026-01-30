# Changelog

All notable changes to foobara-py will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive V1 to V2 migration guide in `docs/MIGRATION_V1_TO_V2.md`
- Expanded migration examples in `MIGRATION_GUIDE.md`
- Migration automation script example
- Detailed troubleshooting section for common migration issues

### Changed
- Enhanced README.md with prominent V1 deprecation notice
- Improved migration documentation with step-by-step examples

## [0.2.0] - 2026-01-21

### Changed - V1 to V2 Transition

**IMPORTANT:** V1 implementations have been deprecated and moved to `_deprecated/`. V2 is now the current implementation (with `_v2` suffix removed).

#### What Changed
- **V1 code moved**: All V1 implementations moved to `foobara_py/_deprecated/` with deprecation warnings
- **V2 renamed**: Removed `_v2` suffix from all current implementations
  - `core/command_v2.py` → `core/command.py`
  - `core/errors_v2.py` → `core/errors.py`
  - `domain/domain_v2.py` → `domain/domain.py`
  - `connectors/mcp_v2.py` → `connectors/mcp.py`
- **Public API unchanged**: `from foobara_py import Command` has always used V2, continues to work

#### Backward Compatibility
- V1 code still available in `_deprecated/` directory
- Deprecation warnings added to all V1 files
- V1 aliases maintained:
  - `SimpleCommand` and `AsyncSimpleCommand` (copied from V1)
  - `ErrorCollection.add_error()` and `add_errors()` (aliases to new methods)
  - `JsonRpcError` (alias for `JsonRpcErrorCode`)

#### Deprecation Timeline
- **v0.2.0** (current): V1 in `_deprecated/`, no warnings yet
- **v0.3.0** (planned): Deprecation warnings enforced for V1 usage
- **v0.4.0** (planned): V1 code completely removed

#### Migration Path
Users importing from the public API (`from foobara_py import Command`) are unaffected. Users importing from internal paths need to update:

**Before (V1 - DEPRECATED):**
```python
from foobara_py.core.command import Command
from foobara_py.core.errors import Error
```

**After (V2 - CURRENT):**
```python
from foobara_py import Command, FoobaraError
```

See [docs/MIGRATION_V1_TO_V2.md](./docs/MIGRATION_V1_TO_V2.md) for complete migration guide.

### Added

#### Core Features
- **8-state command lifecycle**: Full state machine with fine-grained control
  - States: pending → open_transaction → cast_and_validate_inputs → load_records → validate_records → validate → execute → commit_transaction → succeed/fail
- **Comprehensive lifecycle hooks**:
  - `before_execute()` and `after_execute()` methods
  - Decorator-based callbacks: `@before`, `@after`, `@around`
  - Phase-specific hooks: `before_validate`, `after_execute`, etc.
- **Transaction support**:
  - `@transaction` decorator for automatic rollback
  - `TransactionContext` for explicit transaction management
  - Nested transaction support
- **Entity loading system**:
  - `LoadSpec` for automatic entity loading from inputs
  - `_loads` class attribute for declarative entity loading
  - Automatic error handling for missing entities

#### Domain System
- **Domain mappers**: `DomainMapper[FromT, ToT]` for cross-domain type conversion
- **Domain dependencies**: `domain.depends_on()` with validation
- **`run_mapped_subcommand()`**: Execute subcommands with automatic type mapping
- **Global domain support**: Implicit domain for commands without explicit registration

#### Error Handling
- **Error categories**: Data, runtime, input errors with proper categorization
- **Path tracking**: Detailed error paths for nested data structures
- **`add_runtime_error()`**: Convenience method for runtime errors
- **`add_input_error()`**: Convenience method for input validation errors
- **`halt` parameter**: Optional immediate execution halt on errors

#### Persistence
- **Entity callbacks**: `before_create`, `after_save`, etc.
- **Repository pattern**: Explicit `Repository` with `save()` and `find()` methods
- **Transactional repositories**: `TransactionalInMemoryRepository` with rollback
- **Entity registry**: Central registration for entity types
- **Detached entities**: `@detached_entity` for value objects

#### Type System
- **Sensitive types**: `Password`, `APIKey`, `SecretToken`, `BearerToken`
- **Automatic redaction**: Sensitive fields automatically masked in logs/manifests
- **Type registry**: Central type registration and JSON schema generation

#### Caching
- **Cache backend abstraction**: `CacheBackend` protocol
- **In-memory cache**: `InMemoryCache` with TTL and stats
- **`@cached` decorator**: Method-level caching with automatic key generation
- **Cache statistics**: Hit/miss rates, memory usage tracking

#### Remote Imports
- **Remote command execution**: `RemoteCommand` and `AsyncRemoteCommand`
- **Manifest caching**: Cache remote manifests for performance
- **Remote namespaces**: Organize remote commands by service

#### MCP (Model Context Protocol)
- **MCP resources**: Expose read-only data via `MCPResource`
- **Entity-backed resources**: Auto-generate resources from entities
- **URI templates**: Pattern-based resource URLs (e.g., `foobara://user/{id}`)
- **Custom resource loaders**: Flexible data fetching for resources

#### Developer Experience
- **Better error messages**: Detailed error context and suggestions
- **Type safety**: Full generic type support with `Command[InputT, ResultT]`
- **IDE support**: Better autocomplete and type checking
- **Comprehensive tests**: 871+ tests covering all features

### Improved

#### Performance
- **15-25% faster** command execution vs V1
- **Lazy input validation**: Only validate when inputs are accessed
- **Optimized state machine**: Minimal overhead for state transitions
- **Registry caching**: Command/domain lookups cached for speed

#### Architecture
- **Cleaner separation**: Core, domain, persistence, connectors properly isolated
- **Better modularity**: Optional dependencies for MCP, HTTP, CLI connectors
- **Extensibility**: Plugin system for callbacks, mappers, repositories

#### Documentation
- **Inline docstrings**: All classes and methods documented
- **Migration guides**: Comprehensive Ruby → Python and V1 → V2 guides
- **Examples**: Test suite serves as example code
- **README improvements**: Quick start, architecture overview, feature comparison

### Ruby Foobara Parity

V2 achieves **95% feature parity** with Ruby Foobara:

✅ **Fully Compatible:**
- Command pattern and lifecycle
- Domain/organization system
- Error handling and propagation
- Subcommand execution
- Entity system (via repository pattern)
- Manifest generation
- MCP integration

✅ **Python Enhancements:**
- `AsyncCommand` for async/await (Ruby uses threads)
- Pydantic integration for type validation
- Native Python type hints
- `@cached` decorator for memoization

⚠️ **Minor Differences:**
- Repository pattern vs ActiveRecord (explicit save/find)
- Pydantic models vs Ruby type system (more Pythonic)
- Method names: `run_subcommand_bang()` vs Ruby's `run_subcommand!`

See [PARITY_CHECKLIST.md](./PARITY_CHECKLIST.md) for detailed feature comparison.

## [0.1.0] - Initial Release

### Added
- Initial V1 implementation
- Basic command pattern
- Simple outcome handling
- Domain registration
- MCP connector (basic)
- Initial test suite

---

## Migration Guide

For detailed migration instructions, see:
- **[V1 → V2 Quick Guide](./docs/MIGRATION_V1_TO_V2.md)** - Fast migration in <1 hour
- **[Complete Migration Guide](./MIGRATION_GUIDE.md)** - Full Ruby → Python and V1 → V2 guide

## Support

- **Issues**: https://github.com/foobara/foobara-py/issues
- **Discussions**: https://github.com/foobara/foobara-py/discussions
- **Documentation**: See README.md and inline docstrings
