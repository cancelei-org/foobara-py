"""
GraphQL Connector for Foobara commands.

Exposes Foobara commands as GraphQL queries and mutations with automatic
schema generation and type conversion.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from foobara_py.core.command import AsyncCommand, Command
from foobara_py.core.registry import CommandRegistry


class GraphQLOperationType(Enum):
    """GraphQL operation type."""

    QUERY = "query"
    MUTATION = "mutation"


@dataclass
class GraphQLFieldConfig:
    """Configuration for a GraphQL field."""

    name: str
    description: str = ""
    operation_type: GraphQLOperationType = GraphQLOperationType.MUTATION
    deprecation_reason: Optional[str] = None
    require_auth: bool = False


@dataclass
class GraphQLConfig:
    """Configuration for GraphQL schema generation."""

    # Schema metadata
    schema_description: str = "Foobara Commands GraphQL API"

    # Default operation type for commands
    default_operation_type: GraphQLOperationType = GraphQLOperationType.MUTATION

    # Commands that should be queries (read-only operations)
    query_commands: List[str] = field(default_factory=list)

    # Custom field configurations
    field_configs: Dict[str, GraphQLFieldConfig] = field(default_factory=dict)

    # Enable introspection
    enable_introspection: bool = True

    # Max query depth
    max_depth: Optional[int] = None

    # Enable batching
    enable_batching: bool = True


def python_type_to_graphql(python_type: Any, nullable: bool = True) -> str:
    """Convert Python type annotation to GraphQL type string."""
    if python_type is None or python_type is type(None):
        return "String"

    # Handle string type names
    if isinstance(python_type, str):
        type_map = {
            "str": "String",
            "int": "Int",
            "float": "Float",
            "bool": "Boolean",
            "None": "String",
            "list": "[String]",
            "dict": "JSON",
            "Any": "JSON",
        }
        gql_type = type_map.get(python_type, "String")
        return gql_type if nullable else f"{gql_type}!"

    # Handle actual types
    if python_type is str:
        gql_type = "String"
    elif python_type is int:
        gql_type = "Int"
    elif python_type is float:
        gql_type = "Float"
    elif python_type is bool:
        gql_type = "Boolean"
    elif python_type is list:
        gql_type = "[String]"
    elif python_type is dict:
        gql_type = "JSON"
    else:
        # Handle typing generics
        origin = getattr(python_type, "__origin__", None)
        args = getattr(python_type, "__args__", ())

        if origin is list:
            item_type = python_type_to_graphql(args[0], nullable=True) if args else "String"
            gql_type = f"[{item_type}]"
        elif origin is dict:
            gql_type = "JSON"
        elif origin is Union:
            # Handle Optional
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                return python_type_to_graphql(non_none_args[0], nullable=True)
            gql_type = "JSON"
        else:
            # Check for Pydantic model
            if isinstance(python_type, type) and issubclass(python_type, BaseModel):
                gql_type = python_type.__name__
            else:
                gql_type = "String"

    return gql_type if nullable else f"{gql_type}!"


class GraphQLSchemaGenerator:
    """Generates GraphQL schema from Foobara commands."""

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        config: Optional[GraphQLConfig] = None,
    ):
        """Initialize the schema generator.

        Args:
            registry: Command registry to use.
            config: GraphQL configuration.
        """
        self.registry = registry or CommandRegistry()
        self.config = config or GraphQLConfig()
        self._type_definitions: Dict[str, str] = {}

    def _command_to_field_name(self, command_class: Type[Command]) -> str:
        """Convert command class name to GraphQL field name."""
        name = command_class.__name__
        # Convert CamelCase to camelCase
        return name[0].lower() + name[1:]

    def _get_operation_type(self, command_class: Type[Command]) -> GraphQLOperationType:
        """Determine if command should be query or mutation."""
        name = command_class.__name__

        # Check custom config
        if name in self.config.field_configs:
            return self.config.field_configs[name].operation_type

        # Check if in query_commands list
        if name in self.config.query_commands:
            return GraphQLOperationType.QUERY

        # Use default
        return self.config.default_operation_type

    def _generate_input_type(self, command_class: Type[Command]) -> Optional[str]:
        """Generate GraphQL input type for command inputs."""
        inputs_type = getattr(command_class, "Inputs", None)
        if not inputs_type:
            return None

        type_name = f"{command_class.__name__}Input"

        if isinstance(inputs_type, type) and issubclass(inputs_type, BaseModel):
            fields = []
            for field_name, field_info in inputs_type.model_fields.items():
                annotation = field_info.annotation
                gql_type = python_type_to_graphql(
                    annotation,
                    nullable=not field_info.is_required()
                )
                description = field_info.description or ""
                if description:
                    fields.append(f'  """{description}"""\n  {field_name}: {gql_type}')
                else:
                    fields.append(f"  {field_name}: {gql_type}")

            if fields:
                self._type_definitions[type_name] = (
                    f"input {type_name} {{\n" + "\n".join(fields) + "\n}"
                )
                return type_name

        return None

    def _generate_output_type(self, command_class: Type[Command]) -> str:
        """Generate GraphQL output type for command result."""
        result_type = getattr(command_class, "Result", None)
        type_name = f"{command_class.__name__}Result"

        if result_type and isinstance(result_type, type) and issubclass(result_type, BaseModel):
            fields = []
            for field_name, field_info in result_type.model_fields.items():
                annotation = field_info.annotation
                gql_type = python_type_to_graphql(annotation)
                description = field_info.description or ""
                if description:
                    fields.append(f'  """{description}"""\n  {field_name}: {gql_type}')
                else:
                    fields.append(f"  {field_name}: {gql_type}")

            if fields:
                self._type_definitions[type_name] = (
                    f"type {type_name} {{\n" + "\n".join(fields) + "\n}"
                )
                return type_name

        return "JSON"

    def _generate_field(self, command_class: Type[Command]) -> str:
        """Generate GraphQL field definition for a command."""
        field_name = self._command_to_field_name(command_class)
        description = getattr(command_class, "__doc__", "") or ""
        description = description.strip()

        input_type = self._generate_input_type(command_class)
        output_type = self._generate_output_type(command_class)

        # Build field definition
        parts = []
        if description:
            parts.append(f'  """{description}"""')

        if input_type:
            parts.append(f"  {field_name}(input: {input_type}!): {output_type}")
        else:
            parts.append(f"  {field_name}: {output_type}")

        return "\n".join(parts)

    def generate_schema(
        self,
        commands: Optional[List[Type[Command]]] = None,
    ) -> str:
        """Generate complete GraphQL schema.

        Args:
            commands: Optional list of commands. Uses all registered if None.

        Returns:
            GraphQL schema definition language (SDL) string.
        """
        self._type_definitions.clear()

        if commands is None:
            commands = self.registry.list_commands()

        # Separate queries and mutations
        queries = []
        mutations = []

        for command_class in commands:
            op_type = self._get_operation_type(command_class)
            field_def = self._generate_field(command_class)

            if op_type == GraphQLOperationType.QUERY:
                queries.append(field_def)
            else:
                mutations.append(field_def)

        # Build schema
        parts = []

        # Add schema description
        parts.append(f'"""{self.config.schema_description}"""')

        # Add custom scalar for JSON
        parts.append("scalar JSON")
        parts.append("")

        # Add type definitions
        for type_def in self._type_definitions.values():
            parts.append(type_def)
            parts.append("")

        # Add error type
        parts.append("""type FoobaraError {
  key: String!
  message: String!
  path: String
  category: String
  context: JSON
}""")
        parts.append("")

        # Add Query type
        if queries:
            parts.append("type Query {")
            parts.extend(queries)
            parts.append("}")
        else:
            # GraphQL requires at least a Query type
            parts.append("type Query {\n  _empty: String\n}")
        parts.append("")

        # Add Mutation type
        if mutations:
            parts.append("type Mutation {")
            parts.extend(mutations)
            parts.append("}")
            parts.append("")

        return "\n".join(parts)


class GraphQLConnector:
    """GraphQL connector for Foobara commands.

    Provides GraphQL execution capabilities for Foobara commands.
    Can be integrated with any GraphQL server (Ariadne, Strawberry, etc.)
    """

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        config: Optional[GraphQLConfig] = None,
    ):
        """Initialize the GraphQL connector.

        Args:
            registry: Command registry to use.
            config: GraphQL configuration.
        """
        self.registry = registry or CommandRegistry()
        self.config = config or GraphQLConfig()
        self.schema_generator = GraphQLSchemaGenerator(registry, config)
        self._resolvers: Dict[str, Callable] = {}

    def get_schema(self) -> str:
        """Get the GraphQL schema SDL."""
        return self.schema_generator.generate_schema()

    def _command_to_field_name(self, command_class: Type[Command]) -> str:
        """Convert command class name to GraphQL field name."""
        name = command_class.__name__
        return name[0].lower() + name[1:]

    def register_resolvers(self) -> Dict[str, Dict[str, Callable]]:
        """Generate resolvers for all registered commands.

        Returns:
            Dictionary mapping operation types to field resolvers.
        """
        queries: Dict[str, Callable] = {}
        mutations: Dict[str, Callable] = {}

        for command_class in self.registry.list_commands():
            field_name = self._command_to_field_name(command_class)
            resolver = self._create_resolver(command_class)
            op_type = self.schema_generator._get_operation_type(command_class)

            if op_type == GraphQLOperationType.QUERY:
                queries[field_name] = resolver
            else:
                mutations[field_name] = resolver

        return {
            "Query": queries,
            "Mutation": mutations,
        }

    def _create_resolver(
        self,
        command_class: Type[Command],
    ) -> Callable:
        """Create a resolver function for a command.

        Args:
            command_class: The command class to create resolver for.

        Returns:
            Resolver function.
        """
        is_async = issubclass(command_class, AsyncCommand)

        if is_async:
            async def async_resolver(
                root: Any,
                info: Any,
                input: Optional[Dict[str, Any]] = None,
            ) -> Dict[str, Any]:
                """Async resolver for command execution."""
                inputs = input or {}
                outcome = await command_class.run_async(**inputs)
                if outcome.is_success():
                    result = outcome.result
                    if isinstance(result, BaseModel):
                        return result.model_dump()
                    return result
                else:
                    # Return errors in GraphQL format
                    return {
                        "errors": [
                            {
                                "key": str(err.symbol) if hasattr(err, "symbol") else "error",
                                "message": str(err),
                                "path": getattr(err, "path", None),
                                "category": getattr(err, "category", None),
                            }
                            for err in (outcome.errors or [])
                        ]
                    }
            return async_resolver
        else:
            def sync_resolver(
                root: Any,
                info: Any,
                input: Optional[Dict[str, Any]] = None,
            ) -> Dict[str, Any]:
                """Sync resolver for command execution."""
                inputs = input or {}
                outcome = command_class.run(**inputs)
                if outcome.is_success():
                    result = outcome.result
                    if isinstance(result, BaseModel):
                        return result.model_dump()
                    return result
                else:
                    return {
                        "errors": [
                            {
                                "key": str(err.symbol) if hasattr(err, "symbol") else "error",
                                "message": str(err),
                                "path": getattr(err, "path", None),
                                "category": getattr(err, "category", None),
                            }
                            for err in (outcome.errors or [])
                        ]
                    }
            return sync_resolver

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query.

        This is a simple executor for basic use cases. For production,
        consider using a full GraphQL library like Ariadne or Strawberry.

        Args:
            query: GraphQL query string.
            variables: Query variables.
            operation_name: Name of operation to execute.
            context: Execution context.

        Returns:
            GraphQL result dictionary.
        """
        import re

        variables = variables or {}
        context = context or {}

        # Simple query parser (for basic cases)
        # For production, use graphql-core or similar
        try:
            # Extract operation type and fields
            mutation_match = re.search(
                r"mutation\s+\w*\s*(?:\([^)]*\))?\s*\{([^}]+)\}",
                query,
                re.DOTALL
            )
            query_match = re.search(
                r"query\s+\w*\s*(?:\([^)]*\))?\s*\{([^}]+)\}",
                query,
                re.DOTALL
            )

            if not mutation_match and not query_match:
                # Try bare query
                query_match = re.search(r"\{([^}]+)\}", query, re.DOTALL)

            if mutation_match:
                fields_str = mutation_match.group(1)
                operation_type = "Mutation"
            elif query_match:
                fields_str = query_match.group(1)
                operation_type = "Query"
            else:
                return {"errors": [{"message": "Invalid query syntax"}]}

            # Extract field name
            field_match = re.search(r"(\w+)\s*(?:\(|{|$)", fields_str.strip())
            if not field_match:
                return {"errors": [{"message": "No field found in query"}]}

            field_name = field_match.group(1)

            # Get resolver
            resolvers = self.register_resolvers()
            resolver = resolvers.get(operation_type, {}).get(field_name)

            if not resolver:
                return {"errors": [{"message": f"Unknown field: {field_name}"}]}

            # Extract input from variables or inline
            input_data = variables.get("input", {})

            # Execute resolver
            if inspect.iscoroutinefunction(resolver):
                result = await resolver(None, context, input_data)
            else:
                result = resolver(None, context, input_data)

            return {"data": {field_name: result}}

        except Exception as e:
            return {"errors": [{"message": str(e)}]}


