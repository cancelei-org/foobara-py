"""
Pytest configuration and shared fixtures for foobara-py test suite

This module provides:
- Registry cleanup fixtures
- Entity and repository fixtures
- Domain and organization fixtures
- Mock data generators
- Test helpers and utilities
- Database setup/teardown for integration tests

Usage:
    Tests automatically have access to all fixtures defined here.
    Import specific fixtures in your test modules as needed.

    Example:
        def test_something(clean_registries, user_repository):
            # Registries are automatically cleaned
            # Repository is ready to use
            pass
"""

import pytest
import tempfile
import shutil
import asyncio
from typing import Generator, Optional, Any, Dict, List
from pathlib import Path

from foobara_py import Domain
from foobara_py.core.registry import Registry
from foobara_py.persistence import (
    EntityBase,
    Repository,
    InMemoryRepository,
    TransactionalInMemoryRepository,
    RepositoryRegistry,
)
from foobara_py.domain import DomainMapperRegistry
from foobara_py.serializers import SerializerRegistry

# Import factories for use in fixtures
from tests.factories import (
    UserFactory,
    ProductFactory,
    OrderFactory,
    DomainFactory,
    CommandFactory,
    reset_all_factories,
)


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers",
        "unit: Fast unit tests with no I/O"
    )
    config.addinivalue_line(
        "markers",
        "integration: Tests requiring external resources"
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests taking >1 second"
    )
    config.addinivalue_line(
        "markers",
        "persistence: Database/storage tests"
    )
    config.addinivalue_line(
        "markers",
        "connectors: MCP/HTTP/CLI connector tests"
    )
    config.addinivalue_line(
        "markers",
        "async: Async command tests"
    )


# ============================================================================
# REGISTRY CLEANUP FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def clean_registries():
    """
    Automatically clean all registries before and after each test.

    This fixture runs automatically for every test to ensure clean state.
    Prevents test pollution and ensures test isolation.
    """
    # Clean before test
    if hasattr(Domain, '_registry'):
        if isinstance(Domain._registry, dict):
            Domain._registry.clear()
        elif hasattr(Domain._registry, 'clear'):
            Domain._registry.clear()

    RepositoryRegistry.clear()
    DomainMapperRegistry.clear()
    SerializerRegistry.clear()
    reset_all_factories()

    yield

    # Clean after test
    if hasattr(Domain, '_registry'):
        if isinstance(Domain._registry, dict):
            Domain._registry.clear()
        elif hasattr(Domain._registry, 'clear'):
            Domain._registry.clear()

    RepositoryRegistry.clear()
    DomainMapperRegistry.clear()
    SerializerRegistry.clear()
    reset_all_factories()


@pytest.fixture
def isolated_registry():
    """
    Provide an isolated registry context.

    Use when you need explicit control over registry lifecycle.
    """
    registry = Registry()
    yield registry
    registry.clear()


# ============================================================================
# REPOSITORY FIXTURES
# ============================================================================


@pytest.fixture
def in_memory_repository() -> InMemoryRepository:
    """Provide a fresh in-memory repository for each test"""
    return InMemoryRepository()


@pytest.fixture
def transactional_repository() -> TransactionalInMemoryRepository:
    """Provide a transactional in-memory repository for each test"""
    return TransactionalInMemoryRepository()


@pytest.fixture
def user_repository(in_memory_repository) -> Repository:
    """
    Provide a repository registered for User entities

    Usage:
        def test_users(user_repository):
            user = User(username="test", email="test@test.com")
            saved_user = user_repository.save(user)
    """
    # Import here to avoid circular dependencies
    from foobara_py.persistence import EntityBase

    # Create a simple User class for testing
    class User(EntityBase):
        _primary_key_field = 'id'
        id: Optional[int] = None
        username: str
        email: str
        password_hash: str = ""
        is_active: bool = True

    RepositoryRegistry.register(User, in_memory_repository)
    UserFactory.entity_class = User
    return in_memory_repository


@pytest.fixture
def product_repository(in_memory_repository) -> Repository:
    """Provide a repository registered for Product entities"""
    from foobara_py.persistence import EntityBase
    from decimal import Decimal

    class Product(EntityBase):
        _primary_key_field = 'id'
        id: Optional[int] = None
        name: str
        description: str = ""
        price: Decimal = Decimal('0.00')
        stock: int = 0
        category: str = "general"

    RepositoryRegistry.register(Product, in_memory_repository)
    ProductFactory.entity_class = Product
    return in_memory_repository


