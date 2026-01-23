"""Tests for Entity/Model persistence system"""

import pytest
from typing import Optional
from pydantic import Field

from foobara_py.persistence import (
    Entity,
    EntityBase,
    Model,
    MutableModel,
    entity,
    EntityRegistry,
    register_entity,
    Repository,
    InMemoryRepository,
    TransactionalInMemoryRepository,
    RepositoryTransaction,
    RepositoryRegistry,
)


# ==================== Test Fixtures ====================

class Address(Model):
    """Value object for addresses"""
    street: str
    city: str
    zip_code: str


class MutableAddress(MutableModel):
    """Mutable value object for addresses"""
    street: str
    city: str
    zip_code: str


class User(EntityBase):
    """Test entity"""
    _primary_key_field = 'id'
    id: Optional[int] = None
    name: str
    email: str
    age: int = 0


class Product(EntityBase):
    """Test entity with string primary key"""
    _primary_key_field = 'sku'
    sku: Optional[str] = None
    name: str
    price: float


@pytest.fixture
def repo():
    """Fresh in-memory repository for each test"""
    r = InMemoryRepository()
    RepositoryRegistry.set_default(r)
    yield r
    RepositoryRegistry.clear()


@pytest.fixture
def tx_repo():
    """Fresh transactional repository for each test"""
    r = TransactionalInMemoryRepository()
    RepositoryRegistry.set_default(r)
    yield r
    RepositoryRegistry.clear()


# ==================== Model Tests ====================

class TestModel:
    """Tests for immutable Model (value objects)"""

    def test_model_creation(self):
        addr = Address(street="123 Main St", city="Springfield", zip_code="12345")
        assert addr.street == "123 Main St"
        assert addr.city == "Springfield"
        assert addr.zip_code == "12345"

    def test_model_is_immutable(self):
        addr = Address(street="123 Main St", city="Springfield", zip_code="12345")
        with pytest.raises(Exception):  # Pydantic frozen model
            addr.street = "456 Oak Ave"

    def test_model_equality(self):
        addr1 = Address(street="123 Main St", city="Springfield", zip_code="12345")
        addr2 = Address(street="123 Main St", city="Springfield", zip_code="12345")
        assert addr1 == addr2

    def test_model_hash(self):
        addr1 = Address(street="123 Main St", city="Springfield", zip_code="12345")
        addr2 = Address(street="123 Main St", city="Springfield", zip_code="12345")
        assert hash(addr1) == hash(addr2)

        # Can be used in sets
        addr_set = {addr1, addr2}
        assert len(addr_set) == 1

    def test_model_with_updates(self):
        addr = Address(street="123 Main St", city="Springfield", zip_code="12345")
        new_addr = addr.with_updates(city="Shelbyville")

        # Original unchanged
        assert addr.city == "Springfield"
        # New object has update
        assert new_addr.city == "Shelbyville"
        assert new_addr.street == "123 Main St"


class TestMutableModel:
    """Tests for mutable Model"""

    def test_mutable_model_creation(self):
        addr = MutableAddress(street="123 Main St", city="Springfield", zip_code="12345")
        assert addr.street == "123 Main St"

    def test_mutable_model_can_be_modified(self):
        addr = MutableAddress(street="123 Main St", city="Springfield", zip_code="12345")
        addr.street = "456 Oak Ave"
        assert addr.street == "456 Oak Ave"

    def test_mutable_model_equality(self):
        addr1 = MutableAddress(street="123 Main St", city="Springfield", zip_code="12345")
        addr2 = MutableAddress(street="123 Main St", city="Springfield", zip_code="12345")
        assert addr1 == addr2


# ==================== Entity Tests ====================

class TestEntityBase:
    """Tests for EntityBase"""

    def test_entity_creation(self):
        user = User(name="John", email="john@example.com", age=30)
        assert user.name == "John"
        assert user.email == "john@example.com"
        assert user.age == 30
        assert user.id is None

    def test_entity_primary_key(self):
        user = User(id=1, name="John", email="john@example.com")
        assert user.primary_key == 1

    def test_entity_is_new(self):
        user = User(name="John", email="john@example.com")
        assert user.is_new  # Property, not method

        user.mark_persisted()
        assert not user.is_new

    def test_entity_dirty_tracking(self):
        user = User(id=1, name="John", email="john@example.com")
        user.mark_persisted()

        assert not user.is_dirty  # Property

        user.name = "Jane"
        assert user.is_dirty
        assert "name" in user.dirty_attributes  # Property

    def test_entity_reset_dirty(self):
        user = User(id=1, name="John", email="john@example.com")
        user.mark_persisted()
        user.name = "Jane"

        assert user.is_dirty
        user.mark_persisted()  # Clears dirty tracking
        assert not user.is_dirty


# ==================== Repository Tests ====================

