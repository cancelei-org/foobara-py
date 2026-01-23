import pytest
from typing import Optional, List, Union

pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed - persistence tests require: pip install foobara-py[persistence]")
from sqlalchemy import create_engine
from foobara_py.persistence.entity import EntityBase
from foobara_py.persistence.crud_driver import CannotFindError
from foobara_py.persistence.in_memory_driver import InMemoryCRUDDriver
from foobara_py.persistence.sqlalchemy_driver import SQLAlchemyDriver
from foobara_py.persistence.mapping import entity_to_sqlalchemy_table


class User(EntityBase):
    id: Optional[int] = None
    name: str
    email: str
    active: bool = True


@pytest.fixture
def in_memory_driver():
    return InMemoryCRUDDriver()


@pytest.fixture
def sqlite_driver():
    engine = create_engine("sqlite:///:memory:")
    driver = SQLAlchemyDriver(engine)
    # Create table manually for now
    table = entity_to_sqlalchemy_table(User, driver.metadata)
    table.create(engine)
    return driver


def test_in_memory_driver_crud(in_memory_driver):
    table = in_memory_driver.table_for(User)
    
    # Create
    user_data = {"name": "John", "email": "john@example.com"}
    created = table.insert(user_data)
    assert created["id"] == 1
    assert created["name"] == "John"
    
    # Find
    found = table.find(1)
    assert found == created
    
    # Update
    updated = table.update(1, {"name": "Johnny"})
    assert updated["name"] == "Johnny"
    assert table.find(1)["name"] == "Johnny"
    
    # Count
    assert table.count() == 1
    
    # Delete
    assert table.delete(1) is True
    assert table.count() == 0
    assert table.find(1) is None


def test_sqlite_driver_crud(sqlite_driver):
    table = sqlite_driver.table_for(User)
    
    # Create
    user_data = {"name": "Jane", "email": "jane@example.com", "active": True}
    created = table.insert(user_data)
    assert created["id"] is not None
    assert created["name"] == "Jane"
    
    # Find
    found = table.find(created["id"])
    assert found == created
    
    # Update
    table.update(created["id"], {"name": "Janey"})
    assert table.find(created["id"])["name"] == "Janey"
    
    # Select with where
    results = table.select(where={"active": True})
    assert len(results) == 1
    assert results[0]["name"] == "Janey"
    
    # Delete
    assert table.delete(created["id"]) is True
    assert table.count() == 0


def test_select_ordering_and_limit(in_memory_driver):
    table = in_memory_driver.table_for(User)
    table.insert({"name": "B", "email": "b@example.com"})
    table.insert({"name": "A", "email": "a@example.com"})
    table.insert({"name": "C", "email": "c@example.com"})
    
    # Order by name
    results = table.select(order_by="name")
    assert [r["name"] for r in results] == ["A", "B", "C"]
    
    # Order by name descending
    results = table.select(order_by="-name")
    assert [r["name"] for r in results] == ["C", "B", "A"]
    
    # Limit
    results = table.select(order_by="name", limit=2)
    assert [r["name"] for r in results] == ["A", "B"]
    
    # Offset
    results = table.select(order_by="name", limit=2, offset=1)
    assert [r["name"] for r in results] == ["B", "C"]
