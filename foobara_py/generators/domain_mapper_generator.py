"""
Domain Mapper generator for Foobara Python.

Generates domain mapper classes that transform data between types across domains.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from foobara_py.generators.files_generator import FilesGenerator


class DomainMapperGenerator(FilesGenerator):
    """
    Generator for Foobara domain mapper classes.

    Creates domain mappers that transform data between different domain types,
    enabling cross-domain communication with automatic type transformations.

    Usage:
        generator = DomainMapperGenerator(
            name="UserInternalToExternal",
            from_type="UserInternal",
            to_type="UserExternal",
            domain="Users",
            organization="MyApp"
        )

        files = generator.generate(output_dir=Path("myapp/mappers"))
    """

    def __init__(
        self,
        name: str,
        from_type: str,
        to_type: str,
        domain: Optional[str] = None,
        organization: Optional[str] = None,
        description: Optional[str] = None,
        from_type_import: Optional[str] = None,
        to_type_import: Optional[str] = None,
        is_simple_conversion: bool = False,
        mapping_expression: Optional[str] = None,
    ):
        """
        Initialize domain mapper generator.

        Args:
            name: Mapper class name (e.g., "UserInternalToExternal")
            from_type: Source type name (e.g., "UserInternal")
            to_type: Destination type name (e.g., "UserExternal")
            domain: Optional domain name
            organization: Optional organization name
            description: Mapper description for docstring
            from_type_import: Import statement for from_type (e.g., "from myapp.models import UserInternal")
            to_type_import: Import statement for to_type
            is_simple_conversion: Whether this is a simple type conversion (e.g., int to str)
            mapping_expression: Expression for simple conversions (e.g., "str(self.from_value)")
        """
        super().__init__()

        self.name = name
        self.from_type = from_type
        self.to_type = to_type
        self.domain = domain
        self.organization = organization
        self.description = description
        self.from_type_import = from_type_import
        self.to_type_import = to_type_import
        self.is_simple_conversion = is_simple_conversion
        self.mapping_expression = mapping_expression or "self.from_value"

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate domain mapper file.

        Args:
            output_dir: Directory to generate files in
            **kwargs: Additional options

        Returns:
            List of generated file paths
        """
        context = self._build_context()
        mapper_file = self._generate_mapper_file(output_dir, context)
        return [mapper_file]

    def _build_context(self) -> Dict[str, Any]:
        """Build template context from generator configuration."""
        return {
            "mapper_name": self.name,
            "from_type": self.from_type,
            "to_type": self.to_type,
            "domain_name": self.domain,
            "organization_name": self.organization,
            "description": self.description,
            "from_type_import": self.from_type_import,
            "to_type_import": self.to_type_import,
            "is_simple_conversion": self.is_simple_conversion,
            "mapping_expression": self.mapping_expression,
        }

    def _generate_mapper_file(self, output_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate the domain mapper class file."""
        filename = f"{self._to_snake_case(self.name)}.py"
        output_path = output_dir / filename

        return self.create_from_template(
            template_name="domain_mapper.py.j2",
            output_path=output_path,
            context=context,
        )


def generate_domain_mapper(
    name: str,
    from_type: str,
    to_type: str,
    output_dir: Path,
    domain: Optional[str] = None,
    organization: Optional[str] = None,
    description: Optional[str] = None,
    from_type_import: Optional[str] = None,
    to_type_import: Optional[str] = None,
    is_simple_conversion: bool = False,
    mapping_expression: Optional[str] = None,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate a domain mapper.

    Args:
        name: Mapper class name
        from_type: Source type name
        to_type: Destination type name
        output_dir: Output directory
        domain: Optional domain name
        organization: Optional organization name
        description: Mapper description
        from_type_import: Import statement for from_type
        to_type_import: Import statement for to_type
        is_simple_conversion: Whether this is a simple type conversion
        mapping_expression: Expression for simple conversions
        **kwargs: Additional options

    Returns:
        List of generated file paths

    Example:
        files = generate_domain_mapper(
            name="UserInternalToExternal",
            from_type="UserInternal",
            to_type="UserExternal",
            output_dir=Path("myapp/mappers"),
            domain="Users",
        )
    """
    generator = DomainMapperGenerator(
        name=name,
        from_type=from_type,
        to_type=to_type,
        domain=domain,
        organization=organization,
        description=description,
        from_type_import=from_type_import,
        to_type_import=to_type_import,
        is_simple_conversion=is_simple_conversion,
        mapping_expression=mapping_expression,
    )

    return generator.generate(output_dir, **kwargs)
