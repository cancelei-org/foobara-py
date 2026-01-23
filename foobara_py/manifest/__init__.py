"""
Foobara Manifest System.

Provides introspection and discovery for commands, domains, types, and entities.

The manifest system generates JSON-compatible representations of all registered
Foobara components, suitable for:
- API documentation generation
- MCP tool discovery
- Remote command imports
- IDE integration
"""

from foobara_py.manifest.base import BaseManifest
from foobara_py.manifest.command_manifest import CommandManifest
from foobara_py.manifest.domain_manifest import DomainManifest
from foobara_py.manifest.entity_manifest import EntityManifest
from foobara_py.manifest.error_manifest import ErrorManifest
from foobara_py.manifest.organization_manifest import OrganizationManifest
from foobara_py.manifest.root_manifest import RootManifest
from foobara_py.manifest.type_manifest import TypeManifest

__all__ = [
    "BaseManifest",
    "CommandManifest",
    "DomainManifest",
    "OrganizationManifest",
    "TypeManifest",
    "EntityManifest",
    "ErrorManifest",
    "RootManifest",
]
