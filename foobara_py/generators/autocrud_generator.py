"""
AutoCRUD generator for Foobara Python.

Generates CRUD (Create, Read, Update, Delete, List) commands for entities.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set

from foobara_py.generators.files_generator import FilesGenerator

CRUDOperation = Literal["create", "read", "update", "delete", "list"]

ALL_OPERATIONS: Set[CRUDOperation] = {"create", "read", "update", "delete", "list"}


class AutoCRUDGenerator(FilesGenerator):
    """
    Generator for CRUD commands for Foobara entities.

    Creates commands for:
    - Create: Create a new entity
    - Read: Find entity by primary key
    - Update: Update existing entity
    - Delete: Delete entity by primary key
    - List: List all entities (with optional filtering)

    Usage:
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
            ],
            primary_key="id",
            operations=["create", "read", "update", "delete", "list"]
        )

        files = generator.generate(output_dir=Path("myapp/commands"))
    """

    def __init__(
        self,
        entity_name: str,
        entity_module: str,
        fields: List[Dict[str, Any]],
        primary_key: str = "id",
        operations: Optional[List[CRUDOperation]] = None,
        domain: Optional[str] = None,
        organization: Optional[str] = None,
        generate_tests: bool = True,
    ):
        """
        Initialize AutoCRUD generator.

        Args:
            entity_name: Entity class name (e.g., "User", "Product")
            entity_module: Full module path to entity (e.g., "myapp.entities.user")
            fields: List of entity fields [{"name": "id", "type": "int", "description": "..."}]
            primary_key: Primary key field name (default: "id")
            operations: List of operations to generate (default: all)
            domain: Optional domain name for command registration
            organization: Optional organization name
            generate_tests: Whether to generate test files
        """
        super().__init__()

        self.entity_name = entity_name
        self.entity_module = entity_module
        self.fields = fields
        self.primary_key = primary_key
        self.operations = set(operations) if operations else ALL_OPERATIONS
        self.domain = domain
        self.organization = organization
        self.generate_tests = generate_tests

        # Separate fields for different operations
        self._pk_field = next(
            (f for f in fields if f["name"] == primary_key), {"name": primary_key, "type": "int"}
        )
        self._non_pk_fields = [f for f in fields if f["name"] != primary_key]

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate CRUD command files.

        Args:
            output_dir: Directory to generate files in
            **kwargs: Additional options (test_dir)

        Returns:
            List of generated file paths
        """
        files = []

        # Build base context
        base_context = self._build_base_context()

        # Generate each operation
        for operation in self.operations:
            context = self._build_operation_context(operation, base_context)
            template_name = f"crud_{operation}.py.j2"

            # Generate command file
            cmd_file = self._generate_command_file(output_dir, operation, template_name, context)
            files.append(cmd_file)

            # Generate test file
            if self.generate_tests:
                test_dir = kwargs.get("test_dir", output_dir.parent / "tests")
                test_file = self._generate_test_file(test_dir, operation, context)
                files.append(test_file)

        return files

    def _build_base_context(self) -> Dict[str, Any]:
        """Build base template context."""
        return {
            "entity_name": self.entity_name,
            "entity_module": self.entity_module,
            "fields": self.fields,
            "non_pk_fields": self._non_pk_fields,
            "primary_key": self.primary_key,
            "pk_field": self._pk_field,
            "domain_name": self.domain,
            "organization_name": self.organization,
        }

    def _build_operation_context(
        self, operation: CRUDOperation, base_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build context for specific operation."""
        context = base_context.copy()

        # Command naming
        command_names = {
            "create": f"Create{self.entity_name}",
            "read": f"Get{self.entity_name}",
            "update": f"Update{self.entity_name}",
            "delete": f"Delete{self.entity_name}",
            "list": f"List{self.entity_name}s",
        }

        context["operation"] = operation
        context["command_name"] = command_names[operation]

        return context

    def _generate_command_file(
        self,
        output_dir: Path,
        operation: CRUDOperation,
        template_name: str,
        context: Dict[str, Any],
    ) -> Path:
        """Generate a CRUD command file."""
        filename = f"{self._to_snake_case(context['command_name'])}.py"
        output_path = output_dir / filename

        return self.create_from_template(
            template_name=template_name,
            output_path=output_path,
            context=context,
        )

    def _generate_test_file(
        self, test_dir: Path, operation: CRUDOperation, context: Dict[str, Any]
    ) -> Path:
        """Generate test file for a CRUD command."""
        filename = f"test_{self._to_snake_case(context['command_name'])}.py"
        output_path = test_dir / filename

        return self.create_from_template(
            template_name="crud_test.py.j2",
            output_path=output_path,
            context=context,
        )


def generate_crud(
    entity_name: str,
    entity_module: str,
    fields: List[Dict[str, Any]],
    output_dir: Path,
    primary_key: str = "id",
    operations: Optional[List[CRUDOperation]] = None,
    domain: Optional[str] = None,
    organization: Optional[str] = None,
    generate_tests: bool = True,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate CRUD commands for an entity.

    Args:
        entity_name: Entity class name
        entity_module: Full module path to entity
        fields: Entity field definitions
        output_dir: Output directory for commands
        primary_key: Primary key field name
        operations: Operations to generate (default: all)
        domain: Optional domain name
        organization: Optional organization name
        generate_tests: Whether to generate tests
        **kwargs: Additional options (test_dir)

    Returns:
        List of generated file paths

    Example:
        files = generate_crud(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
            ],
            output_dir=Path("myapp/commands"),
            primary_key="id",
            operations=["create", "read", "update", "delete"],
            domain="Users"
        )
    """
    generator = AutoCRUDGenerator(
        entity_name=entity_name,
        entity_module=entity_module,
        fields=fields,
        primary_key=primary_key,
        operations=operations,
        domain=domain,
        organization=organization,
        generate_tests=generate_tests,
    )

    return generator.generate(output_dir, **kwargs)
