"""
In-memory implementation of CRUDDriver for foobara-py.
"""

import threading
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from foobara_py.persistence.crud_driver import (
    CannotDeleteError,
    CannotFindError,
    CannotInsertError,
    CannotUpdateError,
    CRUDDriver,
    CRUDTable,
)


class InMemoryCRUDTable(CRUDTable):
    """
    In-memory implementation of CRUDTable.
    """

    def __init__(
        self, entity_class: Type, driver: "InMemoryCRUDDriver", table_name: Optional[str] = None
    ):
        super().__init__(entity_class, driver, table_name)
        self._data: Dict[Any, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._auto_increment = 0

    def find(self, record_id: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._data.get(record_id)

    def all(self, page_size: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        with self._lock:
            results = list(self._data.values())
            if page_size:
                results = results[:page_size]
            return results

    def insert(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            pk_field = self.entity_class._primary_key_field
            record_id = attributes.get(pk_field)

            if record_id is None:
                self._auto_increment += 1
                record_id = self._auto_increment
                attributes[pk_field] = record_id

            if record_id in self._data:
                raise CannotInsertError(record_id, "already exists")

            self._data[record_id] = attributes.copy()
            return self._data[record_id]

    def update(self, record_id: Any, attributes: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if record_id not in self._data:
                raise CannotUpdateError(record_id, "does not exist")

            self._data[record_id].update(attributes)
            return self._data[record_id]

    def delete(self, record_id: Any) -> bool:
        with self._lock:
            if record_id in self._data:
                del self._data[record_id]
                return True
            return False

    def count(self) -> int:
        with self._lock:
            return len(self._data)

    def select(
        self,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        with self._lock:
            results = list(self._data.values())

            if where:
                results = [r for r in results if all(r.get(k) == v for k, v in where.items())]

            if order_by:
                if isinstance(order_by, str):
                    order_by = [order_by]
                for field in reversed(order_by):  # Multiple fields: sort by last first
                    reverse = field.startswith("-")
                    key_field = field[1:] if reverse else field
                    results.sort(key=lambda x: x.get(key_field), reverse=reverse)

            start = offset or 0
            end = start + limit if limit else None
            return results[start:end]


class InMemoryCRUDDriver(CRUDDriver):
    """
    In-memory CRUDDriver.
    """

    def table_for(self, entity_class: Type) -> InMemoryCRUDTable:
        entity_name = entity_class.__name__
        if entity_name not in self._tables:
            self._tables[entity_name] = InMemoryCRUDTable(entity_class, self)
        return self._tables[entity_name]
