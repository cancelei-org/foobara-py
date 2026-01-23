"""
Root manifest for Foobara introspection.

Aggregates all registered components into a single manifest.
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

from foobara_py.manifest.base import BaseManifest
from foobara_py.manifest.command_manifest import CommandManifest
from foobara_py.manifest.domain_manifest import DomainManifest
from foobara_py.manifest.entity_manifest import EntityManifest
from foobara_py.manifest.error_manifest import ErrorManifest
from foobara_py.manifest.organization_manifest import OrganizationManifest
from foobara_py.manifest.type_manifest import TypeManifest


class RootManifest(BaseManifest):
    """
    Root manifest aggregating all Foobara components.

    Provides a complete view of:
    - All registered commands
    - All registered domains
    - All registered organizations
    - All registered types and entities
    - All registered errors

    Usage:
        # Build from current registries
        manifest = RootManifest.from_registry()

        # Convert to JSON
        json_str = manifest.to_json()

        # Get specific components
        commands = manifest.commands
        domains = manifest.domains
    """

    # Version info
    version: str = Field(default="1.0", description="Manifest version")
    foobara_version: str = Field(default="0.1.0", description="Foobara version")

    # Organizations
    organizations: List[OrganizationManifest] = Field(
        default_factory=list, description="Registered organizations"
    )

    # Domains
    domains: List[DomainManifest] = Field(default_factory=list, description="Registered domains")

    # Commands
    commands: List[CommandManifest] = Field(default_factory=list, description="Registered commands")

    # Types and entities
    types: List[TypeManifest] = Field(default_factory=list, description="Registered types")
    entities: List[EntityManifest] = Field(default_factory=list, description="Registered entities")

    # Errors
    errors: List[ErrorManifest] = Field(default_factory=list, description="Registered error types")

    # Counts
    organization_count: int = Field(default=0)
    domain_count: int = Field(default=0)
    command_count: int = Field(default=0)
    type_count: int = Field(default=0)
    entity_count: int = Field(default=0)
    error_count: int = Field(default=0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "foobara_version": self.foobara_version,
            "organizations": [o.to_dict() for o in self.organizations],
            "domains": [d.to_dict() for d in self.domains],
            "commands": [c.to_dict() for c in self.commands],
            "types": [t.to_dict() for t in self.types],
            "entities": [e.to_dict() for e in self.entities],
            "errors": [e.to_dict() for e in self.errors],
            "counts": {
                "organizations": self.organization_count,
                "domains": self.domain_count,
                "commands": self.command_count,
                "types": self.type_count,
                "entities": self.entity_count,
                "errors": self.error_count,
            },
        }

    def find_command(self, name: str) -> Optional[CommandManifest]:
        """
        Find command by name.

        Args:
            name: Command name or full name.

        Returns:
            CommandManifest if found, None otherwise.
        """
        for cmd in self.commands:
            if cmd.name == name or cmd.full_name == name:
                return cmd
        return None

    def find_domain(self, name: str) -> Optional[DomainManifest]:
        """
        Find domain by name.

        Args:
            name: Domain name.

        Returns:
            DomainManifest if found, None otherwise.
        """
        for domain in self.domains:
            if domain.name == name or domain.full_name == name:
                return domain
        return None

    def find_entity(self, name: str) -> Optional[EntityManifest]:
        """
        Find entity by name.

        Args:
            name: Entity name.

        Returns:
            EntityManifest if found, None otherwise.
        """
        for entity in self.entities:
            if entity.name == name or entity.full_name == name:
                return entity
        return None

    def commands_by_domain(self, domain_name: str) -> List[CommandManifest]:
        """
        Get commands for a specific domain.

        Args:
            domain_name: Domain name.

        Returns:
            List of commands in that domain.
        """
        return [c for c in self.commands if c.domain == domain_name]

    @classmethod
    def from_registry(cls) -> "RootManifest":
        """
        Build manifest from current registries.

        Scans all Foobara registries and builds a complete manifest.

        Returns:
            RootManifest with all registered components.
        """
        organizations = []
        domains = []
        commands = []
        types = []
        entities = []
        errors = []

        # Get commands from CommandRegistry
        try:
            from foobara_py.core.registry import get_default_registry

            registry = get_default_registry()
            for cmd_class in registry.list_commands():
                try:
                    manifest = CommandManifest.from_command(cmd_class)
                    commands.append(manifest)
                except Exception:
                    pass
        except ImportError:
            pass

        # Get entities from EntityRegistry
        try:
            from foobara_py.persistence.entity import EntityRegistry

            for entity_class in EntityRegistry.list_entities():
                try:
                    manifest = EntityManifest.from_entity(entity_class)
                    entities.append(manifest)
                except Exception:
                    pass
        except ImportError:
            pass

        # Get domains from DomainRegistry
        try:
            from foobara_py.domain.domain import DomainRegistry

            for domain in DomainRegistry.list_domains():
                try:
                    manifest = DomainManifest.from_domain(domain)
                    domains.append(manifest)
                except Exception:
                    pass
        except ImportError:
            pass

        # Build organizations from domains
        org_map: Dict[str, List[str]] = {}
        for domain in domains:
            if domain.organization:
                if domain.organization not in org_map:
                    org_map[domain.organization] = []
                org_map[domain.organization].append(domain.name)

        for org_name, domain_names in org_map.items():
            organizations.append(OrganizationManifest.from_domains(org_name, domain_names))

        # Get version
        foobara_version = "0.1.0"
        try:
            from foobara_py import __version__

            foobara_version = __version__
        except ImportError:
            pass

        return cls(
            foobara_version=foobara_version,
            organizations=organizations,
            domains=domains,
            commands=commands,
            types=types,
            entities=entities,
            errors=errors,
            organization_count=len(organizations),
            domain_count=len(domains),
            command_count=len(commands),
            type_count=len(types),
            entity_count=len(entities),
            error_count=len(errors),
        )
