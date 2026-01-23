"""
Command generator for Foobara Python.

Generates new Foobara command classes with inputs, outputs, and tests.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from foobara_py.generators.files_generator import FilesGenerator


class CommandGenerator(FilesGenerator):
    """
    Generator for Foobara command classes.

    Creates:
    - Command class file with inputs and execute stub
    - Test file with basic test cases
    - Optional domain registration

    Usage:
        generator = CommandGenerator(
            name="CreateUser",
            domain="Users",
            organization="MyApp",
            inputs=[
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
            ],
            result_type="User",
            description="Create a new user account"
        )

        files = generator.generate(output_dir=Path("myapp/commands"))
    """

    def __init__(
        self,
        name: str,
        domain: Optional[str] = None,
        organization: Optional[str] = None,
        inputs: Optional[List[Dict[str, Any]]] = None,
        result_type: Optional[str] = None,
        description: Optional[str] = None,
        generate_tests: bool = True,
    ):
        """
        Initialize command generator.

        Args:
            name: Command name (e.g., "CreateUser", "FetchData")
            domain: Optional domain name
            organization: Optional organization name
            inputs: List of input fields [{"name": "email", "type": "str", "default": None, "description": "..."}]
            result_type: Return type annotation (e.g., "User", "str", "dict")
            description: Command description for docstring
            generate_tests: Whether to generate test file
        """
        super().__init__()

        self.name = name
        self.domain = domain
        self.organization = organization
        self.inputs = inputs or []
        self.result_type = result_type
        self.description = description
        self.generate_tests = generate_tests

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate command files.

        Args:
            output_dir: Directory to generate files in
            **kwargs: Additional options (test_dir, module_path)

        Returns:
            List of generated file paths
        """
        files = []

        # Prepare context
        context = self._build_context()

        # Generate command file
        command_file = self._generate_command_file(output_dir, context)
        files.append(command_file)

        # Generate test file
        if self.generate_tests:
            test_dir = kwargs.get("test_dir", output_dir.parent.parent / "tests")
            test_file = self._generate_test_file(test_dir, context, kwargs.get("module_path"))
            files.append(test_file)

        return files

    def _build_context(self) -> Dict[str, Any]:
        """Build template context from generator configuration."""
        return {
            "command_name": self.name,
            "domain_name": self.domain,
            "organization_name": self.organization,
            "has_inputs": len(self.inputs) > 0,
            "input_fields": self.inputs,
            "result_type": self.result_type,
            "description": self.description,
        }

    def _generate_command_file(self, output_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate the command class file."""
        filename = f"{self._to_snake_case(self.name)}.py"
        output_path = output_dir / filename

        return self.create_from_template(
            template_name="command.py.j2",
            output_path=output_path,
            context=context,
        )

    def _generate_test_file(
        self, test_dir: Path, context: Dict[str, Any], module_path: Optional[str] = None
    ) -> Path:
        """Generate the command test file."""
        filename = f"test_{self._to_snake_case(self.name)}.py"
        output_path = test_dir / filename

        # Add module_path to context
        test_context = context.copy()
        if module_path:
            test_context["module_path"] = module_path
        else:
            # Generate module path based on domain
            if self.domain:
                test_context["module_path"] = (
                    f"foobara_py.domains.{self._to_snake_case(self.domain)}.commands.{self._to_snake_case(self.name)}"
                )
            else:
                test_context["module_path"] = f"commands.{self._to_snake_case(self.name)}"

        return self.create_from_template(
            template_name="command_test.py.j2",
            output_path=output_path,
            context=test_context,
        )


def generate_command(
    name: str,
    output_dir: Path,
    domain: Optional[str] = None,
    organization: Optional[str] = None,
    inputs: Optional[List[Dict[str, Any]]] = None,
    result_type: Optional[str] = None,
    description: Optional[str] = None,
    generate_tests: bool = True,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate a command.

    Args:
        name: Command name
        output_dir: Output directory
        domain: Optional domain name
        organization: Optional organization name
        inputs: List of input field definitions
        result_type: Return type annotation
        description: Command description
        generate_tests: Whether to generate tests
        **kwargs: Additional options (test_dir, module_path)

    Returns:
        List of generated file paths

    Example:
        files = generate_command(
            name="CreateUser",
            output_dir=Path("myapp/commands"),
            domain="Users",
            inputs=[
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
            ],
            result_type="User",
        )
    """
    generator = CommandGenerator(
        name=name,
        domain=domain,
        organization=organization,
        inputs=inputs,
        result_type=result_type,
        description=description,
        generate_tests=generate_tests,
    )

    return generator.generate(output_dir, **kwargs)
