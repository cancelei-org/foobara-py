"""
Local Files CRUD Driver for foobara-py.

Provides file-based storage using JSON files for development and testing.
Each table is a directory, each record is a JSON file.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from foobara_py.persistence.crud_driver import (
    CannotInsertError,
    CannotUpdateError,
    CRUDDriver,
    CRUDTable,
)


class LocalFilesCRUDDriver(CRUDDriver):
    """
    File-based CRUD driver for development and testing.

    Stores data as JSON files in a directory structure:
    - base_path/
      - table1/
        - 1.json
        - 2.json
      - table2/
        - 1.json

    Features:
    - Simple JSON storage
    - No external dependencies
    - Good for development/testing
    - Human-readable files

    Usage:
        driver = LocalFilesCRUDDriver(base_path="./data")
        table = driver.table_for(User)
        table.insert({"name": "Alice", "email": "alice@example.com"})
    """

    def __init__(self, base_path: str = "./data", table_prefix: Optional[str] = None):
        """
        Initialize local files CRUD driver.

        Args:
            base_path: Root directory for data storage
            table_prefix: Optional prefix for table directories
        """
        super().__init__(connection_info=base_path, table_prefix=table_prefix)
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def table_for(self, entity_class: Type, table_name: Optional[str] = None) -> CRUDTable:
        """Get or create a CRUDTable for the given entity class"""
        if table_name is None:
            table_name = entity_class.__name__.lower()

        if self.table_prefix:
            table_name = f"{self.table_prefix}{table_name}"

        if table_name not in self._tables:
            self._tables[table_name] = LocalFilesCRUDTable(
                entity_class=entity_class, driver=self, table_name=table_name
            )

        return self._tables[table_name]

    def clear_all(self):
        """Clear all data (useful for testing)"""
        if self.base_path.exists():
            shutil.rmtree(self.base_path)
            self.base_path.mkdir(parents=True, exist_ok=True)


class LocalFilesCRUDTable(CRUDTable):
    """
    File-based CRUD table.

    Each record is stored as a separate JSON file named {id}.json.
    """

    def __init__(self, entity_class: Type, driver: LocalFilesCRUDDriver, table_name: str):
        super().__init__(entity_class, driver, table_name)
        self.table_dir = driver.base_path / table_name
        self.table_dir.mkdir(parents=True, exist_ok=True)
        self.counter_file = self.table_dir / ".counter"

    def find(self, record_id: Any) -> Optional[Dict[str, Any]]:
        """Find record by primary key"""
        file_path = self.table_dir / f"{record_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def all(self, page_size: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        """Return all records"""
        records = []
        for file_path in self.table_dir.glob("*.json"):
            if file_path.name == ".counter":
                continue

            try:
                with open(file_path, "r") as f:
                    record = json.load(f)
                    records.append(record)

                    if page_size and len(records) >= page_size:
                        break
            except (json.JSONDecodeError, IOError):
                continue

        return records

    def insert(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record"""
        # Get primary key field
        pk_field = getattr(self.entity_class, "_primary_key_field", "id")
        record_id = attributes.get(pk_field)

        # Auto-generate ID if not provided
        if record_id is None:
            record_id = self._next_id()
            attributes = {**attributes, pk_field: record_id}

        # Check if record already exists
        file_path = self.table_dir / f"{record_id}.json"
        if file_path.exists():
            raise CannotInsertError(record_id, "already exists")

        # Write atomically using temp file
        self._write_atomic(file_path, attributes)

        return attributes.copy()

    def update(self, record_id: Any, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record"""
        file_path = self.table_dir / f"{record_id}.json"

        # Check if record exists
        if not file_path.exists():
            raise CannotUpdateError(record_id, "does not exist")

        # Read current record
        with open(file_path, "r") as f:
            current = json.load(f)

        # Merge updates
        updated = {**current, **attributes}

        # Write atomically
        self._write_atomic(file_path, updated)

        return updated

    def delete(self, record_id: Any) -> bool:
        """Delete a record"""
        file_path = self.table_dir / f"{record_id}.json"

        if not file_path.exists():
            return False

        try:
            file_path.unlink()
            return True
        except OSError:
            return False

    def count(self) -> int:
        """Count total records"""
        count = 0
        for file_path in self.table_dir.glob("*.json"):
            if file_path.name != ".counter":
                count += 1
        return count

    def select(
        self,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Select records matching criteria"""
        # Get all records
        records = list(self.all())

        # Apply where filter
        if where:
            filtered = []
            for record in records:
                if all(record.get(k) == v for k, v in where.items()):
                    filtered.append(record)
            records = filtered

        # Apply ordering
        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]

            for field in reversed(order_by):
                reverse = False
                if field.startswith("-"):
                    field = field[1:]
                    reverse = True

                records.sort(key=lambda r: r.get(field, ""), reverse=reverse)

        # Apply offset
        if offset:
            records = records[offset:]

        # Apply limit
        if limit:
            records = records[:limit]

        return records

    def _next_id(self) -> int:
        """Get next auto-increment ID"""
        # Try to read counter file
        if self.counter_file.exists():
            try:
                with open(self.counter_file, "r") as f:
                    counter = int(f.read().strip())
            except (ValueError, IOError):
                counter = 0
        else:
            counter = 0

        # Increment counter
        next_id = counter + 1

        # Write new counter
        try:
            with open(self.counter_file, "w") as f:
                f.write(str(next_id))
        except IOError:
            pass

        return next_id

    def _write_atomic(self, file_path: Path, data: Dict[str, Any]):
        """Write JSON file atomically using temp file"""
        # Create temp file in same directory
        temp_fd, temp_path = tempfile.mkstemp(dir=self.table_dir, suffix=".json.tmp")

        try:
            # Write to temp file
            with os.fdopen(temp_fd, "w") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            os.replace(temp_path, file_path)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
