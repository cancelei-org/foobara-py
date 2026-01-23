"""
Organization generator for Foobara Python.

Generates new Foobara organizations with multiple domains.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from foobara_py.generators.domain_generator import DomainGenerator
from foobara_py.generators.files_generator import FilesGenerator


class OrganizationGenerator(FilesGenerator):
    """
    Generator for Foobara organizations.

    Creates an organization package structure with:
    - __init__.py with organization metadata
    - Multiple domain packages
    - Standard directory layout

    Usage:
        generator = OrganizationGenerator(
            name="MyApp",
            domains=["Users", "Products", "Orders"],
            description="E-commerce application"
        )

        files = generator.generate(output_dir=Path("myapp"))

    This creates:
        myapp/
        ├── __init__.py          # Organization definition
        ├── users/
        │   ├── __init__.py      # Domain definition
        │   ├── commands/
        │   │   └── __init__.py
        │   ├── types/
        │   │   └── __init__.py
        │   └── entities/
        │       └── __init__.py
        ├── products/
        │   └── ...
        └── orders/
            └── ...
    """

    def __init__(
        self,
        name: str,
        domains: Optional[List[str]] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
        generate_domains: bool = True,
    ):
        """
        Initialize organization generator.

        Args:
            name: Organization name (e.g., "MyApp", "Acme")
            domains: List of domain names to create (e.g., ["Users", "Products"])
            description: Organization description for docstring
            version: Organization version (default: "0.1.0")
            generate_domains: Whether to generate domain packages
        """
        super().__init__()

        self.name = name
        self.domains = domains or []
        self.description = description
        self.version = version or "0.1.0"
        self.generate_domains = generate_domains

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate organization package files.

        Args:
            output_dir: Base directory to generate organization in
            **kwargs: Additional options (domain_dependencies)

        Returns:
            List of generated file paths
        """
        files = []

        # Prepare context
        context = self._build_context()

        # Organization base directory
        org_dir = output_dir / self._to_snake_case(self.name)

        # Generate organization __init__.py
        init_file = self._generate_init_file(org_dir, context)
        files.append(init_file)

        # Generate domains
        if self.generate_domains and self.domains:
            domain_dependencies = kwargs.get("domain_dependencies", {})

            for domain_name in self.domains:
                domain_files = self._generate_domain(
                    org_dir, domain_name, domain_dependencies.get(domain_name, [])
                )
                files.extend(domain_files)

        return files

    def _build_context(self) -> Dict[str, Any]:
        """Build template context from generator configuration."""
        return {
            "organization_name": self.name,
            "domains": self.domains,
            "description": self.description,
            "version": self.version,
        }

    def _generate_init_file(self, org_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate the organization __init__.py file."""
        output_path = org_dir / "__init__.py"

        return self.create_from_template(
            template_name="organization_init.py.j2",
            output_path=output_path,
            context=context,
        )

    def _generate_domain(
        self, org_dir: Path, domain_name: str, dependencies: List[str]
    ) -> List[Path]:
        """
        Generate a domain package within the organization.

        Args:
            org_dir: Organization directory
            domain_name: Name of the domain to generate
            dependencies: List of domain dependencies

        Returns:
            List of generated file paths
        """
        domain_generator = DomainGenerator(
            name=domain_name,
            organization=self.name,
            dependencies=dependencies,
            description=f"{domain_name} domain",
        )

        return domain_generator.generate(org_dir)


def generate_organization(
    name: str,
    output_dir: Path,
    domains: Optional[List[str]] = None,
    description: Optional[str] = None,
    version: Optional[str] = None,
    generate_domains: bool = True,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate an organization.

    Args:
        name: Organization name
        output_dir: Output directory
        domains: List of domain names to create
        description: Organization description
        version: Organization version
        generate_domains: Whether to generate domain packages
        **kwargs: Additional options (domain_dependencies)

    Returns:
        List of generated file paths

    Example:
        files = generate_organization(
            name="MyApp",
            output_dir=Path("."),
            domains=["Users", "Products", "Orders"],
            description="E-commerce application",
            domain_dependencies={
                "Orders": ["Users", "Products"],
            }
        )
    """
    generator = OrganizationGenerator(
        name=name,
        domains=domains,
        description=description,
        version=version,
        generate_domains=generate_domains,
    )

    return generator.generate(output_dir, **kwargs)
