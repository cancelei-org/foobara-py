"""Tests for Redis CRUD Driver"""

import pytest
from pydantic import BaseModel

from foobara_py.persistence import (
    EntityBase,
    RedisCRUDDriver,
    RedisCRUDTable,
    CannotInsertError,
    CannotUpdateError,
)


# Test entity
class User(EntityBase):
    """Test user entity"""
    _primary_key_field = 'id'

    id: int = None
    name: str
    email: str
    age: int = 0


class Product(EntityBase):
    """Test product entity"""
    _primary_key_field = 'id'

    id: int = None
    name: str
    price: float
    metadata: dict = {}


@pytest.fixture
def redis_driver():
    """Create Redis driver with fakeredis"""
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    # Use fakeredis for testing
    fake_redis = fakeredis.FakeRedis()
    driver = RedisCRUDDriver(fake_redis)

    yield driver

    # Cleanup
    fake_redis.flushdb()


@pytest.fixture
def user_table(redis_driver):
    """Create user table"""
    return redis_driver.table_for(User)


class TestRedisCRUDDriver:
    """Test RedisCRUDDriver class"""

    def test_creates_driver(self):
        """Should create Redis driver"""
        try:
            import fakeredis
        except ImportError:
            pytest.skip("fakeredis not installed")

        fake_redis = fakeredis.FakeRedis()
        driver = RedisCRUDDriver(fake_redis)
        assert driver is not None

    def test_creates_driver_from_url(self):
        """Should create driver from URL"""
        # This will fail without real Redis, so skip
        pytest.skip("Requires real Redis server")

    def test_table_for(self, redis_driver):
        """Should create table for entity"""
        table = redis_driver.table_for(User)
        assert isinstance(table, RedisCRUDTable)
        assert table.entity_class == User

    def test_ping(self, redis_driver):
        """Should ping Redis"""
        assert redis_driver.ping() is True

    def test_flush_db(self, redis_driver):
        """Should flush database"""
        table = redis_driver.table_for(User)
        table.insert({"name": "Alice", "email": "alice@example.com"})

        assert table.count() == 1

        redis_driver.flush_db()

        assert table.count() == 0


