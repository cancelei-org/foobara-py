"""Tests for Local Files CRUD Driver"""

import pytest
import tempfile
import shutil
from pathlib import Path

from foobara_py.persistence import (
    EntityBase,
    LocalFilesCRUDDriver,
    LocalFilesCRUDTable,
    CannotInsertError,
    CannotUpdateError,
)


# Test entities
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
def temp_dir():
    """Create temporary directory for test data"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def files_driver(temp_dir):
    """Create local files driver with temp directory"""
    driver = LocalFilesCRUDDriver(base_path=temp_dir)
    yield driver
    # Cleanup
    driver.clear_all()


@pytest.fixture
def user_table(files_driver):
    """Create user table"""
    return files_driver.table_for(User)


class TestLocalFilesCRUDDriver:
    """Test LocalFilesCRUDDriver class"""

    def test_creates_driver(self, temp_dir):
        """Should create local files driver"""
        driver = LocalFilesCRUDDriver(base_path=temp_dir)
        assert driver is not None
        assert driver.base_path == Path(temp_dir)

    def test_creates_base_directory(self, temp_dir):
        """Should create base directory if it doesn't exist"""
        new_path = Path(temp_dir) / "subdir" / "data"
        driver = LocalFilesCRUDDriver(base_path=str(new_path))
        assert new_path.exists()

    def test_table_for(self, files_driver):
        """Should create table for entity"""
        table = files_driver.table_for(User)
        assert isinstance(table, LocalFilesCRUDTable)
        assert table.entity_class == User

    def test_table_directory_created(self, files_driver):
        """Should create table directory"""
        table = files_driver.table_for(User)
        assert table.table_dir.exists()
        assert table.table_dir.is_dir()

    def test_table_prefix(self, temp_dir):
        """Should use table prefix"""
        driver = LocalFilesCRUDDriver(base_path=temp_dir, table_prefix="test_")
        table = driver.table_for(User)
        assert table.table_name == "test_user"

    def test_clear_all(self, files_driver, user_table):
        """Should clear all data"""
        user_table.insert({"name": "Alice", "email": "alice@example.com"})
        assert user_table.count() == 1

        files_driver.clear_all()

        # Need to recreate table after clear_all
        user_table = files_driver.table_for(User)
        assert user_table.count() == 0


class TestLocalFilesCRUDTable:
    """Test LocalFilesCRUDTable class"""

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


class TestLocalFilesCRUDTableComplexTypes:
    """Test Local Files CRUD with complex data types"""

    def test_store_dict(self, files_driver):
        """Should store and retrieve dict values"""
        table = files_driver.table_for(Product)

        attrs = {
            "name": "Widget",
            "price": 19.99,
            "metadata": {"color": "red", "size": "large"}
        }
        inserted = table.insert(attrs)
        record_id = inserted["id"]

        found = table.find(record_id)

        assert found["metadata"] == {"color": "red", "size": "large"}

    def test_store_list(self, files_driver):
        """Should store and retrieve list values"""
        class Article(EntityBase):
            _primary_key_field = 'id'
            id: int = None
            title: str
            tags: list = []

        table = files_driver.table_for(Article)

        attrs = {
            "title": "Test Article",
            "tags": ["python", "testing", "files"]
        }
        inserted = table.insert(attrs)
        record_id = inserted["id"]

        found = table.find(record_id)

        assert found["tags"] == ["python", "testing", "files"]

    def test_store_float(self, files_driver):
        """Should store and retrieve float values"""
        table = files_driver.table_for(Product)

        attrs = {
            "name": "Widget",
            "price": 19.99,
            "metadata": {}
        }
        inserted = table.insert(attrs)
        record_id = inserted["id"]

        found = table.find(record_id)

        assert abs(found["price"] - 19.99) < 0.01


class TestLocalFilesCRUDTableAutoIncrement:
    """Test auto-increment ID generation"""

    def test_auto_increment_ids(self, user_table):
        """Should auto-increment IDs"""
        result1 = user_table.insert({"name": "Alice", "email": "alice@example.com"})
        result2 = user_table.insert({"name": "Bob", "email": "bob@example.com"})
        result3 = user_table.insert({"name": "Charlie", "email": "charlie@example.com"})

        assert result1["id"] == 1
        assert result2["id"] == 2
        assert result3["id"] == 3

    def test_counter_persistence(self, files_driver):
        """Should persist counter across table recreations"""
        table1 = files_driver.table_for(User)
        table1.insert({"name": "Alice", "email": "alice@example.com"})
        table1.insert({"name": "Bob", "email": "bob@example.com"})

        # Create new table instance (simulates restart)
        table2 = files_driver.table_for(User)
        result = table2.insert({"name": "Charlie", "email": "charlie@example.com"})

        # Should continue from where we left off
        assert result["id"] == 3
