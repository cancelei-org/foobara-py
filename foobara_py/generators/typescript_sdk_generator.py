"""
TypeScript SDK Generator for Foobara commands.

Generates TypeScript client code from Foobara command manifests,
including type definitions, API client, and error types.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

from pydantic import BaseModel

from foobara_py.core.command import Command
from foobara_py.core.registry import CommandRegistry


@dataclass
class TypeScriptSDKConfig:
    """Configuration for TypeScript SDK generation."""

    # Output settings
    output_dir: str = "./generated"
    file_prefix: str = "foobara"

    # API client settings
    base_url: str = "http://localhost:8000"
    api_path_prefix: str = "/commands"

    # Code style
    use_interfaces: bool = True  # Use interfaces vs types
    use_enums: bool = True  # Use enums vs string unions
    use_strict_null_checks: bool = True

    # Generated file structure
    single_file: bool = False  # Generate single file or multiple
    include_index: bool = True  # Generate index.ts

    # Client options
    include_fetch_client: bool = True
    include_axios_client: bool = False

    # Documentation
    include_jsdoc: bool = True


def python_type_to_typescript(
    python_type: Any,
    nullable: bool = True,
    use_strict_null: bool = True,
) -> str:
    """Convert Python type annotation to TypeScript type."""
    if python_type is None or python_type is type(None):
        return "null"

    # Handle string type names
    if isinstance(python_type, str):
        type_map = {
            "str": "string",
            "int": "number",
            "float": "number",
            "bool": "boolean",
            "None": "null",
            "list": "any[]",
            "dict": "Record<string, any>",
            "Any": "any",
        }
        ts_type = type_map.get(python_type, "any")
        if nullable and use_strict_null and python_type != "None":
            return f"{ts_type} | null"
        return ts_type

    # Handle actual types
    if python_type is str:
        ts_type = "string"
    elif python_type is int or python_type is float:
        ts_type = "number"
    elif python_type is bool:
        ts_type = "boolean"
    elif python_type is list:
        ts_type = "any[]"
    elif python_type is dict:
        ts_type = "Record<string, any>"
    else:
        # Handle typing generics
        origin = getattr(python_type, "__origin__", None)
        args = getattr(python_type, "__args__", ())

        if origin is list:
            item_type = python_type_to_typescript(
                args[0] if args else Any,
                nullable=False,
                use_strict_null=use_strict_null,
            )
            ts_type = f"{item_type}[]"
        elif origin is dict:
            key_type = "string"
            value_type = python_type_to_typescript(
                args[1] if len(args) > 1 else Any,
                nullable=False,
                use_strict_null=use_strict_null,
            )
            ts_type = f"Record<{key_type}, {value_type}>"
        elif origin is Union:
            # Handle Optional
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1 and type(None) in args:
                inner_type = python_type_to_typescript(
                    non_none_args[0],
                    nullable=False,
                    use_strict_null=use_strict_null,
                )
                return f"{inner_type} | null" if use_strict_null else inner_type
            else:
                union_types = [
                    python_type_to_typescript(a, nullable=False, use_strict_null=use_strict_null)
                    for a in args
                ]
                ts_type = " | ".join(union_types)
        else:
            # Check for Pydantic model
            if isinstance(python_type, type) and issubclass(python_type, BaseModel):
                ts_type = python_type.__name__
            else:
                ts_type = "any"

    return ts_type


class TypeScriptSDKGenerator:
    """Generates TypeScript SDK from Foobara commands."""

    def __init__(
        self,
        registry: CommandRegistry | None = None,
        config: TypeScriptSDKConfig | None = None,
    ):
        """Initialize the generator.

        Args:
            registry: Command registry to use.
            config: SDK generation configuration.
        """
        self.registry = registry or CommandRegistry()
        self.config = config or TypeScriptSDKConfig()
        self._generated_types: set[str] = set()

    def _to_camel_case(self, name: str) -> str:
        """Convert to camelCase."""
        # Handle PascalCase (e.g., CreateUser -> createUser)
        if "_" not in name and "-" not in name:
            return name[0].lower() + name[1:] if name else name
        # Handle snake_case
        parts = name.replace("-", "_").split("_")
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    def _to_pascal_case(self, name: str) -> str:
        """Convert to PascalCase."""
        parts = name.replace("-", "_").split("_")
        return "".join(p.capitalize() for p in parts)

    def _generate_jsdoc(self, description: str, params: dict[str, str] | None = None) -> str:
        """Generate JSDoc comment."""
        if not self.config.include_jsdoc:
            return ""

        lines = ["/**"]
        if description:
            for line in description.strip().split("\n"):
                lines.append(f" * {line}")

        if params:
            lines.append(" *")
            for name, desc in params.items():
                lines.append(f" * @param {name} - {desc}")

        lines.append(" */")
        return "\n".join(lines)

    def _generate_interface_from_model(
        self,
        model: type[BaseModel],
        name: str | None = None,
    ) -> str:
        """Generate TypeScript interface from Pydantic model."""
        type_name = name or model.__name__
        if type_name in self._generated_types:
            return ""
        self._generated_types.add(type_name)

        lines = []

        # Add JSDoc
        doc = getattr(model, "__doc__", "") or ""
        if doc:
            lines.append(self._generate_jsdoc(doc))

        if self.config.use_interfaces:
            lines.append(f"export interface {type_name} {{")
        else:
            lines.append(f"export type {type_name} = {{")

        for field_name, field_info in model.model_fields.items():
            annotation = field_info.annotation
            ts_type = python_type_to_typescript(
                annotation,
                nullable=not field_info.is_required(),
                use_strict_null=self.config.use_strict_null_checks,
            )

            optional = "?" if not field_info.is_required() else ""
            description = field_info.description or ""
            if description and self.config.include_jsdoc:
                lines.append(f"  /** {description} */")
            lines.append(f"  {field_name}{optional}: {ts_type};")

        if self.config.use_interfaces:
            lines.append("}")
        else:
            lines.append("};")

        return "\n".join(lines)

    def _generate_command_types(self, command_class: type[Command]) -> str:
        """Generate TypeScript types for a command."""
        parts = []

        # Input type
        inputs_type = getattr(command_class, "Inputs", None)
        if inputs_type and isinstance(inputs_type, type) and issubclass(inputs_type, BaseModel):
            input_interface = self._generate_interface_from_model(
                inputs_type,
                f"{command_class.__name__}Input",
            )
            if input_interface:
                parts.append(input_interface)

        # Result type
        result_type = getattr(command_class, "Result", None)
        if result_type and isinstance(result_type, type) and issubclass(result_type, BaseModel):
            result_interface = self._generate_interface_from_model(
                result_type,
                f"{command_class.__name__}Result",
            )
            if result_interface:
                parts.append(result_interface)

        return "\n\n".join(parts)

    def _generate_error_types(self) -> str:
        """Generate TypeScript error types."""
        return '''/**
 * Foobara error categories
 */
export type FoobaraErrorCategory = 'data' | 'runtime';

/**
 * Foobara error structure
 */
export interface FoobaraError {
  key: string;
  message: string;
  path?: string;
  runtime_path?: string;
  category?: FoobaraErrorCategory;
  context?: Record<string, any>;
}

/**
 * Foobara command outcome
 */
export interface FoobaraOutcome<T> {
  success: boolean;
  result?: T;
  errors?: FoobaraError[];
}

/**
 * API error response
 */
export class FoobaraApiError extends Error {
  public readonly errors: FoobaraError[];
  public readonly statusCode: number;

  constructor(message: string, errors: FoobaraError[], statusCode: number = 400) {
    super(message);
    this.name = 'FoobaraApiError';
    this.errors = errors;
    this.statusCode = statusCode;
  }
}'''

    def _generate_fetch_client(self) -> str:
        """Generate fetch-based API client."""
        return f'''/**
 * Foobara API client configuration
 */
export interface FoobaraClientConfig {{
  baseUrl?: string;
  headers?: Record<string, string>;
  timeout?: number;
}}

/**
 * Foobara API client using fetch
 */
export class FoobaraClient {{
  private readonly baseUrl: string;
  private readonly headers: Record<string, string>;
  private readonly timeout: number;

  constructor(config: FoobaraClientConfig = {{}}) {{
    this.baseUrl = config.baseUrl ?? '{self.config.base_url}';
    this.headers = {{
      'Content-Type': 'application/json',
      ...config.headers,
    }};
    this.timeout = config.timeout ?? 30000;
  }}

  private async request<T>(
    path: string,
    inputs: Record<string, any>,
  ): Promise<FoobaraOutcome<T>> {{
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {{
      const response = await fetch(`${{this.baseUrl}}${{path}}`, {{
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(inputs),
        signal: controller.signal,
      }});

      clearTimeout(timeoutId);

      const data = await response.json();

      if (!response.ok) {{
        throw new FoobaraApiError(
          data.error || 'Request failed',
          data.errors || [],
          response.status,
        );
      }}

      return data as FoobaraOutcome<T>;
    }} catch (error) {{
      clearTimeout(timeoutId);
      if (error instanceof FoobaraApiError) {{
        throw error;
      }}
      throw new FoobaraApiError(
        error instanceof Error ? error.message : 'Unknown error',
        [],
        500,
      );
    }}
  }}
'''

    def _generate_command_method(self, command_class: type[Command]) -> str:
        """Generate TypeScript method for a command."""
        command_name = command_class.__name__
        method_name = self._to_camel_case(command_name)
        description = getattr(command_class, "__doc__", "") or ""

        # Determine input and result types
        inputs_type = getattr(command_class, "Inputs", None)
        result_type = getattr(command_class, "Result", None)

        input_type_name = f"{command_name}Input" if inputs_type else "Record<string, any>"
        result_type_name = f"{command_name}Result" if result_type else "any"

        path = f"{self.config.api_path_prefix}/{self._to_camel_case(command_name).replace('::', '/')}"

        # Generate JSDoc
        jsdoc = ""
        if self.config.include_jsdoc and description:
            jsdoc = f'''  /**
   * {description.strip()}
   */
'''

        return f'''{jsdoc}  async {method_name}(inputs: {input_type_name}): Promise<FoobaraOutcome<{result_type_name}>> {{
    return this.request<{result_type_name}>('{path}', inputs);
  }}'''

    def _generate_client_methods(
        self,
        commands: list[type[Command]],
    ) -> str:
        """Generate all command methods for the client."""
        methods = []
        for command_class in commands:
            methods.append(self._generate_command_method(command_class))
        return "\n\n".join(methods)

    def generate_types_file(
        self,
        commands: list[type[Command]] | None = None,
    ) -> str:
        """Generate TypeScript types file content.

        Args:
            commands: List of commands to generate types for.

        Returns:
            TypeScript file content.
        """
        self._generated_types.clear()

        if commands is None:
            commands = self.registry.list_commands()

        parts = [
            "// Auto-generated by foobara-py TypeScript SDK Generator",
            "// Do not edit manually",
            "",
        ]

        # Generate error types
        parts.append(self._generate_error_types())
        parts.append("")

        # Generate command types
        for command_class in commands:
            command_types = self._generate_command_types(command_class)
            if command_types:
                parts.append(command_types)
                parts.append("")

        return "\n".join(parts)

    def generate_client_file(
        self,
        commands: list[type[Command]] | None = None,
    ) -> str:
        """Generate TypeScript client file content.

        Args:
            commands: List of commands to include in client.

        Returns:
            TypeScript file content.
        """
        if commands is None:
            commands = self.registry.list_commands()

        parts = [
            "// Auto-generated by foobara-py TypeScript SDK Generator",
            "// Do not edit manually",
            "",
            "import type {",
            "  FoobaraOutcome,",
            "  FoobaraError,",
            "  FoobaraApiError,",
        ]

        # Import command types
        for command_class in commands:
            parts.append(f"  {command_class.__name__}Input,")
            parts.append(f"  {command_class.__name__}Result,")

        parts.append("} from './types';")
        parts.append("")

        # Re-export error types
        parts.append("export { FoobaraOutcome, FoobaraError, FoobaraApiError };")
        parts.append("")

        # Generate client class
        if self.config.include_fetch_client:
            parts.append(self._generate_fetch_client())
            parts.append("")
            parts.append(self._generate_client_methods(commands))
            parts.append("}")

        return "\n".join(parts)

    def generate_index_file(self) -> str:
        """Generate index.ts barrel file."""
        return '''// Auto-generated by foobara-py TypeScript SDK Generator
// Do not edit manually

export * from './types';
export * from './client';
'''

    def generate_sdk(
        self,
        commands: list[type[Command]] | None = None,
    ) -> dict[str, str]:
        """Generate complete SDK.

        Args:
            commands: List of commands to include.

        Returns:
            Dictionary mapping file names to content.
        """
        if commands is None:
            commands = self.registry.list_commands()

        files = {}

        if self.config.single_file:
            # Generate single file
            content = self.generate_types_file(commands)
            content += "\n\n" + self.generate_client_file(commands)
            files[f"{self.config.file_prefix}.ts"] = content
        else:
            # Generate multiple files
            files["types.ts"] = self.generate_types_file(commands)
            files["client.ts"] = self.generate_client_file(commands)

            if self.config.include_index:
                files["index.ts"] = self.generate_index_file()

        return files

    def write_sdk(
        self,
        commands: list[type[Command]] | None = None,
        output_dir: str | None = None,
    ) -> list[Path]:
        """Generate and write SDK files to disk.

        Args:
            commands: List of commands to include.
            output_dir: Output directory (uses config if not provided).

        Returns:
            List of written file paths.
        """
        output_path = Path(output_dir or self.config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        files = self.generate_sdk(commands)
        written_files = []

        for filename, content in files.items():
            file_path = output_path / filename
            file_path.write_text(content)
            written_files.append(file_path)

        return written_files


# Convenience functions
def generate_typescript_sdk(
    registry: CommandRegistry | None = None,
    config: TypeScriptSDKConfig | None = None,
    commands: list[type[Command]] | None = None,
) -> dict[str, str]:
    """Generate TypeScript SDK files.

    Args:
        registry: Command registry.
        config: SDK configuration.
        commands: Optional list of specific commands.

    Returns:
        Dictionary mapping file names to content.
    """
    generator = TypeScriptSDKGenerator(registry, config)
    return generator.generate_sdk(commands)


def generate_typescript_types(
    registry: CommandRegistry | None = None,
    commands: list[type[Command]] | None = None,
) -> str:
    """Generate TypeScript type definitions.

    Args:
        registry: Command registry.
        commands: Optional list of specific commands.

    Returns:
        TypeScript types file content.
    """
    generator = TypeScriptSDKGenerator(registry)
    return generator.generate_types_file(commands)


def generate_typescript_client(
    registry: CommandRegistry | None = None,
    config: TypeScriptSDKConfig | None = None,
    commands: list[type[Command]] | None = None,
) -> str:
    """Generate TypeScript API client.

    Args:
        registry: Command registry.
        config: SDK configuration.
        commands: Optional list of specific commands.

    Returns:
        TypeScript client file content.
    """
    generator = TypeScriptSDKGenerator(registry, config)
    return generator.generate_client_file(commands)