def create_ariadne_schema(
    registry: Optional[CommandRegistry] = None,
    config: Optional[GraphQLConfig] = None,
) -> tuple:
    """Create Ariadne-compatible schema and resolvers.

    Args:
        registry: Command registry.
        config: GraphQL configuration.

    Returns:
        Tuple of (type_defs, resolvers) for Ariadne.

    Example:
        from ariadne import make_executable_schema
        from ariadne.asgi import GraphQL

        type_defs, resolvers = create_ariadne_schema(registry)
        schema = make_executable_schema(type_defs, resolvers)
        app = GraphQL(schema)
    """
    connector = GraphQLConnector(registry, config)
    type_defs = connector.get_schema()
    resolvers = connector.register_resolvers()

    return type_defs, resolvers


def create_strawberry_types(
    registry: Optional[CommandRegistry] = None,
    config: Optional[GraphQLConfig] = None,
) -> Dict[str, Any]:
    """Create Strawberry-compatible type definitions.

    Args:
        registry: Command registry.
        config: GraphQL configuration.

    Returns:
        Dictionary with Query and Mutation classes for Strawberry.

    Note:
        This returns a dictionary with type definitions that can be
        used to create Strawberry schema. The actual Strawberry decorators
        need to be applied by the user.
    """
    connector = GraphQLConnector(registry, config)
    resolvers = connector.register_resolvers()

    return {
        "query_resolvers": resolvers.get("Query", {}),
        "mutation_resolvers": resolvers.get("Mutation", {}),
        "schema_sdl": connector.get_schema(),
    }


# Convenience functions
def generate_graphql_schema(
    commands: Optional[List[Type[Command]]] = None,
    registry: Optional[CommandRegistry] = None,
    config: Optional[GraphQLConfig] = None,
) -> str:
    """Generate GraphQL schema SDL.

    Args:
        commands: Optional list of commands.
        registry: Command registry.
        config: GraphQL configuration.

    Returns:
        GraphQL schema definition language string.
    """
    generator = GraphQLSchemaGenerator(registry, config)
    return generator.generate_schema(commands)
