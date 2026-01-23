"""
Redis implementation of CRUDDriver for foobara-py.

Provides Redis-based entity persistence using redis-py.
Stores entities as Redis hashes with key pattern: foobara:{EntityName}:{pk}
"""

import json
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from foobara_py.persistence.crud_driver import (
    CannotDeleteError,
    CannotFindError,
    CannotInsertError,
    CannotUpdateError,
    CRUDDriver,
    CRUDTable,
)


class RedisCRUDTable(CRUDTable):
    """
    Redis implementation of CRUDTable.

    Stores entities as Redis hashes.
    Key pattern: foobara:{table_name}:{record_id}
    Maintains an index set: foobara:{table_name}:_all_ids
    """

    def __init__(
        self,
        entity_class: Type,
        driver: "RedisCRUDDriver",
        table_name: Optional[str] = None,
        ttl: Optional[int] = None,
    ):
        super().__init__(entity_class, driver, table_name)
        self.redis = driver.redis
        self.ttl = ttl  # Optional TTL in seconds
        self._counter_key = f"foobara:{self.table_name}:_counter"
        self._index_key = f"foobara:{self.table_name}:_all_ids"

    def _record_key(self, record_id: Any) -> str:
        """Generate Redis key for a record"""
        return f"foobara:{self.table_name}:{record_id}"

    def _serialize_value(self, value: Any) -> str:
        """Serialize Python value for Redis storage"""
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def _deserialize_value(self, value: str, field_name: str = None) -> Any:
        """Deserialize Redis value to Python"""
        if value == "" or value is None:
            return None
        # Try JSON parse for complex types
        if value.startswith("{") or value.startswith("["):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass
        # Try int conversion
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        # Try float conversion
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
        # Return as string
        return value

    def find(self, record_id: Any) -> Optional[Dict[str, Any]]:
        """Find record by primary key"""
        key = self._record_key(record_id)
        data = self.redis.hgetall(key)

        if not data:
            return None

        # Deserialize all values
        result = {}
        for field, value in data.items():
            field_name = field.decode("utf-8") if isinstance(field, bytes) else field
            val_str = value.decode("utf-8") if isinstance(value, bytes) else value
            result[field_name] = self._deserialize_value(val_str, field_name)

        return result

    def all(self, page_size: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        """Return all records"""
        # Get all IDs from index
        ids = self.redis.smembers(self._index_key)

        results = []
        for record_id in ids:
            rid = record_id.decode("utf-8") if isinstance(record_id, bytes) else record_id
            record = self.find(rid)
            if record:
                results.append(record)

            if page_size and len(results) >= page_size:
                break

        return results

    def insert(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record"""
        pk_field = self.entity_class._primary_key_field
        record_id = attributes.get(pk_field)

        # Generate ID if not provided
        if record_id is None:
            record_id = self.redis.incr(self._counter_key)
            attributes[pk_field] = record_id

        key = self._record_key(record_id)

        # Check if already exists
        if self.redis.exists(key):
            raise CannotInsertError(record_id, "already exists")

        # Serialize and store as hash
        serialized = {k: self._serialize_value(v) for k, v in attributes.items()}

        pipe = self.redis.pipeline()
        pipe.hset(key, mapping=serialized)

        # Add to index
        pipe.sadd(self._index_key, str(record_id))

        # Set TTL if configured
        if self.ttl:
            pipe.expire(key, self.ttl)

        pipe.execute()

        return attributes.copy()

    def update(self, record_id: Any, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record"""
        key = self._record_key(record_id)

        # Check if exists
        if not self.redis.exists(key):
            raise CannotUpdateError(record_id, "does not exist")

        # Serialize values
        serialized = {k: self._serialize_value(v) for k, v in attributes.items()}

        # Update hash
        self.redis.hset(key, mapping=serialized)

        # Reset TTL if configured
        if self.ttl:
            self.redis.expire(key, self.ttl)

        # Return full record
        return self.find(record_id)

    def delete(self, record_id: Any) -> bool:
        """Delete a record"""
        key = self._record_key(record_id)

        # Check if exists
        if not self.redis.exists(key):
            return False

        pipe = self.redis.pipeline()
        pipe.delete(key)
        pipe.srem(self._index_key, str(record_id))
        results = pipe.execute()

        return results[0] > 0

    def count(self) -> int:
        """Count total records"""
        return self.redis.scard(self._index_key)

    def select(
        self,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Select records matching criteria"""
        # Get all records and filter in memory
        # (Redis doesn't have native query support for hashes)
        results = list(self.all())

        if where:
            results = [r for r in results if all(r.get(k) == v for k, v in where.items())]

        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]
            for field in reversed(order_by):
                reverse = field.startswith("-")
                key_field = field[1:] if reverse else field
                results.sort(key=lambda x: x.get(key_field) or "", reverse=reverse)

        start = offset or 0
        end = start + limit if limit else None
        return results[start:end]


class RedisCRUDDriver(CRUDDriver):
    """
    Redis CRUDDriver.

    Args:
        connection_info: Redis connection parameters (URL or dict)
        table_prefix: Prefix for table names (default: None)
        **redis_kwargs: Additional arguments for redis.Redis()

    Usage:
        # Using URL
        driver = RedisCRUDDriver("redis://localhost:6379/0")

        # Using dict
        driver = RedisCRUDDriver({
            "host": "localhost",
            "port": 6379,
            "db": 0
        })

        # With connection pool
        driver = RedisCRUDDriver(
            "redis://localhost:6379/0",
            max_connections=10
        )
    """

    def __init__(
        self, connection_info: Any = None, table_prefix: Optional[str] = None, **redis_kwargs
    ):
        super().__init__(connection_info, table_prefix)

        try:
            import redis
        except ImportError:
            raise ImportError(
                "redis-py is required for RedisCRUDDriver. Install with: pip install redis"
            )

        # Create Redis connection
        if connection_info is None:
            connection_info = "redis://localhost:6379/0"

        if isinstance(connection_info, str):
            self.redis = redis.from_url(connection_info, **redis_kwargs)
        elif isinstance(connection_info, dict):
            self.redis = redis.Redis(**connection_info, **redis_kwargs)
        else:
            # Assume it's already a redis client
            self.redis = connection_info

    def table_for(self, entity_class: Type, ttl: Optional[int] = None) -> RedisCRUDTable:
        """Get or create a RedisCRUDTable for the entity class"""
        entity_name = entity_class.__name__
        if entity_name not in self._tables:
            table_name = self.table_prefix + entity_name if self.table_prefix else entity_name
            self._tables[entity_name] = RedisCRUDTable(
                entity_class, self, table_name.lower(), ttl=ttl
            )
        return self._tables[entity_name]

    def begin_transaction(self) -> Any:
        """Begin a Redis transaction using MULTI/EXEC"""
        return self.redis.pipeline()

    def commit_transaction(self, raw_tx: Any) -> None:
        """Commit Redis transaction (execute pipeline)"""
        if raw_tx:
            raw_tx.execute()

    def rollback_transaction(self, raw_tx: Any) -> None:
        """Rollback Redis transaction (discard pipeline)"""
        if raw_tx:
            raw_tx.reset()

    def close(self):
        """Close Redis connection"""
        if hasattr(self.redis, "close"):
            self.redis.close()

    def flush_db(self):
        """
        Flush current database (WARNING: deletes all keys).

        Use with caution, typically only in tests.
        """
        self.redis.flushdb()

    def ping(self) -> bool:
        """Test Redis connection"""
        try:
            return self.redis.ping()
        except Exception:
            return False