@pytest.fixture
def order_repository(in_memory_repository) -> Repository:
    """Provide a repository registered for Order entities"""
    from foobara_py.persistence import EntityBase
    from decimal import Decimal

    class Order(EntityBase):
        _primary_key_field = 'id'
        id: Optional[int] = None
        user_id: int
        product_id: int
        quantity: int
        total: Decimal
        status: str = "pending"

    RepositoryRegistry.register(Order, in_memory_repository)
    OrderFactory.entity_class = Order
    return in_memory_repository


# ============================================================================
# DOMAIN FIXTURES
# ============================================================================


@pytest.fixture
def test_domain() -> Domain:
    """
    Provide a test domain

    Usage:
        def test_domain_commands(test_domain):
            @test_domain.command
            class MyCommand(Command[Inputs, Result]):
                ...
    """
    return DomainFactory.create(name="TestDomain", organization="TestOrg")


@pytest.fixture
def multiple_domains() -> List[Domain]:
    """Provide multiple test domains for cross-domain testing"""
    return [
        DomainFactory.create(name="Domain1", organization="TestOrg"),
        DomainFactory.create(name="Domain2", organization="TestOrg"),
        DomainFactory.create(name="Domain3", organization="TestOrg"),
    ]


@pytest.fixture
def domain_with_commands() -> Domain:
    """Provide a domain pre-populated with test commands"""
    return DomainFactory.create_with_commands(command_count=5)


# ============================================================================
# FILE SYSTEM FIXTURES
# ============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Provide a temporary directory that's cleaned up after the test

    Usage:
        def test_file_operations(temp_dir):
            file_path = temp_dir / "test.txt"
            file_path.write_text("test content")
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_file(temp_dir) -> Generator[Path, None, None]:
    """Provide a temporary file"""
    file_path = temp_dir / "test_file.txt"
    file_path.touch()
    yield file_path


# ============================================================================
# ASYNC FIXTURES
# ============================================================================


