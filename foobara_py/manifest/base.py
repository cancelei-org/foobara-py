"""
Base manifest class for Foobara introspection.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class BaseManifest(BaseModel, ABC):
    """
    Base class for all manifest types.

    Manifests provide JSON-serializable representations of Foobara components
    for introspection and discovery.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert manifest to dictionary representation.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        pass

    def to_json(self, indent: Optional[int] = 2) -> str:
        """
        Convert manifest to JSON string.

        Args:
            indent: JSON indentation level (None for compact).

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_json_schema(self) -> Dict[str, Any]:
        """
        Generate JSON Schema for this manifest type.

        Returns:
            JSON Schema dictionary.
        """
        return self.model_json_schema()

    def domain_reference(self) -> Optional[str]:
        """
        Get the domain reference for this manifest.

        Returns domain identifier string (e.g., "Organization::Domain").
        Added in v0.5.1 for compatibility with Ruby foobara (commit 0c0b3377).

        Returns:
            Domain reference string or None if not applicable.
        """
        # Default implementation - subclasses can override
        return None
