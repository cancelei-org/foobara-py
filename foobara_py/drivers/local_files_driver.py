"""
Local files CRUD driver for Foobara Python.

Provides file-system based entity storage using YAML or JSON.
Each entity type is stored in a separate directory, with each entity as a separate file.
This provides human-readable storage useful for development, testing, and simple applications.
"""

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, List, Optional, Type

import yaml

from foobara_py.persistence.entity import EntityBase, PrimaryKey
from foobara_py.persistence.repository import Repository


class LocalFilesDriver(Repository):
    """
    File-system based CRUD driver using YAML or JSON.

    Features:
    - Human-readable entity storage
    - Separate directory per entity type
    - Separate file per entity instance
    - File locking for concurrent access
    - Atomic writes via temp files

    Storage structure:
        {base_path}/
            User/
                1.yml
                2.yml
            Post/
                10.yml
                20.yml

    Usage:
        driver = LocalFilesDriver(base_path=".foobara_data", format="yaml")
        User._repository = driver

        user = User(id=1, name="John")
        user.save()  # Writes to .foobara_data/User/1.yml
    """

    def __init__(self, base_path: str = ".foobara_data", format: str = "yaml"):
        """
        Initialize local files driver.

        Args:
            base_path: Root directory for storing entity files
            format: File format - "yaml" or "json"
        """
        self.base_path = Path(base_path)
        self.format = format

        if format not in ("yaml", "json"):
            raise ValueError(f"Unsupported format: {format}. Use 'yaml' or 'json'.")

        # Create base directory
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _entity_dir(self, entity_class: Type[EntityBase]) -> Path:
        """Get directory path for entity type"""
        path = self.base_path / entity_class.__name__
        path.mkdir(exist_ok=True)
        return path

    def _entity_file(self, entity_class: Type[EntityBase], pk: Any) -> Path:
        """Get file path for entity instance"""
        ext = "yml" if self.format == "yaml" else "json"
        return self._entity_dir(entity_class) / f"{pk}.{ext}"

    def _serialize(self, data: dict) -> str:
        """Serialize data to string"""
        if self.format == "yaml":
            return yaml.dump(data, default_flow_style=False, allow_unicode=True)
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _deserialize(self, content: str) -> dict:
        """Deserialize data from string"""
        if self.format == "yaml":
            return yaml.safe_load(content) or {}
        return json.loads(content)

    @contextmanager
    def _file_lock(self, file_path: Path):
        """
        Context manager for file locking.

        Provides exclusive lock for writes, preventing concurrent modifications.
        """
        # Create lock file
        lock_file = file_path.parent / f"{file_path.name}.lock"
        lock_fd = None

        try:
            # Open lock file
            lock_fd = open(lock_file, "w")
            # Acquire exclusive lock
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            # Release lock
            if lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            # Clean up lock file
            if lock_file.exists():
                try:
                    lock_file.unlink()
                except:
                    pass  # Ignore cleanup errors

    def _atomic_write(self, file_path: Path, content: str) -> None:
        """
        Write file atomically using temp file.

        Writes to temp file first, then atomically renames to target.
        This prevents partial writes from being read.
        """
        temp_path = file_path.parent / f"{file_path.name}.tmp"

        try:
            # Write to temp file
            temp_path.write_text(content, encoding="utf-8")
            # Atomic rename
            temp_path.replace(file_path)
        except:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise

    def find(self, entity_class: Type[EntityBase], pk: PrimaryKey) -> Optional[EntityBase]:
        """
        Find entity by primary key.

        Returns:
            Entity instance if found, None otherwise
        """
        file_path = self._entity_file(entity_class, pk)

        if not file_path.exists():
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            data = self._deserialize(content)
            return entity_class.from_persisted(**data)
        except Exception as e:
            # Log error in production
            print(f"Error loading {entity_class.__name__} {pk}: {e}")
            return None

    def find_all(self, entity_class: Type[EntityBase]) -> List[EntityBase]:
        """
        Find all entities of a type.

        Returns:
            List of all entity instances
        """
        entity_dir = self._entity_dir(entity_class)
        entities = []

        # Get file extension pattern
        ext_pattern = "*.yml" if self.format == "yaml" else "*.json"

        for file_path in entity_dir.glob(ext_pattern):
            try:
                content = file_path.read_text(encoding="utf-8")
                data = self._deserialize(content)
                entities.append(entity_class.from_persisted(**data))
            except Exception as e:
                # Log error but continue processing other files
                print(f"Error loading {file_path}: {e}")
                continue

        return entities

    def save(self, entity: EntityBase) -> EntityBase:
        """
        Save entity (create or update).

        Uses atomic writes and file locking for safety.

        Returns:
            The saved entity
        """
        file_path = self._entity_file(entity.__class__, entity.primary_key)

        # Serialize entity
        data = entity.model_dump()
        content = self._serialize(data)

        # Write atomically with lock
        with self._file_lock(file_path):
            self._atomic_write(file_path, content)

        # Mark entity as persisted
        entity.mark_persisted()

        return entity

    def delete(self, entity: EntityBase) -> bool:
        """
        Delete entity.

        Returns:
            True if deleted, False if not found
        """
        file_path = self._entity_file(entity.__class__, entity.primary_key)

        if not file_path.exists():
            return False

        with self._file_lock(file_path):
            file_path.unlink()

        return True

    def count(self, entity_class: Type[EntityBase]) -> int:
        """
        Count entities of a type.

        Optimized implementation that doesn't load entity data.
        """
        entity_dir = self._entity_dir(entity_class)
        ext_pattern = "*.yml" if self.format == "yaml" else "*.json"
        return sum(1 for _ in entity_dir.glob(ext_pattern))

    def clear(self, entity_class: Optional[Type[EntityBase]] = None) -> None:
        """
        Clear all entities (for testing).

        Args:
            entity_class: If provided, only clear entities of this type.
                         If None, clear all entities.
        """
        if entity_class:
            # Clear specific entity type
            entity_dir = self._entity_dir(entity_class)
            ext_pattern = "*.yml" if self.format == "yaml" else "*.json"
            for file_path in entity_dir.glob(ext_pattern):
                file_path.unlink()
        else:
            # Clear all entity types
            import shutil

            if self.base_path.exists():
                shutil.rmtree(self.base_path)
            self.base_path.mkdir(parents=True, exist_ok=True)
