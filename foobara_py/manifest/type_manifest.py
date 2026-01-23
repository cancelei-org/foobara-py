"""
Type manifest for Foobara introspection.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from pydantic import BaseModel, Field

from foobara_py.manifest.base import BaseManifest


class TypeManifest(BaseManifest):
    """
    Manifest for a Foobara type.

    Types include Pydantic models, custom types, and value objects.
    """

    name: str = Field(description="Type name")
    full_name: str = Field(description="Full qualified name")
    description: Optional[str] = Field(default=None, description="Type description")

    # Type details
    kind: str = Field(default="type", description="Type kind (type, model, entity)")
    json_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema for the type"
    )

    # Metadata
    domain: Optional[str] = Field(default=None, description="Domain name")
    organization: Optional[str] = Field(default=None, description="Organization name")
    is_mutable: bool = Field(default=False, description="Whether type is mutable")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "full_name": self.full_name,
            "description": self.description,
            "kind": self.kind,
            "json_schema": self.json_schema,
            "domain": self.domain,
            "organization": self.organization,
            "is_mutable": self.is_mutable,
        }

    @classmethod
    def from_model(cls, model_class: Type[BaseModel]) -> "TypeManifest":
        """
        Create manifest from a Pydantic model class.

        Args:
            model_class: The model class to create manifest for.

        Returns:
            TypeManifest instance.
        """
        import inspect

        name = model_class.__name__
        description = inspect.getdoc(model_class)

        # Get JSON schema
        json_schema = None
        try:
            json_schema = model_class.model_json_schema()
        except Exception:
            pass

        # Determine kind
        kind = "model"
        if hasattr(model_class, "_primary_key_field"):
            kind = "entity"

        # Check mutability
        is_mutable = True
        if hasattr(model_class, "model_config"):
            config = model_class.model_config
            if isinstance(config, dict):
                is_mutable = not config.get("frozen", False)

        return cls(
            name=name,
            full_name=name,  # TODO: add domain/org prefix
            description=description,
            kind=kind,
            json_schema=json_schema,
            is_mutable=is_mutable,
        )