class TestInMemoryRepository:
    """Tests for InMemoryRepository"""

    def test_save_new_entity(self, repo):
        user = User(name="John", email="john@example.com")
        saved = repo.save(user)

        assert saved.id == 1  # Auto-incremented
        assert not saved.is_new  # Property

    def test_find_entity(self, repo):
        user = User(name="John", email="john@example.com")
        repo.save(user)

        found = repo.find(User, 1)
        assert found is not None
        assert found.name == "John"

    def test_find_nonexistent_returns_none(self, repo):
        found = repo.find(User, 999)
        assert found is None

    def test_find_all(self, repo):
        repo.save(User(name="John", email="john@example.com"))
        repo.save(User(name="Jane", email="jane@example.com"))

        users = repo.find_all(User)
        assert len(users) == 2

    def test_delete_entity(self, repo):
        user = User(name="John", email="john@example.com")
        repo.save(user)

        result = repo.delete(user)
        assert result is True
        assert repo.find(User, 1) is None

    def test_delete_nonexistent_returns_false(self, repo):
        user = User(id=999, name="Ghost", email="ghost@example.com")
        result = repo.delete(user)
        assert result is False

    def test_exists(self, repo):
        user = User(name="John", email="john@example.com")
        repo.save(user)

        assert repo.exists(User, 1) is True
        assert repo.exists(User, 999) is False

    def test_find_by(self, repo):
        repo.save(User(name="John", email="john@example.com", age=30))
        repo.save(User(name="Jane", email="jane@example.com", age=25))
        repo.save(User(name="Bob", email="bob@example.com", age=30))

        users_age_30 = repo.find_by(User, age=30)
        assert len(users_age_30) == 2

    def test_first_by(self, repo):
        repo.save(User(name="John", email="john@example.com", age=30))
        repo.save(User(name="Jane", email="jane@example.com", age=25))

        user = repo.first_by(User, age=25)
        assert user is not None
        assert user.name == "Jane"

    def test_count(self, repo):
        assert repo.count(User) == 0

        repo.save(User(name="John", email="john@example.com"))
        repo.save(User(name="Jane", email="jane@example.com"))

        assert repo.count(User) == 2

    def test_clear(self, repo):
        repo.save(User(name="John", email="john@example.com"))
        repo.save(User(name="Jane", email="jane@example.com"))

        repo.clear()
        assert repo.count(User) == 0


# ==================== CRUD Instance Methods ====================

class TestEntityCRUD:
    """Tests for Entity CRUD instance methods"""

    def test_save_instance_method(self, repo):
        user = User(name="John", email="john@example.com")
        user.save()

        assert user.id == 1
        assert not user.is_new  # Property

    def test_delete_instance_method(self, repo):
        user = User(name="John", email="john@example.com")
        user.save()

        result = user.delete()
        assert result is True
        assert repo.find(User, 1) is None

    def test_reload_instance_method(self, repo):
        user = User(name="John", email="john@example.com")
        user.save()

        # Modify the stored version directly
        stored = repo.find(User, 1)
        stored.name = "Jane"
        repo.save(stored)

        # Reload should get the updated value
        user.reload()
        assert user.name == "Jane"


# ==================== CRUD Class Methods ====================

class TestEntityClassMethods:
    """Tests for Entity CRUD class methods"""

    def test_create(self, repo):
        user = User.create(name="John", email="john@example.com", age=30)

        assert user.id == 1
        assert user.name == "John"
        assert not user.is_new  # Property

    def test_find_class_method(self, repo):
        User.create(name="John", email="john@example.com")

        user = User.find(1)
        assert user is not None
        assert user.name == "John"

    def test_find_all_class_method(self, repo):
        User.create(name="John", email="john@example.com")
        User.create(name="Jane", email="jane@example.com")

        users = User.find_all()
        assert len(users) == 2

    def test_find_by_class_method(self, repo):
        User.create(name="John", email="john@example.com", age=30)
        User.create(name="Jane", email="jane@example.com", age=25)

        users = User.find_by(age=30)
        assert len(users) == 1
        assert users[0].name == "John"

    def test_first_by_class_method(self, repo):
        User.create(name="John", email="john@example.com", age=30)
        User.create(name="Jane", email="jane@example.com", age=25)

        user = User.first_by(age=25)
        assert user.name == "Jane"

    def test_exists_class_method(self, repo):
        User.create(name="John", email="john@example.com")

        assert User.exists(1) is True
        assert User.exists(999) is False

    def test_count_class_method(self, repo):
        assert User.count() == 0

        User.create(name="John", email="john@example.com")
        User.create(name="Jane", email="jane@example.com")

        assert User.count() == 2


# ==================== Transaction Tests ====================

