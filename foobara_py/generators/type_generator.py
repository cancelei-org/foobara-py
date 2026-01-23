"""
Type and Entity generator for Foobara Python.

Generates new types, models (value objects), and entities with tests.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from foobara_py.generators.files_generator import FilesGenerator

TypeKind = Literal["type", "model", "entity"]


class TypeGenerator(FilesGenerator):
    """
    Generator for Foobara types, models, and entities.

    Creates:
    - Type: Pydantic Annotated types with validators
    - Model: Immutable value objects (Model base class)
    - Entity: Database-backed entities (EntityBase)

    Usage:
        # Generate a simple type
        generator = TypeGenerator(
            name="EmailAddress",
            kind="type",
            base_type="str",
            validators=["strip_whitespace", "validate_email"]
        )

        # Generate a model (value object)
        generator = TypeGenerator(
            name="Address",
            kind="model",
            fields=[
                {"name": "street", "type": "str"},
                {"name": "city", "type": "str"},
                {"name": "postal_code", "type": "str"},
            ]
        )

        # Generate an entity
        generator = TypeGenerator(
            name="User",
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
            ],
            primary_key="id",
            domain="Users"
        )

        files = generator.generate(output_dir=Path("myapp/types"))
    """

    def __init__(
        self,
        name: str,
        kind: TypeKind = "model",
        fields: Optional[List[Dict[str, Any]]] = None,
        base_type: Optional[str] = None,
        validators: Optional[List[str]] = None,
        primary_key: str = "id",
        domain: Optional[str] = None,
        organization: Optional[str] = None,
        description: Optional[str] = None,
        mutable: bool = False,
        generate_tests: bool = True,
    ):
        """
        Initialize type generator.

        Args:
            name: Type/model/entity name (e.g., "User", "Address", "EmailAddress")
            kind: Type of object to generate: "type", "model", or "entity"
            fields: List of field definitions [{"name": "email", "type": "str", "default": None}]
            base_type: Base type for simple types (e.g., "str", "int")
            validators: List of validator names for simple types
            primary_key: Primary key field name for entities (default: "id")
            domain: Optional domain name for entity registration
            organization: Optional organization name
            description: Type/model/entity description for docstring
            mutable: For models, whether to use MutableModel instead of Model
            generate_tests: Whether to generate test file
        """
        super().__init__()

        self.name = name
        self.kind = kind
        self.fields = fields or []
        self.base_type = base_type
        self.validators = validators or []
        self.primary_key = primary_key
        self.domain = domain
        self.organization = organization
        self.description = description
        self.mutable = mutable
        self.generate_tests = generate_tests

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate type/model/entity files.

        Args:
            output_dir: Directory to generate files in
            **kwargs: Additional options (test_dir, module_path)

        Returns:
            List of generated file paths
        """
        files = []

        # Prepare context
        context = self._build_context()

        # Select template based on kind
        template_map = {
            "type": "type.py.j2",
            "model": "model.py.j2",
            "entity": "entity.py.j2",
        }
        template_name = template_map[self.kind]

        # Generate main file
        main_file = self._generate_main_file(output_dir, template_name, context)
        files.append(main_file)

        # Generate test file
        if self.generate_tests:
            test_dir = kwargs.get("test_dir", output_dir.parent.parent / "tests")
            test_file = self._generate_test_file(test_dir, context, kwargs.get("module_path"))
            files.append(test_file)

        return files

    def _build_context(self) -> Dict[str, Any]:
        """Build template context from generator configuration."""
        # Process fields to add computed properties
        processed_fields = []
        for field in self.fields:
            processed = dict(field)
            # Determine if field is optional
            processed["is_optional"] = (
                "Optional" in field.get("type", "") or field.get("default") is not None
            )
            processed_fields.append(processed)

        return {
            "type_name": self.name,
            "kind": self.kind,
            "fields": processed_fields,
            "has_fields": len(self.fields) > 0,
            "base_type": self.base_type,
            "validators": self.validators,
            "has_validators": len(self.validators) > 0,
            "primary_key": self.primary_key,
            "domain_name": self.domain,
            "organization_name": self.organization,
            "description": self.description,
            "mutable": self.mutable,
        }

    def _generate_main_file(
        self, output_dir: Path, template_name: str, context: Dict[str, Any]
    ) -> Path:
        """Generate the main type/model/entity file."""
        filename = f"{self._to_snake_case(self.name)}.py"
        output_path = output_dir / filename

        return self.create_from_template(
            template_name=template_name,
            output_path=output_path,
            context=context,
        )

    def _generate_test_file(
        self, test_dir: Path, context: Dict[str, Any], module_path: Optional[str] = None
    ) -> Path:
        """Generate the test file."""
        filename = f"test_{self._to_snake_case(self.name)}.py"
        output_path = test_dir / filename

        # Add module_path to context
        test_context = context.copy()
        if module_path:
            test_context["module_path"] = module_path
        else:
            # Generate module path based on kind and domain
            if self.domain:
                base = f"foobara_py.domains.{self._to_snake_case(self.domain)}"
            else:
                base = "types"

            kind_dirs = {
                "type": "types",
                "model": "models",
                "entity": "entities",
            }
            test_context["module_path"] = (
                f"{base}.{kind_dirs[self.kind]}.{self._to_snake_case(self.name)}"
            )

        return self.create_from_template(
            template_name="type_test.py.j2",
            output_path=output_path,
            context=test_context,
        )


def generate_type(
    name: str,
    output_dir: Path,
    kind: TypeKind = "model",
    fields: Optional[List[Dict[str, Any]]] = None,
    base_type: Optional[str] = None,
    validators: Optional[List[str]] = None,
    primary_key: str = "id",
    domain: Optional[str] = None,
    organization: Optional[str] = None,
    description: Optional[str] = None,
    mutable: bool = False,
    generate_tests: bool = True,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate a type/model/entity.

    Args:
        name: Type name
        output_dir: Output directory
        kind: "type", "model", or "entity"
        fields: Field definitions
        base_type: Base type for simple types
        validators: Validators for simple types
        primary_key: Primary key field for entities
        domain: Optional domain name
        organization: Optional organization name
        description: Type description
        mutable: Use MutableModel for models
        generate_tests: Whether to generate tests
        **kwargs: Additional options (test_dir, module_path)

    Returns:
        List of generated file paths

    Example:
        # Generate entity
        files = generate_type(
            name="User",
            output_dir=Path("myapp/entities"),
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
            ],
            primary_key="id",
            domain="Users"
        )

        # Generate model
        files = generate_type(
            name="Address",
            output_dir=Path("myapp/models"),
            kind="model",
            fields=[
                {"name": "street", "type": "str"},
                {"name": "city", "type": "str"},
            ]
        )
    """
    generator = TypeGenerator(
        name=name,
        kind=kind,
        fields=fields,
        base_type=base_type,
        validators=validators,
        primary_key=primary_key,
        domain=domain,
        organization=organization,
        description=description,
        mutable=mutable,
        generate_tests=generate_tests,
    )

    return generator.generate(output_dir, **kwargs)
