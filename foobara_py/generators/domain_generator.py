"""
Domain generator for Foobara Python.

Generates new Foobara domains with standard directory structure.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from foobara_py.generators.files_generator import FilesGenerator


class DomainGenerator(FilesGenerator):
    """
    Generator for Foobara domains.

    Creates a domain package with:
    - __init__.py with domain definition
    - commands/ directory for command classes
    - types/ directory for type definitions
    - entities/ directory for entity classes

    Usage:
        generator = DomainGenerator(
            name="Users",
            organization="MyApp",
            dependencies=["Auth", "Notifications"],
            description="User management domain"
        )

        files = generator.generate(output_dir=Path("myapp/domains"))

    This creates:
        myapp/domains/users/
        ├── __init__.py          # Domain definition
        ├── commands/
        │   └── __init__.py
        ├── types/
        │   └── __init__.py
        └── entities/
            └── __init__.py
    """

    def __init__(
        self,
        name: str,
        organization: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        description: Optional[str] = None,
        generate_commands_dir: bool = True,
        generate_types_dir: bool = True,
        generate_entities_dir: bool = True,
    ):
        """
        Initialize domain generator.

        Args:
            name: Domain name (e.g., "Users", "Products", "Analytics")
            organization: Optional organization name for namespacing
            dependencies: List of domain names this domain depends on
            description: Domain description for docstring
            generate_commands_dir: Whether to generate commands/ directory
            generate_types_dir: Whether to generate types/ directory
            generate_entities_dir: Whether to generate entities/ directory
        """
        super().__init__()

        self.name = name
        self.organization = organization
        self.dependencies = dependencies or []
        self.description = description
        self.generate_commands_dir = generate_commands_dir
        self.generate_types_dir = generate_types_dir
        self.generate_entities_dir = generate_entities_dir

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate domain package files.

        Args:
            output_dir: Base directory to generate domain in
            **kwargs: Additional options

        Returns:
            List of generated file paths
        """
        files = []

        # Prepare context
        context = self._build_context()

        # Domain base directory
        domain_dir = output_dir / self._to_snake_case(self.name)

        # Generate domain __init__.py
        init_file = self._generate_init_file(domain_dir, context)
        files.append(init_file)

        # Generate subdirectories
        if self.generate_commands_dir:
            cmd_init = self._generate_subdir_init(domain_dir / "commands", "commands", context)
            files.append(cmd_init)

        if self.generate_types_dir:
            types_init = self._generate_subdir_init(domain_dir / "types", "types", context)
            files.append(types_init)

        if self.generate_entities_dir:
            entities_init = self._generate_subdir_init(domain_dir / "entities", "entities", context)
            files.append(entities_init)

        return files

    def _build_context(self) -> Dict[str, Any]:
        """Build template context from generator configuration."""
        return {
            "domain_name": self.name,
            "organization_name": self.organization,
            "dependencies": self.dependencies,
            "has_dependencies": len(self.dependencies) > 0,
            "description": self.description,
        }

    def _generate_init_file(self, domain_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate the domain __init__.py file."""
        output_path = domain_dir / "__init__.py"

        return self.create_from_template(
            template_name="domain_init.py.j2",
            output_path=output_path,
            context=context,
        )

    def _generate_subdir_init(
        self, subdir: Path, subdir_type: str, context: Dict[str, Any]
    ) -> Path:
        """Generate __init__.py for a subdirectory."""
        output_path = subdir / "__init__.py"

        subdir_context = context.copy()
        subdir_context["subdir_type"] = subdir_type

        return self.create_from_template(
            template_name="domain_subdir_init.py.j2",
            output_path=output_path,
            context=subdir_context,
        )


def generate_domain(
    name: str,
    output_dir: Path,
    organization: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
    description: Optional[str] = None,
    generate_commands_dir: bool = True,
    generate_types_dir: bool = True,
    generate_entities_dir: bool = True,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate a domain.

    Args:
        name: Domain name
        output_dir: Output directory
        organization: Optional organization name
        dependencies: Domain dependencies
        description: Domain description
        generate_commands_dir: Generate commands/ directory
        generate_types_dir: Generate types/ directory
        generate_entities_dir: Generate entities/ directory
        **kwargs: Additional options

    Returns:
        List of generated file paths

    Example:
        files = generate_domain(
            name="Users",
            output_dir=Path("myapp/domains"),
            organization="MyApp",
            dependencies=["Auth"],
            description="User management domain"
        )
    """
    generator = DomainGenerator(
        name=name,
        organization=organization,
        dependencies=dependencies,
        description=description,
        generate_commands_dir=generate_commands_dir,
        generate_types_dir=generate_types_dir,
        generate_entities_dir=generate_entities_dir,
    )

    return generator.generate(output_dir, **kwargs)
