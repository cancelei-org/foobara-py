"""
Utilities for mapping Entities to database tables.
"""

import datetime
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, Union, get_args, get_origin, get_type_hints

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from foobara_py.persistence.entity import EntityBase

TYPE_MAP = {
    int: Integer,
    str: String,
    bool: Boolean,
    float: Float,
    datetime.datetime: DateTime,
    datetime.date: DateTime,  # Or Date
    uuid.UUID: PG_UUID(as_uuid=True),
    Decimal: Numeric,
    dict: JSON,
    list: JSON,
}


def map_type_to_column_type(py_type: Any) -> Any:
    """Map a Python type to a SQLAlchemy column type"""
    # Handle Optional[T] and Union
    origin = get_origin(py_type)
    if origin is Union:
        args = get_args(py_type)
        if type(None) in args:
            # It's an Optional, get the non-None type
            py_type = next(t for t in args if t is not type(None))
        else:
            # Non-optional Union, default to JSON or first type
            py_type = args[0]

    # If it's still a complex type (like List[int]), get the origin
    origin = get_origin(py_type)
    if origin:
        py_type = origin

    # Handle basic types
    try:
        if py_type in TYPE_MAP:
            return TYPE_MAP[py_type]
    except TypeError:
        # If py_type is not hashable, it might be a ForwardRef or something else
        pass

    # Default to String/JSON for unknown types
    return JSON if py_type in (dict, list) else String


def entity_to_sqlalchemy_table(
    entity_class: Type[EntityBase], metadata: MetaData, table_name: Optional[str] = None
) -> Table:
    """
    Generate a SQLAlchemy Table definition from an Entity class.
    """
    if not table_name:
        table_name = entity_class.__name__.lower()

    columns = []
    pk_field = entity_class._primary_key_field

    # Use get_type_hints to resolve any ForwardRefs
    type_hints = get_type_hints(entity_class)

    for field_name, field_info in entity_class.model_fields.items():
        py_type = type_hints.get(field_name, field_info.annotation)
        sa_type = map_type_to_column_type(py_type)

        is_pk = field_name == pk_field
        nullable = not field_info.is_required()

        columns.append(Column(field_name, sa_type, primary_key=is_pk, nullable=nullable))

    return Table(table_name, metadata, *columns)
