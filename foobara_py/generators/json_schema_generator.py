"""
JSON Schema Generator for Foobara commands.

Generates JSON Schema and OpenAPI specifications from Foobara command manifests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode

from foobara_py.core.command import Command
from foobara_py.core.registry import CommandRegistry


@dataclass
class OpenAPIInfo:
    """OpenAPI Info object."""

    title: str = "Foobara API"
    version: str = "1.0.0"
    description: str = "API generated from Foobara commands"
    terms_of_service: Optional[str] = None
    contact: Optional[Dict[str, str]] = None
    license: Optional[Dict[str, str]] = None


@dataclass
class OpenAPIServer:
    """OpenAPI Server object."""

    url: str = "http://localhost:8000"
    description: str = "Local development server"
    variables: Optional[Dict[str, Any]] = None


@dataclass
class OpenAPIConfig:
    """Configuration for OpenAPI generation."""

    info: OpenAPIInfo = field(default_factory=OpenAPIInfo)
    servers: List[OpenAPIServer] = field(default_factory=lambda: [OpenAPIServer()])
    tags: Optional[List[Dict[str, str]]] = None
    security_schemes: Optional[Dict[str, Any]] = None
    default_security: Optional[List[Dict[str, List[str]]]] = None


class FoobaraJsonSchemaGenerator(GenerateJsonSchema):
    """Custom JSON Schema generator for Foobara types."""

    def generate(self, schema: Any, mode: JsonSchemaMode = "validation") -> Dict[str, Any]:
        """Generate JSON schema with Foobara-specific modifications."""
        json_schema = super().generate(schema, mode)
        return json_schema


def get_pydantic_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """Get JSON Schema from a Pydantic model."""
    try:
        return model.model_json_schema(
            schema_generator=FoobaraJsonSchemaGenerator,
            mode="serialization"
        )
    except Exception:
        # Fallback for models that can't generate schema
        return {"type": "object"}


def python_type_to_json_schema(python_type: Any) -> Dict[str, Any]:
    """Convert Python type annotation to JSON Schema."""
    if python_type is None or python_type is type(None):
        return {"type": "null"}

    # Handle string type names
    if isinstance(python_type, str):
        type_map = {
            "str": {"type": "string"},
            "int": {"type": "integer"},
            "float": {"type": "number"},
            "bool": {"type": "boolean"},
            "None": {"type": "null"},
            "list": {"type": "array"},
            "dict": {"type": "object"},
            "Any": {},
        }
        return type_map.get(python_type, {"type": "string"})

    # Handle actual types
    if python_type is str:
        return {"type": "string"}
    if python_type is int:
        return {"type": "integer"}
    if python_type is float:
        return {"type": "number"}
    if python_type is bool:
        return {"type": "boolean"}
    if python_type is list:
        return {"type": "array"}
    if python_type is dict:
        return {"type": "object"}

    # Handle Pydantic models
    if isinstance(python_type, type) and issubclass(python_type, BaseModel):
        return get_pydantic_schema(python_type)

    # Handle typing generics
    origin = getattr(python_type, "__origin__", None)
    args = getattr(python_type, "__args__", ())

    if origin is list:
        items_schema = python_type_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": items_schema}

    if origin is dict:
        return {"type": "object"}

    if origin is Union:
        # Handle Optional (Union[X, None])
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1 and type(None) in args:
            schema = python_type_to_json_schema(non_none_args[0])
            return {"anyOf": [schema, {"type": "null"}]}
        return {"anyOf": [python_type_to_json_schema(a) for a in args]}

    # Default to string
    return {"type": "string"}


class JsonSchemaGenerator:
    """Generates JSON Schema from Foobara commands."""

    def __init__(self, registry: Optional[CommandRegistry] = None):
        """Initialize the generator.

        Args:
            registry: Command registry to use. Uses default if not provided.
        """
        self.registry = registry or CommandRegistry.get_default()

    def generate_command_input_schema(
        self,
        command_class: Type[Command],
    ) -> Dict[str, Any]:
        """Generate JSON Schema for command inputs.

        Args:
            command_class: The command class to generate schema for.

        Returns:
            JSON Schema dictionary for command inputs.
        """
        # Try to get schema from Inputs model
        inputs_type = getattr(command_class, "Inputs", None)
        if inputs_type and isinstance(inputs_type, type) and issubclass(inputs_type, BaseModel):
            schema = get_pydantic_schema(inputs_type)
            schema["title"] = f"{command_class.__name__}Inputs"
            return schema

        # Fallback: inspect type hints
        schema: Dict[str, Any] = {
            "type": "object",
            "title": f"{command_class.__name__}Inputs",
            "properties": {},
            "required": [],
        }

        # Try to get inputs from annotations
        annotations = getattr(command_class, "__annotations__", {})
        for name, type_hint in annotations.items():
            if not name.startswith("_"):
                schema["properties"][name] = python_type_to_json_schema(type_hint)

        return schema

    def generate_command_output_schema(
        self,
        command_class: Type[Command],
    ) -> Dict[str, Any]:
        """Generate JSON Schema for command output/result.

        Args:
            command_class: The command class to generate schema for.

        Returns:
            JSON Schema dictionary for command output.
        """
        # Try to get schema from Result model
        result_type = getattr(command_class, "Result", None)
        if result_type and isinstance(result_type, type) and issubclass(result_type, BaseModel):
            schema = get_pydantic_schema(result_type)
            schema["title"] = f"{command_class.__name__}Result"
            return schema

        # Try to get from generic parameters
        orig_bases = getattr(command_class, "__orig_bases__", ())
        for base in orig_bases:
            args = getattr(base, "__args__", ())
            if len(args) >= 2:
                result_type = args[1]
                return python_type_to_json_schema(result_type)

        return {"type": "object", "title": f"{command_class.__name__}Result"}

    def generate_command_error_schema(
        self,
        command_class: Type[Command],
    ) -> Dict[str, Any]:
        """Generate JSON Schema for command errors.

        Args:
            command_class: The command class to generate schema for.

        Returns:
            JSON Schema dictionary for command errors.
        """
        return {
            "type": "object",
            "title": f"{command_class.__name__}Error",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Error key identifier"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the error location"
                },
                "runtime_path": {
                    "type": "string",
                    "description": "Runtime path for nested command errors"
                },
                "message": {
                    "type": "string",
                    "description": "Human-readable error message"
                },
                "context": {
                    "type": "object",
                    "description": "Additional error context"
                },
                "category": {
                    "type": "string",
                    "enum": ["data", "runtime"],
                    "description": "Error category"
                }
            },
            "required": ["key", "message"]
        }

    def generate_command_schema(
        self,
        command_class: Type[Command],
    ) -> Dict[str, Any]:
        """Generate complete JSON Schema for a command.

        Args:
            command_class: The command class to generate schema for.

        Returns:
            Complete JSON Schema dictionary for the command.
        """
        return {
            "title": command_class.__name__,
            "description": getattr(command_class, "__doc__", "") or "",
            "type": "object",
            "properties": {
                "inputs": self.generate_command_input_schema(command_class),
                "result": self.generate_command_output_schema(command_class),
                "errors": {
                    "type": "array",
                    "items": self.generate_command_error_schema(command_class)
                }
            }
        }

    def generate_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Generate JSON Schemas for all registered commands.

        Returns:
            Dictionary mapping command names to their schemas.
        """
        schemas = {}
        for command_class in self.registry.list_commands():
            name = command_class.__name__
            schemas[name] = self.generate_command_schema(command_class)
        return schemas


