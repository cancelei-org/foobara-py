"""
PostgreSQL CRUD driver for foobara-py.

Provides a CRUD interface for PostgreSQL databases using psycopg3.

Features:
- Connection pooling
- Transaction support
- Parameterized queries (SQL injection safe)
- Full CRUD operations
- Query builder support

Usage:
    driver = PostgreSQLCRUDDriver("postgresql://user:pass@localhost/dbname")
    table = driver.table_for(User)

    # Insert
    user_attrs = table.insert({"name": "John", "email": "john@example.com"})

    # Find
    user = table.find(user_attrs["id"])

    # Update
    table.update(user_attrs["id"], {"name": "Jane"})

    # Delete
    table.delete(user_attrs["id"])
"""

from typing import Any, Dict, Iterable, List, Optional, Type

from foobara_py.persistence.crud_driver import (
    CannotDeleteError,
    CannotFindError,
    CannotInsertError,
    CannotUpdateError,
    CRUDDriver,
    CRUDTable,
)


class PostgreSQLCRUDTable(CRUDTable):
    """
    PostgreSQL implementation of CRUDTable.

    Uses psycopg3 for database operations with connection pooling.
    """

    def __init__(
        self,
        entity_class: Type,
        driver: "PostgreSQLCRUDDriver",
        table_name: Optional[str] = None,
        primary_key_field: str = "id",
    ):
        super().__init__(entity_class, driver, table_name)
        self.primary_key_field = primary_key_field

    def _get_connection(self):
        """Get a connection from the pool"""
        return self.driver.pool.connection()

    def find(self, record_id: Any) -> Optional[Dict[str, Any]]:
        """Find record by primary key"""
        sql = f"SELECT * FROM {self.table_name} WHERE {self.primary_key_field} = %s"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (record_id,))
                row = cur.fetchone()

                if row is None:
                    return None

                # Convert row to dict using column names
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, row))

    def all(self, page_size: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        """Return all records in the table"""
        sql = f"SELECT * FROM {self.table_name}"
        if page_size:
            sql += f" LIMIT {page_size}"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [desc[0] for desc in cur.description]

                for row in cur:
                    yield dict(zip(columns, row))

    def insert(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record and return its attributes (including generated PK)"""
        if not attributes:
            raise CannotInsertError(None, "No attributes provided")

        columns = list(attributes.keys())
        placeholders = ["%s"] * len(columns)
        values = [attributes[col] for col in columns]

        sql = f"""
            INSERT INTO {self.table_name} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
            RETURNING *
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, values)
                    row = cur.fetchone()

                    if row is None:
                        raise CannotInsertError(None, "INSERT did not return a row")

                    # Convert row to dict
                    result_columns = [desc[0] for desc in cur.description]
                    result = dict(zip(result_columns, row))

                    # Commit the transaction
                    conn.commit()

                    return result

        except Exception as e:
            raise CannotInsertError(None, f"Insert failed: {e}")

    def update(self, record_id: Any, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record and return its full attributes"""
        if not attributes:
            raise CannotUpdateError(record_id, "No attributes provided")

        # Build SET clause
        set_parts = [f"{col} = %s" for col in attributes.keys()]
        values = list(attributes.values())
        values.append(record_id)  # For WHERE clause

        sql = f"""
            UPDATE {self.table_name}
            SET {", ".join(set_parts)}
            WHERE {self.primary_key_field} = %s
            RETURNING *
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, values)
                    row = cur.fetchone()

                    if row is None:
                        raise CannotUpdateError(record_id, "Record not found or update failed")

                    # Convert row to dict
                    columns = [desc[0] for desc in cur.description]
                    result = dict(zip(columns, row))

                    # Commit the transaction
                    conn.commit()

                    return result

        except CannotUpdateError:
            raise
        except Exception as e:
            raise CannotUpdateError(record_id, f"Update failed: {e}")

    def delete(self, record_id: Any) -> bool:
        """Delete a record by primary key, return True if deleted"""
        sql = f"DELETE FROM {self.table_name} WHERE {self.primary_key_field} = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (record_id,))
                    deleted_count = cur.rowcount

                    # Commit the transaction
                    conn.commit()

                    return deleted_count > 0

        except Exception as e:
            raise CannotDeleteError(record_id, f"Delete failed: {e}")

    def count(self) -> int:
        """Count total records in the table"""
        sql = f"SELECT COUNT(*) FROM {self.table_name}"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchone()
                return result[0] if result else 0

    def select(
        self,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[str | List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Select records matching criteria"""
        sql = f"SELECT * FROM {self.table_name}"
        values = []

        # Build WHERE clause
        if where:
            conditions = [f"{col} = %s" for col in where.keys()]
            sql += f" WHERE {' AND '.join(conditions)}"
            values.extend(where.values())

        # Build ORDER BY clause
        if order_by:
            if isinstance(order_by, str):
                sql += f" ORDER BY {order_by}"
            else:
                sql += f" ORDER BY {', '.join(order_by)}"

        # Add LIMIT and OFFSET
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                columns = [desc[0] for desc in cur.description]

                for row in cur:
                    yield dict(zip(columns, row))


class PostgreSQLCRUDDriver(CRUDDriver):
    """
    PostgreSQL CRUD driver using psycopg3.

    Manages connection pooling and provides CRUDTable instances for entities.

    Features:
    - Connection pooling for performance
    - Transaction support
    - SQL injection protection via parameterized queries
    - Automatic table name derivation

    Usage:
        driver = PostgreSQLCRUDDriver(
            "postgresql://user:password@localhost:5432/mydb",
            pool_size=10
        )

        # Get table for entity
        user_table = driver.table_for(User)

        # CRUD operations
        user_attrs = user_table.insert({"name": "John", "email": "john@example.com"})
    """

    def __init__(
        self,
        connection_string: str,
        pool_size: int = 10,
        table_prefix: Optional[str] = None,
        primary_key_field: str = "id",
    ):
        """
        Initialize PostgreSQL CRUD driver.

        Args:
            connection_string: PostgreSQL connection string
                (e.g., "postgresql://user:pass@localhost:5432/dbname")
            pool_size: Maximum number of connections in the pool
            table_prefix: Optional prefix for table names
            primary_key_field: Default primary key field name
        """
        super().__init__(connection_string, table_prefix)

        try:
            from psycopg_pool import ConnectionPool
        except ImportError:
            raise ImportError(
                "psycopg3 and psycopg_pool are required for PostgreSQL driver. "
                "Install with: pip install psycopg[pool]"
            )

        self.connection_string = connection_string
        self.pool_size = pool_size
        self.primary_key_field = primary_key_field

        # Create connection pool
        self.pool = ConnectionPool(
            conninfo=connection_string,
            min_size=1,
            max_size=pool_size,
        )

    def table_for(self, entity_class: Type, table_name: Optional[str] = None) -> CRUDTable:
        """
        Get or create a CRUDTable for the given entity class.

        Args:
            entity_class: Entity class to create table for
            table_name: Optional override for table name

        Returns:
            PostgreSQLCRUDTable instance
        """
        # Derive table name
        if table_name is None:
            table_name = self._default_table_name(entity_class)

        # Apply table prefix if set
        if self.table_prefix:
            table_name = f"{self.table_prefix}{table_name}"

        # Check cache
        if table_name in self._tables:
            return self._tables[table_name]

        # Create new table instance
        table = PostgreSQLCRUDTable(entity_class, self, table_name, self.primary_key_field)

        self._tables[table_name] = table
        return table

    def _default_table_name(self, entity_class: Type) -> str:
        """Generate default table name from entity class"""
        name = entity_class.__name__

        # Convert PascalCase to snake_case
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())

        return "".join(result)

    def begin_transaction(self) -> Any:
        """Begin a transaction, return a connection object"""
        conn = self.pool.getconn()
        return conn

    def commit_transaction(self, raw_tx: Any) -> None:
        """Commit the given transaction"""
        if raw_tx:
            raw_tx.commit()
            self.pool.putconn(raw_tx)

    def rollback_transaction(self, raw_tx: Any) -> None:
        """Rollback the given transaction"""
        if raw_tx:
            raw_tx.rollback()
            self.pool.putconn(raw_tx)

    def close(self) -> None:
        """Close the connection pool"""
        if hasattr(self, "pool"):
            self.pool.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close pool"""
        self.close()
