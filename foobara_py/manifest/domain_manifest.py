"""
Domain manifest for Foobara introspection.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import Field

from foobara_py.manifest.base import BaseManifest

if TYPE_CHECKING:
    from foobara_py.domain.domain import Domain
    from foobara_py.manifest.command_manifest import CommandManifest
    from foobara_py.manifest.entity_manifest import EntityManifest
    from foobara_py.manifest.type_manifest import TypeManifest


class DomainManifest(BaseManifest):
    """
    Manifest for a Foobara domain.

    Captures all metadata about a domain including:
    - Name and organization
    - Registered commands
    - Registered types and entities
    - Dependencies
    """

    name: str = Field(description="Domain name")
    full_name: str = Field(description="Full name (Organization::Domain)")
    description: Optional[str] = Field(default=None, description="Domain description")

    organization: Optional[str] = Field(default=None, description="Organization name")
    dependencies: List[str] = Field(default_factory=list, description="Domain dependencies")

    # Counts (full manifests in RootManifest)
    command_count: int = Field(default=0, description="Number of commands")
    type_count: int = Field(default=0, description="Number of types")
    entity_count: int = Field(default=0, description="Number of entities")

    # Command names for reference
    command_names: List[str] = Field(
        default_factory=list, description="Names of commands in this domain"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "full_name": self.full_name,
            "description": self.description,
            "organization": self.organization,
            "dependencies": self.dependencies,
            "command_count": self.command_count,
            "type_count": self.type_count,
            "entity_count": self.entity_count,
            "command_names": self.command_names,
        }

    @classmethod
    def from_domain(cls, domain: "Domain") -> "DomainManifest":
        """
        Create manifest from a domain instance.

        Args:
            domain: The domain to create manifest for.

        Returns:
            DomainManifest instance.
        """
        # Build full name
        parts = []
        if domain.organization:
            parts.append(domain.organization)
        parts.append(domain.name)
        full_name = "::".join(parts)

        # Get command names
        command_names = list(domain._commands.keys()) if hasattr(domain, "_commands") else []

        # Count types and entities
        type_count = 0
        entity_count = 0
        if hasattr(domain, "_types"):
            for type_class in domain._types.values():
                # Check if it's an Entity (imports handled carefully to avoid circular imports)
                try:
                    from foobara_py.persistence.entity import EntityBase

                    if isinstance(type_class, type) and issubclass(type_class, EntityBase):
                        entity_count += 1
                    else:
                        type_count += 1
                except ImportError:
                    # If Entity is not available, count as type
                    type_count += 1

        return cls(
            name=domain.name,
            full_name=full_name,
            description=getattr(domain, "description", None),
            organization=domain.organization,
            dependencies=domain.dependencies if hasattr(domain, "dependencies") else [],
            command_count=len(command_names),
            type_count=type_count,
            entity_count=entity_count,
            command_names=command_names,
        )