class OpenAPIGenerator:
    """Generates OpenAPI 3.0 specification from Foobara commands."""

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        config: Optional[OpenAPIConfig] = None,
    ):
        """Initialize the OpenAPI generator.

        Args:
            registry: Command registry to use.
            config: OpenAPI configuration.
        """
        self.registry = registry or CommandRegistry.get_default()
        self.config = config or OpenAPIConfig()
        self.schema_generator = JsonSchemaGenerator(registry)

    def _command_to_path(self, command_name: str) -> str:
        """Convert command name to URL path."""
        import re
        # First replace :: with / to preserve namespace structure
        name = command_name.replace("::", "/")
        # Convert each path segment from CamelCase to kebab-case
        segments = name.split("/")
        kebab_segments = []
        for segment in segments:
            kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", segment).lower()
            kebab_segments.append(kebab)
        name = "/".join(kebab_segments)
        return f"/commands/{name}"

    def _command_to_operation_id(self, command_name: str) -> str:
        """Convert command name to operation ID."""
        return command_name.replace("::", "_")

    def _extract_tags(self, command_class: Type[Command]) -> List[str]:
        """Extract tags from command (domain name, etc.)."""
        tags = []

        # Try to get domain from command
        domain = getattr(command_class, "_domain", None)
        if domain:
            domain_name = getattr(domain, "name", None) or domain.__name__
            tags.append(domain_name)

        return tags or ["commands"]

    def generate_path_item(
        self,
        command_class: Type[Command],
    ) -> Dict[str, Any]:
        """Generate OpenAPI path item for a command.

        Args:
            command_class: The command class.

        Returns:
            OpenAPI path item dictionary.
        """
        command_name = command_class.__name__
        description = getattr(command_class, "__doc__", "") or ""

        input_schema = self.schema_generator.generate_command_input_schema(command_class)
        output_schema = self.schema_generator.generate_command_output_schema(command_class)
        error_schema = self.schema_generator.generate_command_error_schema(command_class)

        return {
            "post": {
                "operationId": self._command_to_operation_id(command_name),
                "summary": command_name,
                "description": description.strip(),
                "tags": self._extract_tags(command_class),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": input_schema
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Successful execution",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "const": True},
                                        "result": output_schema
                                    },
                                    "required": ["success", "result"]
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Validation error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "const": False},
                                        "errors": {
                                            "type": "array",
                                            "items": error_schema
                                        }
                                    },
                                    "required": ["success", "errors"]
                                }
                            }
                        }
                    },
                    "401": {
                        "description": "Authentication required",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AuthError"}
                            }
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ServerError"}
                            }
                        }
                    }
                }
            }
        }

    def generate_components(self) -> Dict[str, Any]:
        """Generate OpenAPI components section."""
        components: Dict[str, Any] = {
            "schemas": {
                "AuthError": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "const": False},
                        "error": {"type": "string"},
                        "message": {"type": "string"}
                    },
                    "required": ["success", "error"]
                },
                "ServerError": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "const": False},
                        "error": {"type": "string"},
                        "message": {"type": "string"},
                        "trace_id": {"type": "string"}
                    },
                    "required": ["success", "error"]
                }
            }
        }

        # Add security schemes if configured
        if self.config.security_schemes:
            components["securitySchemes"] = self.config.security_schemes
        else:
            # Default security schemes
            components["securitySchemes"] = {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                },
                "apiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            }

        return components

    def generate_spec(
        self,
        commands: Optional[List[Type[Command]]] = None,
    ) -> Dict[str, Any]:
        """Generate complete OpenAPI 3.0 specification.

        Args:
            commands: Optional list of specific commands to include.
                     If not provided, includes all registered commands.

        Returns:
            Complete OpenAPI specification dictionary.
        """
        spec: Dict[str, Any] = {
            "openapi": "3.0.3",
            "info": {
                "title": self.config.info.title,
                "version": self.config.info.version,
                "description": self.config.info.description,
            },
            "servers": [
                {
                    "url": server.url,
                    "description": server.description,
                }
                for server in self.config.servers
            ],
            "paths": {},
            "components": self.generate_components(),
        }

        # Add optional info fields
        if self.config.info.terms_of_service:
            spec["info"]["termsOfService"] = self.config.info.terms_of_service
        if self.config.info.contact:
            spec["info"]["contact"] = self.config.info.contact
        if self.config.info.license:
            spec["info"]["license"] = self.config.info.license

        # Add tags if configured
        if self.config.tags:
            spec["tags"] = self.config.tags

        # Add default security if configured
        if self.config.default_security:
            spec["security"] = self.config.default_security

        # Generate paths for commands
        if commands is None:
            commands = self.registry.list_commands()

        for command_class in commands:
            path = self._command_to_path(command_class.__name__)
            spec["paths"][path] = self.generate_path_item(command_class)

        return spec

    def generate_yaml(
        self,
        commands: Optional[List[Type[Command]]] = None,
    ) -> str:
        """Generate OpenAPI spec as YAML string.

        Args:
            commands: Optional list of specific commands.

        Returns:
            YAML string of the OpenAPI specification.
        """
        import yaml
        spec = self.generate_spec(commands)
        return yaml.dump(spec, default_flow_style=False, sort_keys=False)

    def generate_json(
        self,
        commands: Optional[List[Type[Command]]] = None,
        indent: int = 2,
    ) -> str:
        """Generate OpenAPI spec as JSON string.

        Args:
            commands: Optional list of specific commands.
            indent: JSON indentation level.

        Returns:
            JSON string of the OpenAPI specification.
        """
        import json
        spec = self.generate_spec(commands)
        return json.dumps(spec, indent=indent)


