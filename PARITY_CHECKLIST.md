# Foobara Ruby vs Python - Detailed Parity Checklist

Last updated: 2026-01-20

This document provides a granular, feature-by-feature comparison between Ruby Foobara and Python Foobara implementations.

## Legend
- ✅ Fully implemented and tested
- ⚠️ Partially implemented
- ❌ Not implemented
- 🔄 In progress
- N/A - Not applicable to Python

---

## 1. Core Command System

### 1.1 Basic Command
- ✅ Command class definition
- ✅ Generic type parameters (Command[InputT, ResultT])
- ✅ Pydantic-based inputs (vs Ruby's types system)
- ✅ execute() method
- ✅ run() class method
- ✅ run!() / run_() method (with error propagation)
- ✅ Outcome objects (Success/Failure)
- ✅ Error propagation

### 1.2 Command Lifecycle (8 States)
- ✅ open_transaction
- ✅ cast_and_validate_inputs
- ✅ load_records
- ✅ validate_records
- ✅ validate
- ✅ execute
- ✅ commit_transaction
- ✅ succeed/fail/error

### 1.3 Async Command
- ✅ AsyncCommand base class
- ✅ async execute() support
- ✅ async run() support
- ✅ Full lifecycle support in async

### 1.4 Subcommands
- ✅ run_subcommand() - without error propagation
- ✅ run_subcommand!() / run_subcommand_() - with error propagation
- ✅ run_mapped_subcommand() - with domain mapping
- ✅ Nested error path tracking

### 1.5 Callbacks
- ✅ before callbacks
- ✅ after callbacks
- ✅ around callbacks
- ✅ Phase-specific callbacks (before_validate, after_execute, etc.)
- ✅ Callback registry
- ✅ Callback inheritance

### 1.6 Transactions
- ✅ Transaction context
- ✅ Transaction registry
- ✅ @transaction decorator
- ✅ Automatic rollback on error
- ✅ Nested transactions

---

## 2. Domain & Organization

### 2.1 Domain
- ✅ Domain class
- ✅ Command registration
- ✅ Type registration
- ✅ Domain dependencies (depends_on)
- ✅ Cross-domain validation
- ✅ Domain manifest generation
- ✅ Global domain support

### 2.2 Organization
- ✅ Organization class
- ✅ Multi-domain grouping
- ✅ Organization manifest

### 2.3 Domain Mappers
- ✅ DomainMapper[FromT, ToT] base class
- ✅ DomainMapperRegistry
- ✅ Automatic mapper discovery
- ✅ Type scoring for best match
- ✅ Bidirectional mapping
- ✅ run_mapped_subcommand() integration

---

## 3. Error System

### 3.1 FoobaraError
- ✅ Base error class
- ✅ Error symbols
- ✅ Error categories (data, runtime, etc.)
- ✅ Data path tracking
- ✅ Runtime path tracking
- ✅ Error context
- ✅ Fatal errors
- ✅ Ruby-compatible error keys

### 3.2 ErrorCollection
- ✅ Error aggregation
- ✅ Category filtering
- ✅ Symbol-based retrieval
- ✅ Path filtering

### 3.3 Standard Error Symbols
- ✅ data_errors
- ✅ missing_required
- ✅ invalid_type
- ✅ out_of_range
- ✅ authentication_failed
- ✅ authorization_failed
- ✅ rate_limit_exceeded
- ✅ not_found
- ✅ already_exists
- ✅ validation_failed
- ✅ runtime_error
- ✅ system_error

---

## 4. Types System

### 4.1 Basic Types (via Pydantic)
- ✅ BaseModel types
- ✅ Type validation
- ✅ JSON Schema generation
- ⚠️ Type registry (exists but limited)
- ❌ Ruby-style type declarations
- ❌ Custom type DSL

### 4.2 Sensitive Types
- ✅ Sensitive[T] wrapper
- ✅ SensitiveStr
- ✅ Password type
- ✅ APIKey type
- ✅ SecretToken type
- ✅ BearerToken type
- ✅ SensitiveModel base
- ✅ Automatic redaction in logs/manifests

### 4.3 Type Transformations
- ❌ Transformers system
- ❌ Type coercion pipeline
- ❌ Custom transformation rules

### 4.4 Desugarizers
- ❌ Input desugaring system
- ❌ Desugarizer chains
- ❌ Custom desugarizers

---

## 5. Persistence

### 5.1 Entity
- ✅ EntityBase class
- ✅ Primary key tracking
- ✅ Dirty attribute tracking
- ✅ Persisted state management
- ✅ Entity registration
- ✅ DetachedEntity support

### 5.2 Entity CRUD (Instance Methods)
- ✅ save()
- ✅ delete()
- ✅ reload()
- ✅ update()

### 5.3 Entity CRUD (Class Methods)
- ✅ create()
- ✅ find()
- ✅ find_all()
- ✅ find_by()
- ✅ exists()
- ✅ count()

### 5.4 Entity Callbacks
- ✅ before_validation
- ✅ after_validation
- ✅ before_create
- ✅ after_create
- ✅ before_save
- ✅ after_save
- ✅ before_update
- ✅ after_update
- ✅ before_delete
- ✅ after_delete

### 5.5 Models (Value Objects)
- ✅ Model base class
- ✅ MutableModel
- ✅ Immutability by default
- ✅ Value-based equality
- ✅ Embedding in entities

### 5.6 Repository System
- ✅ Repository protocol
- ✅ Repository registry
- ✅ InMemoryRepository
- ✅ TransactionalInMemoryRepository
- ✅ Custom repository support

### 5.7 Drivers
- ✅ LocalFilesDriver
- ⚠️ SQLAlchemy driver (basic)
- ❌ Full SQLAlchemy integration
- ❌ PostgreSQL driver
- ❌ MySQL driver
- ❌ Redis driver

### 5.8 Load Declarations
- ✅ LoadSpec system
- ✅ Automatic PK → entity loading in commands
- ✅ Association loading declarations

---

## 6. Serialization

### 6.1 Base Serializer
- ✅ Serializer[T] base class
- ✅ serialize() method
- ✅ deserialize() method
- ✅ SerializerRegistry
- ✅ Priority-based serializer selection

### 6.2 Entity Serializers
- ✅ AggregateSerializer - full entity with associations
- ✅ AtomicSerializer - entity with associations as PKs
- ✅ EntitiesToPrimaryKeysSerializer - recursive PK conversion

### 6.3 Error Serializers
- ✅ ErrorsSerializer
- ✅ Ruby Foobara-compatible error format
- ✅ Error key generation
- ✅ Context and path serialization

### 6.4 Type Serializers
- ⚠️ Basic Pydantic serialization
- ❌ Custom type serializers
- ❌ Sensitive type serialization (manual redaction works)

---

## 7. Connectors

### 7.1 MCP Connector (Python-specific)
- ✅ MCP server implementation
- ✅ Command → MCP tool conversion
- ✅ Async MCP protocol support
- ✅ Schema generation
- ✅ create_mcp_server() helper

### 7.2 HTTP Connector
- ✅ FastAPI integration
- ✅ Command → HTTP endpoint conversion
- ✅ Automatic route generation
- ✅ Request/response handling
- ✅ Error mapping to HTTP status codes

### 7.3 CLI Connector
- ✅ Typer integration
- ✅ Command → CLI command conversion
- ✅ Automatic argument parsing
- ✅ Help text generation

### 7.4 Other Connectors (Ruby has these)
- ❌ Rack connector
- ❌ Rails connector
- ❌ Sinatra connector
- ❌ Celery connector
- ❌ Django connector

---

## 8. HTTP API Integration

### 8.1 HTTPAPICommand
- ✅ Base class for HTTP API clients
- ✅ Abstract endpoint() method
- ✅ Abstract method() method
- ✅ Abstract parse_response() method
- ✅ Optional request_body() override
- ✅ Optional query_params() override
- ✅ Optional headers() override
- ✅ Automatic error handling
- ✅ Retry logic with exponential backoff
- ✅ Custom authentication support
- ✅ httpx-based implementation

### 8.2 HTTP Status Code Mapping
- ✅ 4xx → data errors
- ✅ 5xx → runtime errors
- ✅ 401 → authentication_failed
- ✅ 403 → authorization_failed
- ✅ 404 → not_found
- ✅ 429 → rate_limit_exceeded

---

## 9. Caching System

### 9.1 Cached Command
- ✅ @cached decorator
- ✅ TTL support
- ✅ Custom cache key generation
- ✅ cache_key() helper
- ✅ cache_failures parameter
- ✅ Custom cache backend support
- ✅ clear_cache() method

### 9.2 Cache Backends
- ✅ CacheBackend protocol
- ✅ InMemoryCache with TTL
- ✅ Thread-safe operations
- ❌ Redis cache backend
- ❌ Memcached backend

### 9.3 Cache Stats
- ✅ CacheStats class
- ✅ Hit/miss tracking
- ✅ Hit rate calculation
- ❌ Cache metrics export

---

## 10. Manifest System

### 10.1 Basic Manifests
- ✅ Command manifest (from Pydantic)
- ✅ Domain manifest
- ⚠️ Type manifest (basic)
- ❌ Full type manifest with Ruby compatibility

### 10.2 Advanced Manifests
- ❌ RootManifest aggregating all
- ❌ Organization manifest
- ❌ Entity manifest
- ❌ Error manifest
- ❌ Processor manifest

### 10.3 Manifest Features
- ❌ Cross-referencing with $ref
- ❌ Dependency tracking
- ❌ Manifest filtering
- ❌ Manifest caching

---

## 11. Remote Imports

### 11.1 Remote Command System
- ❌ RemoteCommand proxy class
- ❌ Manifest fetching
- ❌ RemoteImporter
- ❌ Manifest caching
- ❌ import_command()
- ❌ import_all()

### 11.2 Remote Types
- ❌ Remote type imports
- ❌ DetachedEntity from remote
- ❌ Type synchronization

---

## 12. Code Generation

### 12.1 FilesGenerator Base
- ✅ FilesGenerator abstract base
- ✅ Jinja2 template support
- ✅ Template rendering
- ✅ File creation from templates
- ✅ Directory creation
- ✅ Custom filters (snake_case, pascal_case, camel_case, kebab_case)
- ✅ Template path discovery

### 12.2 Command Generator
- ❌ CommandGenerator class
- ❌ Command file template
- ❌ Inputs class generation
- ❌ Test file generation
- ❌ CLI integration

### 12.3 Domain Generator
- ❌ DomainGenerator class
- ❌ Domain package structure
- ❌ __init__.py generation
- ❌ Domain registration

### 12.4 Type/Entity Generator
- ❌ TypeGenerator class
- ❌ Entity class generation
- ❌ Model class generation
- ❌ Repository generation
- ❌ Migration generation (if using SQLAlchemy)

### 12.5 AutoCRUD Generator
- ❌ CRUD command generation
- ❌ Create/Read/Update/Delete commands
- ❌ List/Search commands
- ❌ Validation generation

### 12.6 Project Generator
- ❌ New project scaffolding
- ❌ pyproject.toml generation
- ❌ Directory structure setup
- ❌ Example code generation

### 12.7 CLI Tool (foob-py)
- ❌ foob-py CLI executable
- ❌ generate command
- ❌ scaffold command
- ❌ Interactive mode

---

## 13. Authentication & Authorization

### 13.1 Entities
- ✅ Token entity
- ❌ User entity
- ❌ Session entity
- ❌ Role entity
- ❌ Permission entity

### 13.2 Password Utilities
- ✅ hash_password()
- ✅ verify_password()
- ✅ needs_rehash()
- ✅ verify_and_rehash()
- ✅ Argon2id algorithm
- ✅ Configurable parameters

### 13.3 Commands
- ❌ Login command
- ❌ Logout command
- ❌ RefreshToken command
- ❌ ValidateToken command
- ❌ RevokeToken command
- ❌ ChangePassword command
- ❌ ResetPassword command

### 13.4 Middleware
- ❌ HTTP auth middleware
- ❌ Token extraction
- ❌ Token validation
- ❌ User context injection
- ❌ Permission checking

---

## 14. AI/LLM Integration

### 14.1 LLM-Backed Commands
- ❌ LLMBackedCommand base class
- ❌ Prompt template system
- ❌ Input → prompt conversion
- ❌ Response → result parsing
- ❌ JSON response handling

### 14.2 LLM API Clients
- ❌ Anthropic API client (CreateMessage, ListModels)
- ❌ OpenAI API client (ChatCompletion, Embeddings)
- ❌ Ollama API client (Generate, Embeddings)

### 14.3 AI Agent Framework
- ❌ Agent base class
- ❌ Tool use patterns
- ❌ Multi-step reasoning
- ❌ Agent coordination
- ❌ Agent memory/context

### 14.4 Tool Use
- ❌ Tool definition from commands
- ❌ Tool execution
- ❌ Tool result handling
- ❌ Multi-turn tool use

---

## 15. Testing Utilities

### 15.1 Test Helpers
- ⚠️ Basic pytest fixtures
- ❌ Command test helpers
- ❌ Entity test helpers
- ❌ Mock repository
- ❌ Test data generators

### 15.2 Factories
- ❌ Entity factories
- ❌ FactoryBot equivalent
- ❌ Trait support

---

## 16. Observability

### 16.1 Logging
- ⚠️ Basic Python logging
- ❌ Structured logging
- ❌ Command execution logging
- ❌ Sensitive data redaction in logs

### 16.2 Metrics
- ❌ Command execution metrics
- ❌ Cache metrics
- ❌ Error rate tracking
- ❌ Performance monitoring

### 16.3 Tracing
- ❌ OpenTelemetry integration
- ❌ Command trace spans
- ❌ Distributed tracing

---

## 17. Async/Background Processing

### 17.1 Async Commands
- ✅ AsyncCommand base class
- ✅ Full async support

### 17.2 Background Jobs
- ❌ Background job system
- ❌ Celery integration
- ❌ Job queue abstraction
- ❌ Retry logic for background jobs

---

## 18. Validation

### 18.1 Input Validation (via Pydantic)
- ✅ Type validation
- ✅ Required field validation
- ✅ Format validation
- ✅ Custom validators
- ✅ Nested validation

### 18.2 Business Logic Validation
- ✅ validate() method
- ✅ validate_records() method
- ✅ Custom validation errors

### 18.3 Cross-Field Validation
- ✅ Pydantic validators
- ✅ model_validator

---

## 19. Documentation

### 19.1 Auto-Generated Docs
- ❌ Command documentation generation
- ❌ API documentation generation
- ❌ Manifest → docs conversion

### 19.2 Examples
- ⚠️ Basic examples in README
- ❌ Comprehensive example projects
- ❌ Tutorial documentation

---

## Summary Statistics

### By Major Category
| Category | Complete | Partial | Missing | Total | % Complete |
|----------|----------|---------|---------|-------|------------|
| Core Command | 25 | 0 | 0 | 25 | 100% |
| Domain System | 11 | 0 | 0 | 11 | 100% |
| Error System | 12 | 0 | 0 | 12 | 100% |
| Types | 10 | 2 | 4 | 16 | 62.5% |
| Persistence | 29 | 1 | 5 | 35 | 82.9% |
| Serialization | 10 | 1 | 2 | 13 | 76.9% |
| Connectors | 13 | 0 | 5 | 18 | 72.2% |
| HTTP API | 13 | 0 | 0 | 13 | 100% |
| Caching | 8 | 0 | 2 | 10 | 80% |
| Manifests | 2 | 1 | 8 | 11 | 18.2% |
| Remote Imports | 0 | 0 | 8 | 8 | 0% |
| Code Generation | 7 | 0 | 24 | 31 | 22.6% |
| Auth | 6 | 0 | 12 | 18 | 33.3% |
| AI/LLM | 0 | 0 | 14 | 14 | 0% |
| Testing | 1 | 0 | 7 | 8 | 12.5% |
| Observability | 1 | 0 | 8 | 9 | 11.1% |
| Async/Background | 2 | 0 | 4 | 6 | 33.3% |
| Validation | 7 | 0 | 0 | 7 | 100% |
| Documentation | 1 | 0 | 2 | 3 | 33.3% |

### Grand Total
- **Total Features**: 248
- **Complete**: 158 (63.7%)
- **Partial**: 5 (2.0%)
- **Missing**: 85 (34.3%)

---

## Priority Gaps to Close

### Critical (Core Features)
1. ❌ Transformers/Desugarizers system - Core data processing
2. ❌ Full type manifest system - Needed for remote imports
3. ❌ Remote imports - Cross-service integration

### High Priority (Developer Experience)
1. ❌ Command/Domain/Type generators - Developer productivity
2. ❌ foob-py CLI tool - Project scaffolding
3. ❌ Full SQLAlchemy driver - Production persistence

### Medium Priority (Common Use Cases)
1. ❌ Login/Logout commands - Auth completion
2. ❌ HTTP auth middleware - API security
3. ❌ LLM API clients - AI integration
4. ❌ Background job system - Async processing

### Low Priority (Nice to Have)
1. ❌ AI agent framework - Advanced AI features
2. ❌ Observability (metrics, tracing) - Production monitoring
3. ❌ Test factories - Testing convenience
