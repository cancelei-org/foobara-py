"""
Remote Imports generator for Foobara Python.

Generates static Python files for remote commands from a Foobara manifest.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from foobara_py.generators.files_generator import FilesGenerator


class RemoteImportsGenerator(FilesGenerator):
    """
    Generator for creating static remote command files from a manifest.

    Instead of importing commands dynamically at runtime, this generator
    creates actual Python files with proper type hints for remote commands.

    Usage:
        generator = RemoteImportsGenerator(
            manifest_url="https://api.example.com/manifest",
            commands=["Users::CreateUser", "Users::ListUsers"],
            remote_url="https://api.example.com",
            timeout=30.0
        )

        files = generator.generate(output_dir=Path("myapp/remote_commands"))
    """

    def __init__(
        self,
        manifest_url: str,
        remote_url: Optional[str] = None,
        commands: Optional[List[str]] = None,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize remote imports generator.

        Args:
            manifest_url: URL to the remote Foobara manifest
            remote_url: Base URL for running commands (defaults to manifest_url base)
            commands: List of specific commands to import (None = import all)
            timeout: HTTP timeout for remote calls
            headers: Optional HTTP headers for remote calls
        """
        super().__init__()

        self.manifest_url = manifest_url
        self.remote_url = remote_url or self._derive_base_url(manifest_url)
        self.commands_filter = commands
        self.timeout = timeout
        self.headers = headers or {}

        self._manifest_data: Optional[Dict[str, Any]] = None

    def _derive_base_url(self, manifest_url: str) -> str:
        """Derive base URL from manifest URL"""
        if manifest_url.endswith("/manifest"):
            return manifest_url[:-9]

        from urllib.parse import urlparse

        parsed = urlparse(manifest_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _fetch_manifest(self) -> Dict[str, Any]:
        """Fetch manifest from remote URL"""
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for fetching manifests. Install it with: pip install httpx"
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.manifest_url, headers=self.headers)

                if response.status_code >= 400:
                    raise RuntimeError(f"Failed to fetch manifest: HTTP {response.status_code}")

                return response.json()

        except httpx.ConnectError as e:
            raise RuntimeError(f"Failed to connect to {self.manifest_url}: {e}")
        except httpx.TimeoutException:
            raise RuntimeError(f"Request timed out after {self.timeout}s")

    @property
    def manifest(self) -> Dict[str, Any]:
        """Get the manifest data (fetched on first access)"""
        if self._manifest_data is None:
            self._manifest_data = self._fetch_manifest()
        return self._manifest_data

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate remote command files.

        Args:
            output_dir: Directory to generate files in
            **kwargs: Additional options

        Returns:
            List of generated file paths
        """
        files = []

        # Get commands from manifest
        commands = self.manifest.get("commands", [])

        for cmd_data in commands:
            # Filter commands if specified
            full_name = cmd_data.get("full_name") or cmd_data.get("name", "")
            if self.commands_filter and full_name not in self.commands_filter:
                continue

            # Generate file for this command
            cmd_file = self._generate_command_file(output_dir, cmd_data)
            files.append(cmd_file)

        # Generate __init__.py to export all commands
        if files:
            init_file = self._generate_init_file(output_dir, commands)
            files.append(init_file)

        return files

    def _generate_command_file(self, output_dir: Path, cmd_data: Dict[str, Any]) -> Path:
        """Generate a single remote command file"""
        # Extract command metadata
        name = cmd_data.get("name", "UnknownCommand")
        full_name = cmd_data.get("full_name", name)
        description = cmd_data.get("description", "")
        domain = cmd_data.get("domain")
        organization = cmd_data.get("organization")

        # Parse inputs schema
        inputs_schema = cmd_data.get("inputs_type", {}).get("schema", {})
        inputs_fields = self._schema_to_fields(inputs_schema)

        # Parse result schema
        result_schema = cmd_data.get("result_type", {}).get("schema", {})
        result_fields = self._schema_to_fields(result_schema)

        # Build context
        context = {
            "command_name": name,
            "full_name": full_name,
            "description": description,
            "domain": domain,
            "organization": organization,
            "remote_url": self.remote_url,
            "timeout": self.timeout,
            "headers": self.headers,
            "manifest_url": self.manifest_url,
            "generated_at": datetime.now().isoformat(),
            "inputs_fields": inputs_fields,
            "result_fields": result_fields,
            "function_name": self._to_snake_case(name),
        }

        # Generate file
        filename = f"{self._to_snake_case(name)}.py"
        output_path = output_dir / filename

        return self.create_from_template(
            template_name="remote_command.py.j2",
            output_path=output_path,
            context=context,
        )

    def _schema_to_fields(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert JSON Schema to field definitions"""
        if not schema or "properties" not in schema:
            return []

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        fields = []
        for field_name, field_schema in properties.items():
            field_type = self._schema_type_to_string(field_schema)
            is_required = field_name in required

            # Build type annotation
            if is_required:
                type_annotation = field_type
            else:
                type_annotation = f"Optional[{field_type}]"

            # Get default value
            default_value = field_schema.get("default")
            has_default = default_value is not None or not is_required

            if not is_required and default_value is None:
                default_repr = "None"
            elif isinstance(default_value, str):
                default_repr = f'"{default_value}"'
            else:
                default_repr = repr(default_value) if default_value is not None else "None"

            fields.append(
                {
                    "name": field_name,
                    "type_annotation": type_annotation,
                    "description": field_schema.get("description", ""),
                    "has_default": has_default,
                    "default": default_repr if has_default else None,
                    "required": is_required,
                }
            )

        return fields

    def _schema_type_to_string(self, schema: Dict[str, Any]) -> str:
        """Convert JSON Schema type to Python type string"""
        json_type = schema.get("type", "string")

        type_map = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
            "null": "None",
        }

        if json_type == "array":
            items_schema = schema.get("items", {})
            items_type = self._schema_type_to_string(items_schema)
            return f"List[{items_type}]"

        return type_map.get(json_type, "Any")

    def _generate_init_file(self, output_dir: Path, commands: List[Dict[str, Any]]) -> Path:
        """Generate __init__.py to export all commands"""
        output_path = output_dir / "__init__.py"

        # Build imports and exports
        imports = []
        exports = []

        for cmd_data in commands:
            # Filter commands if specified
            full_name = cmd_data.get("full_name") or cmd_data.get("name", "")
            if self.commands_filter and full_name not in self.commands_filter:
                continue

            name = cmd_data.get("name", "")
            if not name:
                continue

            module_name = self._to_snake_case(name)
            imports.append(f"from .{module_name} import {name}, {self._to_snake_case(name)}")
            exports.append(f'    "{name}",')
            exports.append(f'    "{self._to_snake_case(name)}",')

        content = f'''"""
Remote commands imported from {self.manifest_url}

Auto-generated at: {datetime.now().isoformat()}
"""

{chr(10).join(imports)}

__all__ = [
{chr(10).join(exports)}
]
'''

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

        return output_path


def generate_remote_imports(
    manifest_url: str,
    output_dir: Path,
    remote_url: Optional[str] = None,
    commands: Optional[List[str]] = None,
    timeout: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate remote command files.

    Args:
        manifest_url: URL to the remote Foobara manifest
        output_dir: Output directory
        remote_url: Base URL for running commands
        commands: List of specific commands to import
        timeout: HTTP timeout
        headers: Optional HTTP headers
        **kwargs: Additional options

    Returns:
        List of generated file paths

    Example:
        files = generate_remote_imports(
            manifest_url="https://api.example.com/manifest",
            output_dir=Path("myapp/remote"),
            commands=["Users::CreateUser", "Users::ListUsers"]
        )
    """
    generator = RemoteImportsGenerator(
        manifest_url=manifest_url,
        remote_url=remote_url,
        commands=commands,
        timeout=timeout,
        headers=headers,
    )

    return generator.generate(output_dir, **kwargs)