# Convenience functions
def generate_json_schema(
    command_class: Type[Command],
    registry: Optional[CommandRegistry] = None,
) -> Dict[str, Any]:
    """Generate JSON Schema for a single command.

    Args:
        command_class: The command class.
        registry: Optional command registry.

    Returns:
        JSON Schema dictionary.
    """
    generator = JsonSchemaGenerator(registry)
    return generator.generate_command_schema(command_class)


def generate_openapi_spec(
    commands: Optional[List[Type[Command]]] = None,
    config: Optional[OpenAPIConfig] = None,
    registry: Optional[CommandRegistry] = None,
) -> Dict[str, Any]:
    """Generate OpenAPI specification for commands.

    Args:
        commands: Optional list of commands. Uses all registered if None.
        config: Optional OpenAPI configuration.
        registry: Optional command registry.

    Returns:
        OpenAPI specification dictionary.
    """
    generator = OpenAPIGenerator(registry, config)
    return generator.generate_spec(commands)


def generate_openapi_yaml(
    commands: Optional[List[Type[Command]]] = None,
    config: Optional[OpenAPIConfig] = None,
    registry: Optional[CommandRegistry] = None,
) -> str:
    """Generate OpenAPI specification as YAML.

    Args:
        commands: Optional list of commands.
        config: Optional OpenAPI configuration.
        registry: Optional command registry.

    Returns:
        YAML string.
    """
    generator = OpenAPIGenerator(registry, config)
    return generator.generate_yaml(commands)


def generate_openapi_json(
    commands: Optional[List[Type[Command]]] = None,
    config: Optional[OpenAPIConfig] = None,
    registry: Optional[CommandRegistry] = None,
    indent: int = 2,
) -> str:
    """Generate OpenAPI specification as JSON.

    Args:
        commands: Optional list of commands.
        config: Optional OpenAPI configuration.
        registry: Optional command registry.
        indent: JSON indentation.

    Returns:
        JSON string.
    """
    generator = OpenAPIGenerator(registry, config)
    return generator.generate_json(commands, indent)