class TestRedisCRUDTable:
    """Test RedisCRUDTable class"""

    def test_insert_without_id(self, user_table):
        """Should insert record without ID"""
        attrs = {"name": "Alice", "email": "alice@example.com", "age": 30}
        result = user_table.insert(attrs)

        assert result["id"] is not None
        assert result["name"] == "Alice"
        assert result["email"] == "alice@example.com"
        assert result["age"] == 30

    def test_insert_with_id(self, user_table):
        """Should insert record with ID"""
        attrs = {"id": 42, "name": "Bob", "email": "bob@example.com", "age": 25}
        result = user_table.insert(attrs)

        assert result["id"] == 42
        assert result["name"] == "Bob"

    def test_insert_duplicate_id(self, user_table):
        """Should raise error for duplicate ID"""
        attrs1 = {"id": 1, "name": "Alice", "email": "alice@example.com"}
        attrs2 = {"id": 1, "name": "Bob", "email": "bob@example.com"}

        user_table.insert(attrs1)

        with pytest.raises(CannotInsertError):
            user_table.insert(attrs2)

    def test_find_existing(self, user_table):
        """Should find existing record"""
        attrs = {"name": "Alice", "email": "alice@example.com", "age": 30}
        inserted = user_table.insert(attrs)
        record_id = inserted["id"]

        found = user_table.find(record_id)

        assert found is not None
        assert found["id"] == record_id
        assert found["name"] == "Alice"
        assert found["age"] == 30

    def test_find_nonexistent(self, user_table):
        """Should return None for nonexistent record"""
        found = user_table.find(999)
        assert found is None

    def test_update_existing(self, user_table):
        """Should update existing record"""
        attrs = {"name": "Alice", "email": "alice@example.com", "age": 30}
        inserted = user_table.insert(attrs)
        record_id = inserted["id"]

        updated = user_table.update(record_id, {"age": 31, "email": "alice.new@example.com"})

        assert updated["age"] == 31
        assert updated["email"] == "alice.new@example.com"
        assert updated["name"] == "Alice"  # Should keep old value

    def test_update_nonexistent(self, user_table):
        """Should raise error for nonexistent record"""
        with pytest.raises(CannotUpdateError):
            user_table.update(999, {"name": "Bob"})

    def test_delete_existing(self, user_table):
        """Should delete existing record"""
        attrs = {"name": "Alice", "email": "alice@example.com"}
        inserted = user_table.insert(attrs)
        record_id = inserted["id"]

        result = user_table.delete(record_id)

        assert result is True
        assert user_table.find(record_id) is None

    def test_delete_nonexistent(self, user_table):
        """Should return False for nonexistent record"""
        result = user_table.delete(999)
        assert result is False

    def test_all(self, user_table):
        """Should return all records"""
        user_table.insert({"name": "Alice", "email": "alice@example.com"})
        user_table.insert({"name": "Bob", "email": "bob@example.com"})
        user_table.insert({"name": "Charlie", "email": "charlie@example.com"})

        all_records = list(user_table.all())

        assert len(all_records) == 3
        names = [r["name"] for r in all_records]
        assert "Alice" in names
        assert "Bob" in names
        assert "Charlie" in names

    def test_all_with_page_size(self, user_table):
        """Should limit results with page_size"""
        user_table.insert({"name": "Alice", "email": "alice@example.com"})
        user_table.insert({"name": "Bob", "email": "bob@example.com"})
        user_table.insert({"name": "Charlie", "email": "charlie@example.com"})

        results = list(user_table.all(page_size=2))

        assert len(results) == 2

    def test_count(self, user_table):
        """Should count records"""
        assert user_table.count() == 0

        user_table.insert({"name": "Alice", "email": "alice@example.com"})
        assert user_table.count() == 1

        user_table.insert({"name": "Bob", "email": "bob@example.com"})
        assert user_table.count() == 2

    def test_exists(self, user_table):
        """Should check if record exists"""
        attrs = {"name": "Alice", "email": "alice@example.com"}
        inserted = user_table.insert(attrs)
        record_id = inserted["id"]

        assert user_table.exists(record_id) is True
        assert user_table.exists(999) is False

    def test_select_with_where(self, user_table):
        """Should select records with where clause"""
        user_table.insert({"name": "Alice", "email": "alice@example.com", "age": 30})
        user_table.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
        user_table.insert({"name": "Charlie", "email": "charlie@example.com", "age": 30})

        results = list(user_table.select(where={"age": 30}))

        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "Alice" in names
        assert "Charlie" in names

    def test_select_with_order_by(self, user_table):
        """Should select records with ordering"""
        user_table.insert({"name": "Charlie", "email": "c@example.com", "age": 35})
        user_table.insert({"name": "Alice", "email": "a@example.com", "age": 30})
        user_table.insert({"name": "Bob", "email": "b@example.com", "age": 25})

        results = list(user_table.select(order_by="name"))

        assert results[0]["name"] == "Alice"
        assert results[1]["name"] == "Bob"
        assert results[2]["name"] == "Charlie"

    def test_select_with_reverse_order(self, user_table):
        """Should select records in reverse order"""
        user_table.insert({"name": "Alice", "email": "a@example.com", "age": 30})
        user_table.insert({"name": "Bob", "email": "b@example.com", "age": 25})
        user_table.insert({"name": "Charlie", "email": "c@example.com", "age": 35})

        results = list(user_table.select(order_by="-age"))

        assert results[0]["age"] == 35
        assert results[1]["age"] == 30
        assert results[2]["age"] == 25

    def test_select_with_limit_offset(self, user_table):
        """Should select records with limit and offset"""
        for i in range(10):
            user_table.insert({"name": f"User{i}", "email": f"user{i}@example.com"})

        results = list(user_table.select(limit=3, offset=2, order_by="name"))

        assert len(results) == 3

    def test_find_by(self, user_table):
        """Should find first record matching criteria"""
        user_table.insert({"name": "Alice", "email": "alice@example.com", "age": 30})
        user_table.insert({"name": "Bob", "email": "bob@example.com", "age": 30})

        result = user_table.find_by(age=30)

        assert result is not None
        assert result["age"] == 30

    def test_find_all_by(self, user_table):
        """Should find all records matching criteria"""
        user_table.insert({"name": "Alice", "email": "alice@example.com", "age": 30})
        user_table.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
        user_table.insert({"name": "Charlie", "email": "charlie@example.com", "age": 30})

        results = user_table.find_all_by(age=30)

        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "Alice" in names
        assert "Charlie" in names


