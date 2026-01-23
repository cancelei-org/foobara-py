"""
Organization manifest for Foobara introspection.
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

from foobara_py.manifest.base import BaseManifest


class OrganizationManifest(BaseManifest):
    """
    Manifest for a Foobara organization.

    Organizations are top-level namespaces that contain domains.
    """

    name: str = Field(description="Organization name")
    description: Optional[str] = Field(default=None, description="Organization description")

    # Domain references
    domain_names: List[str] = Field(
        default_factory=list, description="Names of domains in this organization"
    )
    domain_count: int = Field(default=0, description="Number of domains")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "domain_names": self.domain_names,
            "domain_count": self.domain_count,
        }

    @classmethod
    def from_domains(cls, name: str, domains: List[str]) -> "OrganizationManifest":
        """
        Create organization manifest from domain list.

        Args:
            name: Organization name.
            domains: List of domain names in this organization.

        Returns:
            OrganizationManifest instance.
        """
        return cls(
            name=name,
            domain_names=domains,
            domain_count=len(domains),
        )
