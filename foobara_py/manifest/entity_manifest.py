"""
Entity manifest for Foobara introspection.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from pydantic import Field

from foobara_py.manifest.base import BaseManifest

if TYPE_CHECKING:
    from foobara_py.persistence.entity import EntityBase


class EntityManifest(BaseManifest):
    """
    Manifest for a Foobara entity.

    Entities are database-backed objects with primary keys.
    """

    name: str = Field(description="Entity name")
    full_name: str = Field(description="Full qualified name")
    description: Optional[str] = Field(default=None, description="Entity description")

    # Entity details
    primary_key_field: str = Field(description="Primary key field name")
    json_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema for the entity"
    )

    # Fields metadata
    fields: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Field definitions")

    # Associations
    associations: List[str] = Field(default_factory=list, description="Association names")

    # Metadata
    domain: Optional[str] = Field(default=None, description="Domain name")
    organization: Optional[str] = Field(default=None, description="Organization name")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "full_name": self.full_name,
            "description": self.description,
            "primary_key_field": self.primary_key_field,
            "json_schema": self.json_schema,
            "fields": self.fields,
            "associations": self.associations,
            "domain": self.domain,
            "organization": self.organization,
        }

    @classmethod
    def from_entity(cls, entity_class: Type["EntityBase"]) -> "EntityManifest":
        """
        Create manifest from an entity class.

        Args:
            entity_class: The entity class to create manifest for.

        Returns:
            EntityManifest instance.
        """
        import inspect

        name = entity_class.__name__
        description = inspect.getdoc(entity_class)

        # Get primary key field
        primary_key_field = getattr(entity_class, "_primary_key_field", "id")

        # Get JSON schema
        json_schema = None
        try:
            json_schema = entity_class.model_json_schema()
        except Exception:
            pass

        # Get field information
        fields = {}
        if hasattr(entity_class, "model_fields"):
            for field_name, field_info in entity_class.model_fields.items():
                fields[field_name] = {
                    "type": str(field_info.annotation),
                    "required": field_info.is_required(),
                    "is_primary_key": field_name == primary_key_field,
                }
                if field_info.default is not None:
                    fields[field_name]["default"] = str(field_info.default)

        # Get associations (if any)
        associations = []
        for attr_name in dir(entity_class):
            if not attr_name.startswith("_"):
                attr = getattr(entity_class, attr_name, None)
                if hasattr(attr, "_is_association") and attr._is_association:
                    associations.append(attr_name)

        return cls(
            name=name,
            full_name=name,  # TODO: add domain/org prefix
            description=description,
            primary_key_field=primary_key_field,
            json_schema=json_schema,
            fields=fields,
            associations=associations,
        )