@pytest.fixture
def event_loop():
    """
    Provide an event loop for async tests

    This ensures each test gets a fresh event loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_repository():
    """Provide an async-compatible repository for testing"""
    repo = InMemoryRepository()
    yield repo


# ============================================================================
# MOCK DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_users() -> List[Dict[str, Any]]:
    """Provide sample user data for testing"""
    from tests.factories import MockDataGenerator
    return MockDataGenerator.generate_user_data(count=5)


@pytest.fixture
def sample_products() -> List[Dict[str, Any]]:
    """Provide sample product data for testing"""
    from tests.factories import MockDataGenerator
    return MockDataGenerator.generate_product_data(count=10)


@pytest.fixture
def sample_orders() -> List[Dict[str, Any]]:
    """Provide sample order data for testing"""
    from tests.factories import MockDataGenerator
    return MockDataGenerator.generate_order_data(
        user_count=5,
        product_count=10,
        order_count=20
    )


@pytest.fixture
def complete_test_data() -> Dict[str, List[Dict[str, Any]]]:
    """Provide a complete set of test data (users, products, orders)"""
    from tests.factories import create_test_suite_data
    return create_test_suite_data(
        user_count=5,
        product_count=10,
        order_count=20
    )


# ============================================================================
# ENTITY INSTANCE FIXTURES
# ============================================================================


@pytest.fixture
def user_instance(user_repository):
    """Provide a single User entity instance"""
    return UserFactory.create(repository=user_repository, username="testuser")


@pytest.fixture
def multiple_users(user_repository):
    """Provide multiple User entity instances"""
    return UserFactory.create_batch(5, repository=user_repository)


@pytest.fixture
def product_instance(product_repository):
    """Provide a single Product entity instance"""
    return ProductFactory.create(repository=product_repository, name="Test Product")


@pytest.fixture
def multiple_products(product_repository):
    """Provide multiple Product entity instances"""
    return ProductFactory.create_batch(10, repository=product_repository)


# ============================================================================
# HTTP/CONNECTOR FIXTURES
# ============================================================================


@pytest.fixture
def mock_http_client():
    """Provide a mock HTTP client for testing HTTP connectors"""
    from unittest.mock import Mock
    client = Mock()
    client.get.return_value = Mock(status_code=200, json=lambda: {})
    client.post.return_value = Mock(status_code=200, json=lambda: {})
    return client


@pytest.fixture
def fastapi_test_client():
    """
    Provide FastAPI test client for HTTP connector testing

    Usage:
        def test_http_endpoint(fastapi_test_client, test_domain):
            response = fastapi_test_client.get("/api/commands")
            assert response.status_code == 200
    """
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI not installed")


# ============================================================================
# TRANSACTION FIXTURES
# ============================================================================


@pytest.fixture
def transaction_context():
    """Provide a transaction context for testing"""
    from foobara_py.core.transactions import TransactionContext, NoOpTransactionHandler
    handler = NoOpTransactionHandler()
    return TransactionContext(handler)


@pytest.fixture
def nested_transaction_context():
    """Provide nested transaction contexts for testing"""
    from foobara_py.core.transactions import TransactionContext, NoOpTransactionHandler
    handler = NoOpTransactionHandler()
    contexts = [
        TransactionContext(handler),
        TransactionContext(handler),
        TransactionContext(handler),
    ]
    return contexts


# ============================================================================
# AUTHENTICATION FIXTURES
# ============================================================================


@pytest.fixture
def mock_auth_context():
    """Provide a mock authentication context"""
    from foobara_py.auth import AuthContext
    return AuthContext(
        user_id="test_user_123",
        claims={'role': 'admin', 'permissions': ['read', 'write']}
    )


@pytest.fixture
def bearer_token_authenticator():
    """Provide a bearer token authenticator for testing"""
    try:
        from foobara_py.auth import BearerTokenAuthenticator
        return BearerTokenAuthenticator(secret_key="test_secret_key_12345")
    except ImportError:
        pytest.skip("Auth dependencies not installed")


# ============================================================================
# SERIALIZATION FIXTURES
# ============================================================================


@pytest.fixture
def entity_serializer():
    """Provide an entity serializer for testing"""
    from foobara_py.serializers import AggregateSerializer
    return AggregateSerializer()


@pytest.fixture
def atomic_serializer():
    """Provide an atomic serializer for testing"""
    from foobara_py.serializers import AtomicSerializer
    return AtomicSerializer()


# ============================================================================
# HYPOTHESIS FIXTURES
# ============================================================================


@pytest.fixture
def hypothesis_settings():
    """
    Provide Hypothesis settings for property-based testing

    Adjust based on environment (CI vs local development)
    """
    try:
        from hypothesis import settings
        import os

        profile = os.getenv("HYPOTHESIS_PROFILE", "dev")
        settings.load_profile(profile)
        return settings
    except ImportError:
        pytest.skip("Hypothesis not installed")


# ============================================================================
# HELPER FIXTURES
# ============================================================================


@pytest.fixture
def capture_logs():
    """Capture log output for testing"""
    import logging
    from io import StringIO

    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = logging.getLogger('foobara_py')
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    yield log_stream

    logger.removeHandler(handler)


@pytest.fixture
def freeze_time():
    """Freeze time for testing time-dependent functionality"""
    try:
        from freezegun import freeze_time as _freeze_time
        return _freeze_time
    except ImportError:
        pytest.skip("freezegun not installed")


# ============================================================================
# PYTEST HELPERS
# ============================================================================


class TestHelpers:
    """Helper methods available in tests"""

    @staticmethod
    def assert_command_success(outcome):
        """Assert that a command outcome is successful"""
        assert outcome.is_success(), f"Command failed: {outcome.errors}"

    @staticmethod
    def assert_command_failure(outcome, expected_error_symbol=None):
        """Assert that a command outcome failed"""
        assert outcome.is_failure(), "Expected command to fail"
        if expected_error_symbol:
            error_symbols = [e.symbol for e in outcome.errors]
            assert expected_error_symbol in error_symbols, \
                f"Expected error '{expected_error_symbol}' not in {error_symbols}"

    @staticmethod
    def assert_entity_persisted(entity, repository):
        """Assert that an entity is persisted in repository"""
        pk = entity.primary_key
        found = repository.find_by_primary_key(pk)
        assert found is not None, f"Entity with pk={pk} not found in repository"

    @staticmethod
    def assert_registry_contains(registry, key):
        """Assert that a registry contains a key"""
        assert key in registry._registry, f"Key '{key}' not found in registry"


@pytest.fixture
def helpers():
    """Provide test helpers"""
    return TestHelpers()