class TestTransactionalRepository:
    """Tests for TransactionalInMemoryRepository"""

    def test_successful_transaction(self, tx_repo):
        with tx_repo.transaction():
            user = User(name="John", email="john@example.com")
            tx_repo.save(user)

        # Should persist after commit
        assert tx_repo.count(User) == 1

    def test_rollback_on_exception(self, tx_repo):
        try:
            with tx_repo.transaction():
                user = User(name="John", email="john@example.com")
                tx_repo.save(user)
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Should rollback
        assert tx_repo.count(User) == 0

    def test_rollback_restores_deleted_entity(self, tx_repo):
        # First save a user
        user = User(name="John", email="john@example.com")
        tx_repo.save(user)

        # Then try to delete in a failing transaction
        try:
            with tx_repo.transaction():
                tx_repo.delete(user)
                assert tx_repo.count(User) == 0
                raise ValueError("Rollback")
        except ValueError:
            pass

        # User should be restored
        assert tx_repo.count(User) == 1

    def test_rollback_restores_auto_increment(self, tx_repo):
        # Save and commit one user
        user1 = User(name="John", email="john@example.com")
        tx_repo.save(user1)
        assert user1.id == 1

        # Try to save another in failing transaction
        try:
            with tx_repo.transaction():
                user2 = User(name="Jane", email="jane@example.com")
                tx_repo.save(user2)
                assert user2.id == 2
                raise ValueError("Rollback")
        except ValueError:
            pass

        # Next save should still get id=2 (counter restored)
        user3 = User(name="Bob", email="bob@example.com")
        tx_repo.save(user3)
        assert user3.id == 2


# ==================== Entity Registry Tests ====================

class TestEntityRegistry:
    """Tests for EntityRegistry"""

    def test_register_entity(self):
        EntityRegistry.clear()

        @register_entity
        class TestEntity(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

        assert EntityRegistry.get("TestEntity") is TestEntity
        EntityRegistry.clear()

    def test_list_entities(self):
        EntityRegistry.clear()

        @register_entity
        class Entity1(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None

        @register_entity
        class Entity2(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None

        entities = EntityRegistry.list_entities()
        assert len(entities) == 2
        EntityRegistry.clear()

    def test_list_names(self):
        EntityRegistry.clear()

        @register_entity
        class MyEntity(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None

        names = EntityRegistry.list_names()
        assert "MyEntity" in names
        EntityRegistry.clear()

    def test_get_manifest(self):
        EntityRegistry.clear()

        @register_entity
        class ManifestEntity(EntityBase):
            """Test entity for manifest"""
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str
            value: int = 0

        manifest = EntityRegistry.get_manifest()
        assert "ManifestEntity" in manifest["entities"]
        assert manifest["entities"]["ManifestEntity"]["primary_key_field"] == "id"
        EntityRegistry.clear()

    def test_unregister_entity(self):
        EntityRegistry.clear()

        @register_entity
        class TempEntity(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None

        assert EntityRegistry.get("TempEntity") is not None
        EntityRegistry.unregister(TempEntity)  # Takes class, not string
        assert EntityRegistry.get("TempEntity") is None
        EntityRegistry.clear()


# ==================== Repository Registry Tests ====================

class TestRepositoryRegistry:
    """Tests for RepositoryRegistry"""

    def test_set_default_repository(self):
        RepositoryRegistry.clear()

        repo = InMemoryRepository()
        RepositoryRegistry.set_default(repo)

        assert RepositoryRegistry.get(User) is repo
        RepositoryRegistry.clear()

    def test_register_per_entity(self):
        RepositoryRegistry.clear()

        user_repo = InMemoryRepository()
        product_repo = InMemoryRepository()

        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Product, product_repo)

        assert RepositoryRegistry.get(User) is user_repo
        assert RepositoryRegistry.get(Product) is product_repo
        RepositoryRegistry.clear()

    def test_entity_specific_overrides_default(self):
        RepositoryRegistry.clear()

        default_repo = InMemoryRepository()
        user_repo = InMemoryRepository()

        RepositoryRegistry.set_default(default_repo)
        RepositoryRegistry.register(User, user_repo)

        assert RepositoryRegistry.get(User) is user_repo
        assert RepositoryRegistry.get(Product) is default_repo
        RepositoryRegistry.clear()


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_save_without_repository_raises(self):
        RepositoryRegistry.clear()

        user = User(name="John", email="john@example.com")
        with pytest.raises(ValueError, match="No repository configured"):
            user.save()

    def test_find_without_repository_raises(self):
        RepositoryRegistry.clear()

        with pytest.raises(ValueError, match="No repository configured"):
            User.find(1)

    def test_nested_transaction_raises(self, tx_repo):
        with tx_repo.transaction():
            with pytest.raises(ValueError, match="Already in a transaction"):
                tx_repo.begin_transaction()

    def test_commit_without_transaction_raises(self, tx_repo):
        with pytest.raises(ValueError, match="No transaction"):
            tx_repo.commit_transaction()

    def test_rollback_without_transaction_raises(self, tx_repo):
        with pytest.raises(ValueError, match="No transaction"):
            tx_repo.rollback_transaction()
