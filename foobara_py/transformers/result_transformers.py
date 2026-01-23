"""
Result transformers for post-processing command results.

These transformers run after command execution to format,
serialize, or enhance results before returning to the caller.
"""

from typing import Any

from foobara_py.transformers.base import Transformer


class LoadAggregatesTransformer(Transformer[Any]):
    """
    Load full entity aggregates with all associations.

    When a command result contains entities, this transformer
    ensures all associations are loaded (not just primary keys).

    Usage:
        transformer = LoadAggregatesTransformer("user", "user.posts")
        result = transformer.transform(result)
        # All specified entity paths are fully loaded
    """

    def __init__(self, *entity_paths: str):
        """
        Initialize with entity paths to load.

        Args:
            *entity_paths: Dot-separated paths to entities (e.g., "user", "user.posts")
        """
        self.entity_paths = list(entity_paths)

    def transform(self, value: Any) -> Any:
        """Load associations for specified entity paths"""
        # Note: This is a placeholder implementation
        # Full implementation would need repository access and path resolution

        if hasattr(value, "model_dump"):
            # Pydantic model - convert to dict first
            data = value.model_dump()
            return self._load_at_paths(data)
        elif isinstance(value, dict):
            return self._load_at_paths(value)
        elif isinstance(value, list):
            return [self.transform(item) for item in value]

        return value

    def _load_at_paths(self, data: dict) -> dict:
        """Load entities at specified paths in dict"""
        # Simplified implementation
        # In practice, this would:
        # 1. Parse entity_paths (e.g., "user.posts")
        # 2. Navigate to each path in data
        # 3. Check if value is entity/pk
        # 4. Load full entity with associations from repository

        return data


class LoadAtomsTransformer(Transformer[Any]):
    """
    Load atomic entities (no nested associations).

    Similar to LoadAggregatesTransformer but loads entities
    without their associations (atomic representation).

    Usage:
        transformer = LoadAtomsTransformer("user", "post")
        result = transformer.transform(result)
        # Entities loaded but associations remain as PKs
    """

    def __init__(self, *entity_paths: str):
        """
        Initialize with entity paths to load.

        Args:
            *entity_paths: Dot-separated paths to entities
        """
        self.entity_paths = list(entity_paths)

    def transform(self, value: Any) -> Any:
        """Load entities at specified paths without associations"""
        # Simplified placeholder
        return value


class ResultToJsonTransformer(Transformer[Any]):
    """
    Convert result to JSON-serializable format.

    Handles Pydantic models, entities, dates, and other non-JSON types.

    Usage:
        transformer = ResultToJsonTransformer()
        result = transformer.transform(my_result)
        # Result is now JSON-serializable
    """

    def __init__(self, use_serializer: bool = True):
        """
        Initialize transformer.

        Args:
            use_serializer: Whether to use registered serializers for entities
        """
        self.use_serializer = use_serializer

    def transform(self, value: Any) -> Any:
        """Convert to JSON-serializable format"""
        from datetime import date, datetime

        from pydantic import BaseModel

        # Handle None
        if value is None:
            return None

        # Handle Pydantic models
        if isinstance(value, BaseModel):
            return value.model_dump()

        # Handle entities (use serializer if available)
        if hasattr(value, "primary_key") and self.use_serializer:
            try:
                from foobara_py.serializers import SerializerRegistry

                return SerializerRegistry.serialize(value)
            except Exception:
                # Fall back to model_dump if available
                if hasattr(value, "model_dump"):
                    return value.model_dump()

        # Handle datetime/date
        if isinstance(value, (datetime, date)):
            return value.isoformat()

        # Handle dicts recursively
        if isinstance(value, dict):
            return {k: self.transform(v) for k, v in value.items()}

        # Handle lists recursively
        if isinstance(value, (list, tuple)):
            return [self.transform(item) for item in value]

        # Handle sets
        if isinstance(value, set):
            return [self.transform(item) for item in value]

        # Primitives pass through
        return value


class EntityToPrimaryKeyResultTransformer(Transformer[Any]):
    """
    Convert all entities in result to primary keys.

    Usage:
        transformer = EntityToPrimaryKeyResultTransformer()
        result = transformer.transform(result)
        # All entities replaced with their PKs
    """

    def transform(self, value: Any) -> Any:
        """Recursively convert entities to primary keys"""
        # Check if entity
        if hasattr(value, "primary_key"):
            return value.primary_key

        # Handle dicts
        if isinstance(value, dict):
            return {k: self.transform(v) for k, v in value.items()}

        # Handle lists
        if isinstance(value, (list, tuple)):
            return [self.transform(item) for item in value]

        # Primitives pass through
        return value


class PaginationTransformer(Transformer[list[Any]]):
    """
    Add pagination metadata to list results.

    Usage:
        transformer = PaginationTransformer(page=1, per_page=10, total=100)
        result = transformer.transform(items)
        # Returns: {"items": [...], "page": 1, "per_page": 10, "total": 100}
    """

    def __init__(self, page: int = 1, per_page: int = 20, total: int = None):
        """
        Initialize with pagination parameters.

        Args:
            page: Current page number (1-indexed)
            per_page: Items per page
            total: Total number of items (None to omit)
        """
        self.page = page
        self.per_page = per_page
        self.total = total

    def transform(self, value: list[Any]) -> dict[str, Any]:
        """Wrap list in pagination metadata"""
        if not isinstance(value, list):
            return value

        result = {
            "items": value,
            "page": self.page,
            "per_page": self.per_page,
        }

        if self.total is not None:
            result["total"] = self.total
            result["total_pages"] = (self.total + self.per_page - 1) // self.per_page

        return result


# Auto-register transformers
from foobara_py.transformers.base import TransformerRegistry

TransformerRegistry.register("load_aggregates", LoadAggregatesTransformer, "result")
TransformerRegistry.register("load_atoms", LoadAtomsTransformer, "result")
TransformerRegistry.register("to_json", ResultToJsonTransformer, "result")
TransformerRegistry.register("entity_to_pk_result", EntityToPrimaryKeyResultTransformer, "result")
TransformerRegistry.register("pagination", PaginationTransformer, "result")
