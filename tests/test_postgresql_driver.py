"""
Tests for PostgreSQLCRUDDriver

These tests require a PostgreSQL database to run.
Set the POSTGRES_TEST_URL environment variable to run these tests:

    export POSTGRES_TEST_URL="postgresql://user:password@localhost:5432/test_db"
    pytest tests/test_postgresql_driver.py
"""

import pytest
import os
from typing import Optional


# Check if PostgreSQL is available
POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="PostgreSQL test database not configured (set POSTGRES_TEST_URL)"
)


@pytest.fixture
def driver():
    """Create a PostgreSQL driver for testing"""
    try:
        from foobara_py.persistence import PostgreSQLCRUDDriver
    except ImportError:
        pytest.skip("psycopg3 not installed")

    driver = PostgreSQLCRUDDriver(POSTGRES_TEST_URL, pool_size=5)

    # Create test table
    with driver.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    email VARCHAR(100),
                    age INTEGER
                )
            """)
            conn.commit()

    yield driver

    # Cleanup: drop test table
    with driver.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS test_users")
            conn.commit()

    driver.close()


@pytest.fixture
def table(driver):
    """Get a table instance for testing"""
    class TestUser:
        __name__ = "TestUser"

    # Clear any existing data
    with driver.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM test_users")
            conn.commit()

    return driver.table_for(TestUser, table_name="test_users")


class TestPostgreSQLCRUDDriver:
    """Test PostgreSQL CRUD driver"""

    def test_insert(self, table):
        """Test inserting a record"""
        attrs = table.insert({
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        })

        assert attrs["id"] is not None
        assert attrs["name"] == "John Doe"
        assert attrs["email"] == "john@example.com"
        assert attrs["age"] == 30

    def test_find(self, table):
        """Test finding a record by ID"""
        # Insert first
        inserted = table.insert({
            "name": "Jane Smith",
            "email": "jane@example.com",
            "age": 25
        })

        # Find by ID
        found = table.find(inserted["id"])

        assert found is not None
        assert found["id"] == inserted["id"]
        assert found["name"] == "Jane Smith"
        assert found["email"] == "jane@example.com"

    def test_find_not_found(self, table):
        """Test finding a non-existent record"""
        result = table.find(99999)
        assert result is None

    def test_update(self, table):
        """Test updating a record"""
        # Insert first
        inserted = table.insert({
            "name": "Bob Johnson",
            "email": "bob@example.com",
            "age": 35
        })

        # Update
        updated = table.update(inserted["id"], {
            "name": "Robert Johnson",
            "age": 36
        })

        assert updated["id"] == inserted["id"]
        assert updated["name"] == "Robert Johnson"
        assert updated["age"] == 36
        assert updated["email"] == "bob@example.com"  # Unchanged

    def test_delete(self, table):
        """Test deleting a record"""
        # Insert first
        inserted = table.insert({
            "name": "Alice Brown",
            "email": "alice@example.com",
            "age": 28
        })

        # Delete
        deleted = table.delete(inserted["id"])
        assert deleted is True

        # Verify it's gone
        found = table.find(inserted["id"])
        assert found is None

    def test_delete_not_found(self, table):
        """Test deleting a non-existent record"""
        deleted = table.delete(99999)
        assert deleted is False

    def test_count(self, table):
        """Test counting records"""
        # Initially empty
        assert table.count() == 0

        # Insert some records
        table.insert({"name": "User 1", "email": "user1@example.com", "age": 20})
        table.insert({"name": "User 2", "email": "user2@example.com", "age": 21})
        table.insert({"name": "User 3", "email": "user3@example.com", "age": 22})

        assert table.count() == 3

    def test_all(self, table):
        """Test fetching all records"""
        # Insert some records
        table.insert({"name": "User A", "email": "a@example.com", "age": 30})
        table.insert({"name": "User B", "email": "b@example.com", "age": 31})
        table.insert({"name": "User C", "email": "c@example.com", "age": 32})

        records = list(table.all())

        assert len(records) == 3
        assert all(isinstance(r, dict) for r in records)
        assert records[0]["name"] == "User A"
        assert records[1]["name"] == "User B"
        assert records[2]["name"] == "User C"

    def test_select_with_where(self, table):
        """Test selecting records with WHERE clause"""
        # Insert some records
        table.insert({"name": "User X", "email": "x@example.com", "age": 25})
        table.insert({"name": "User Y", "email": "y@example.com", "age": 30})
        table.insert({"name": "User Z", "email": "z@example.com", "age": 25})

        # Select records with age = 25
        records = list(table.select(where={"age": 25}))

        assert len(records) == 2
        assert all(r["age"] == 25 for r in records)

    def test_select_with_order_by(self, table):
        """Test selecting records with ORDER BY"""
        # Insert in random order
        table.insert({"name": "Charlie", "email": "c@example.com", "age": 30})
        table.insert({"name": "Alice", "email": "a@example.com", "age": 25})
        table.insert({"name": "Bob", "email": "b@example.com", "age": 28})

        # Select ordered by name
        records = list(table.select(order_by="name"))

        assert len(records) == 3
        assert records[0]["name"] == "Alice"
        assert records[1]["name"] == "Bob"
        assert records[2]["name"] == "Charlie"

    def test_select_with_limit_offset(self, table):
        """Test selecting records with LIMIT and OFFSET"""
        # Insert 5 records
        for i in range(5):
            table.insert({
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "age": 20 + i
            })

        # Get 2 records starting from offset 1
        records = list(table.select(order_by="age", limit=2, offset=1))

        assert len(records) == 2
        assert records[0]["age"] == 21
        assert records[1]["age"] == 22

    def test_exists(self, table):
        """Test checking if record exists"""
        # Insert a record
        inserted = table.insert({
            "name": "Exists Test",
            "email": "exists@example.com",
            "age": 40
        })

        assert table.exists(inserted["id"]) is True
        assert table.exists(99999) is False

    def test_connection_pooling(self, driver):
        """Test that connection pooling works"""
        # Create multiple tables and ensure they all work
        class User1:
            __name__ = "User1"

        class User2:
            __name__ = "User2"

        table1 = driver.table_for(User1, table_name="test_users")
        table2 = driver.table_for(User2, table_name="test_users")

        # Both should work without issues
        count1 = table1.count()
        count2 = table2.count()

        assert count1 == count2

    def test_table_name_conversion(self, driver):
        """Test PascalCase to snake_case table name conversion"""
        class UserAccount:
            __name__ = "UserAccount"

        # Default table name should be snake_case
        table_name = driver._default_table_name(UserAccount)
        assert table_name == "user_account"
