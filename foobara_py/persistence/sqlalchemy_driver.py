"""
SQLAlchemy implementation of CRUDDriver for foobara-py.
"""

from typing import Any, Dict, Iterable, List, Optional, Type, Union

from sqlalchemy import (
    Column,
    Connection,
    Engine,
    MetaData,
    Table,
    create_engine,
    delete,
    func,
    insert,
    inspect,
    select,
    update,
)
from sqlalchemy.schema import CreateTable

from foobara_py.persistence.crud_driver import (
    CannotDeleteError,
    CannotFindError,
    CannotInsertError,
    CannotUpdateError,
    CRUDDriver,
    CRUDTable,
)
from foobara_py.persistence.mapping import entity_to_sqlalchemy_table


class SQLAlchemyTable(CRUDTable):
    """
    CRUDTable implementation using SQLAlchemy.
    """

    def __init__(
        self,
        entity_class: Type,
        driver: "SQLAlchemyDriver",
        table_name: Optional[str] = None,
        sa_table: Optional[Table] = None,
    ):
        super().__init__(entity_class, driver, table_name)
        self.sa_table = sa_table or self._reflect_or_create_table()

    def _reflect_or_create_table(self) -> Table:
        """Reflect existing table or create a new one based on entity fields"""
        metadata = self.driver.metadata
        if self.table_name in metadata.tables:
            return metadata.tables[self.table_name]

        # Basic reflection
        with self.driver.engine.connect() as conn:
            if inspect(self.driver.engine).has_table(self.table_name):
                metadata.reflect(only=[self.table_name])
                return metadata.tables[self.table_name]

        # If not found, use mapping utility to define it
        return entity_to_sqlalchemy_table(self.entity_class, metadata, self.table_name)

    def find(self, record_id: Any) -> Optional[Dict[str, Any]]:
        pk_col = self.sa_table.primary_key.columns[0]
        stmt = select(self.sa_table).where(pk_col == record_id)
        with self.driver.engine.connect() as conn:
            result = conn.execute(stmt).mappings().first()
            return dict(result) if result else None

    def all(self, page_size: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        stmt = select(self.sa_table)
        if page_size:
            stmt = stmt.limit(page_size)

        with self.driver.engine.connect() as conn:
            results = conn.execute(stmt).mappings().all()
            return [dict(r) for r in results]

    def insert(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        stmt = insert(self.sa_table).values(**attributes).returning(self.sa_table)
        with self.driver.engine.connect() as conn:
            result = conn.execute(stmt).mappings().first()
            conn.commit()
            if not result:
                raise CannotInsertError(None, "Insert failed")
            return dict(result)

    def update(self, record_id: Any, attributes: Dict[str, Any]) -> Dict[str, Any]:
        pk_col = self.sa_table.primary_key.columns[0]
        stmt = (
            update(self.sa_table)
            .where(pk_col == record_id)
            .values(**attributes)
            .returning(self.sa_table)
        )
        with self.driver.engine.connect() as conn:
            result = conn.execute(stmt).mappings().first()
            conn.commit()
            if not result:
                raise CannotUpdateError(record_id, "Update failed or record not found")
            return dict(result)

    def delete(self, record_id: Any) -> bool:
        pk_col = self.sa_table.primary_key.columns[0]
        stmt = delete(self.sa_table).where(pk_col == record_id)
        with self.driver.engine.connect() as conn:
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount > 0

    def count(self) -> int:
        stmt = select(func.count()).select_from(self.sa_table)
        with self.driver.engine.connect() as conn:
            return conn.execute(stmt).scalar() or 0

    def select(
        self,
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        stmt = select(self.sa_table)

        if where:
            for field, value in where.items():
                col = self.sa_table.c[field]
                stmt = stmt.where(col == value)

        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]
            for field in order_by:
                # Handle "-field" for descending
                if field.startswith("-"):
                    stmt = stmt.order_by(self.sa_table.c[field[1:]].desc())
                else:
                    stmt = stmt.order_by(self.sa_table.c[field].asc())

        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)

        with self.driver.engine.connect() as conn:
            results = conn.execute(stmt).mappings().all()
            return [dict(r) for r in results]


class SQLAlchemyDriver(CRUDDriver):
    """
    CRUDDriver implementation using SQLAlchemy.
    """

    def __init__(
        self,
        connection_info: Union[str, Engine],
        table_prefix: Optional[str] = None,
        metadata: Optional[MetaData] = None,
    ):
        super().__init__(connection_info, table_prefix)
        if isinstance(connection_info, str):
            self.engine = create_engine(connection_info)
        else:
            self.engine = connection_info

        self.metadata = metadata or MetaData()

    def table_for(self, entity_class: Type) -> SQLAlchemyTable:
        entity_name = entity_class.__name__
        if entity_name not in self._tables:
            self._tables[entity_name] = SQLAlchemyTable(entity_class, self)
        return self._tables[entity_name]

    def begin_transaction(self) -> Connection:
        return self.engine.connect()

    def commit_transaction(self, raw_tx: Connection) -> None:
        raw_tx.commit()
        raw_tx.close()

    def rollback_transaction(self, raw_tx: Connection) -> None:
        raw_tx.rollback()
        raw_tx.close()
