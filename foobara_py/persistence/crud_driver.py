"""
Abstract interface for CRUD drivers in foobara-py.

CRUD drivers provide a low-level abstraction for storage technologies
(SQL, NoSQL, Files, etc.) that the Repository layer uses.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Type, Union


class CannotCrudError(Exception):
    """Base class for CRUD errors"""

    def __init__(self, record_id: Any, message: Optional[str] = None):
        self.record_id = record_id
        verb = self.__class__.__name__.replace("Cannot", "").replace("Error", "").lower()
        full_message = f"Could not {verb} for id {record_id!r}"
        if message:
            full_message = f"{full_message}: {message}"
        super().__init__(full_message)


class CannotFindError(CannotCrudError):
    """Raised when a record cannot be found"""


class CannotInsertError(CannotCrudError):
    """Raised when a record cannot be inserted"""


class CannotUpdateError(CannotCrudError):
    """Raised when a record cannot be updated"""


class CannotDeleteError(CannotCrudError):
    """Raised when a record cannot be deleted"""


class CRUDTable(ABC):
    """
    Abstract base class for a CRUD table/collection.

    Handles low-level storage operations for a specific entity type.
    """

    def __init__(self, entity_class: Type, driver: "CRUDDriver", table_name: Optional[str] = None):
        self.entity_class = entity_class
        self.driver = driver
        self.table_name = table_name or self._default_table_name(entity_class)

    def _default_table_name(self, entity_class: Type) -> str:
        """Generate default table name from entity class"""
        name = entity_class.__name__
        # Simple camelCase/PascalCase to snake_case conversion could go here
        # For now, just use the name as-is or lowercase it
        return name.lower()

    @abstractmethod
    def find(self, record_id: Any) -> Optional[Dict[str, Any]]:
        """Find record attributes by primary key"""
        pass

    def find_or_raise(self, record_id: Any) -> Dict[str, Any]:
        """Find record or raise CannotFindError"""
        attributes = self.find(record_id)
        if attributes is None:
            raise CannotFindError(record_id, "does not exist")
        return attributes

    @abstractmethod
    def all(self, page_size: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        """Return all records in the table"""
        pass

    @abstractmethod
    def insert(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record and return its attributes (including generated PK)"""
        pass

    @abstractmethod
    def update(self, record_id: Any, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record and return its full attributes"""
        pass

    @abstractmethod
    def delete(self, record_id: Any) -> bool:
        """Delete a record by primary key, return True if deleted"""
        pass

    @abstractmethod
    def count(self) -> int:
        """Count total records in the table"""
        pass

    @abstractmethod
    def select(
        self,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Select records matching criteria"""
        pass

    def exists(self, record_id: Any) -> bool:
        """Check if record exists"""
        return self.find(record_id) is not None

    def find_by(self, **criteria) -> Optional[Dict[str, Any]]:
        """Find first record matching criteria"""
        for record in self.all():
            if all(record.get(k) == v for k, v in criteria.items()):
                return record
        return None

    def find_all_by(self, **criteria) -> List[Dict[str, Any]]:
        """Find all records matching criteria"""
        results = []
        for record in self.all():
            if all(record.get(k) == v for k, v in criteria.items()):
                results.append(record)
        return results


class CRUDDriver(ABC):
    """
    Abstract base class for CRUD drivers.

    Manages connections and provides access to CRUDTable instances.
    """

    def __init__(self, connection_info: Any = None, table_prefix: Optional[str] = None):
        self.connection_info = connection_info
        self.table_prefix = table_prefix
        self._tables: Dict[str, CRUDTable] = {}

    @abstractmethod
    def table_for(self, entity_class: Type) -> CRUDTable:
        """Get or create a CRUDTable for the given entity class"""
        pass

    # Transaction support (optional/default no-op)
    def begin_transaction(self) -> Any:
        """Begin a transaction, return a raw transaction object if supported"""
        return None

    def commit_transaction(self, raw_tx: Any) -> None:
        """Commit the given transaction"""
        pass

    def rollback_transaction(self, raw_tx: Any) -> None:
        """Rollback the given transaction"""
        pass