class TestRedisCRUDTableComplexTypes:
    """Test Redis CRUD with complex data types"""

    def test_store_dict(self, redis_driver):
        """Should store and retrieve dict values"""
        table = redis_driver.table_for(Product)

        attrs = {
            "name": "Widget",
            "price": 19.99,
            "metadata": {"color": "red", "size": "large"}
        }
        inserted = table.insert(attrs)
        record_id = inserted["id"]

        found = table.find(record_id)

        assert found["metadata"] == {"color": "red", "size": "large"}

    def test_store_list(self, redis_driver):
        """Should store and retrieve list values"""
        class Article(EntityBase):
            _primary_key_field = 'id'
            id: int = None
            title: str
            tags: list = []

        table = redis_driver.table_for(Article)

        attrs = {
            "title": "Test Article",
            "tags": ["python", "redis", "testing"]
        }
        inserted = table.insert(attrs)
        record_id = inserted["id"]

        found = table.find(record_id)

        assert found["tags"] == ["python", "redis", "testing"]

    def test_store_float(self, redis_driver):
        """Should store and retrieve float values"""
        table = redis_driver.table_for(Product)

        attrs = {
            "name": "Widget",
            "price": 19.99,
            "metadata": {}
        }
        inserted = table.insert(attrs)
        record_id = inserted["id"]

        found = table.find(record_id)

        assert abs(found["price"] - 19.99) < 0.01


class TestRedisCRUDTableTTL:
    """Test Redis CRUD with TTL support"""

    def test_ttl_support(self, redis_driver):
        """Should support TTL for cached entities"""
        table = redis_driver.table_for(User, ttl=3600)

        attrs = {"name": "Alice", "email": "alice@example.com"}
        inserted = table.insert(attrs)
        record_id = inserted["id"]

        # Check that key has TTL set
        key = table._record_key(record_id)
        ttl = redis_driver.redis.ttl(key)

        assert ttl > 0
        assert ttl <= 3600


class TestRedisCRUDTransactions:
    """Test Redis transaction support"""

    def test_begin_transaction(self, redis_driver):
        """Should create pipeline for transaction"""
        tx = redis_driver.begin_transaction()
        assert tx is not None

    def test_commit_transaction(self, redis_driver, user_table):
        """Should commit transaction"""
        tx = redis_driver.begin_transaction()

        # Operations in transaction
        attrs1 = {"name": "Alice", "email": "alice@example.com"}
        attrs2 = {"name": "Bob", "email": "bob@example.com"}

        user_table.insert(attrs1)
        user_table.insert(attrs2)

        redis_driver.commit_transaction(tx)

        assert user_table.count() == 2

    def test_rollback_transaction(self, redis_driver):
        """Should rollback transaction"""
        tx = redis_driver.begin_transaction()

        # Reset pipeline
        redis_driver.rollback_transaction(tx)

        # Pipeline should be reset
        assert tx is not None


class TestRedisCRUDMultipleTables:
    """Test Redis CRUD with multiple entity types"""

    def test_separate_tables(self, redis_driver):
        """Should maintain separate tables for different entities"""
        user_table = redis_driver.table_for(User)
        product_table = redis_driver.table_for(Product)

        user_table.insert({"name": "Alice", "email": "alice@example.com"})
        product_table.insert({"name": "Widget", "price": 19.99, "metadata": {}})

        assert user_table.count() == 1
        assert product_table.count() == 1

    def test_table_prefix(self):
        """Should use table prefix"""
        try:
            import fakeredis
        except ImportError:
            pytest.skip("fakeredis not installed")

        fake_redis = fakeredis.FakeRedis()
        driver = RedisCRUDDriver(fake_redis, table_prefix="test_")

        table = driver.table_for(User)

        assert table.table_name == "test_user"
