"""
Command and Type Registry for foobara-py

Provides registration and discovery of commands, similar to Foobara's
domain/organization namespace system.
"""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from foobara_py.core.command import Command


class CommandRegistry:
    """
    Registry for commands with namespace support.

    Provides:
    - Command registration by name
    - Discovery by domain/organization
    - Manifest generation for MCP tools/list

    Example:
        registry = CommandRegistry()
        registry.register(CreateUser)
        registry.register(UpdateUser)

        # Get command by name
        cmd_class = registry.get("Users::CreateUser")

        # List all as MCP tools
        tools = registry.list_tools()
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._commands: Dict[str, Type[Command]] = {}
        self._domains: Dict[str, "DomainRegistry"] = {}

    def register(self, command_class: Type[Command]) -> None:
        """Register a command class"""
        name = command_class.full_name()
        self._commands[name] = command_class

        # Also register in domain if set
        domain = command_class._domain
        if domain:
            if domain not in self._domains:
                self._domains[domain] = DomainRegistry(domain)
            self._domains[domain].register(command_class)

    def get(self, name: str) -> Optional[Type[Command]]:
        """Get command by full name"""
        return self._commands.get(name)

    def execute(self, name: str, inputs: dict) -> Any:
        """Execute command by name with inputs"""
        cmd_class = self.get(name)
        if not cmd_class:
            raise KeyError(f"Command not found: {name}")
        return cmd_class.run(**inputs)

    def list_commands(self) -> List[Type[Command]]:
        """List all registered commands"""
        return list(self._commands.values())

    def list_tools(self) -> List[dict]:
        """
        List commands in MCP tools format.

        Returns list of tool definitions with:
        - name: Full command name
        - description: Command description
        - inputSchema: JSON Schema for inputs
        """
        return [
            {
                "name": cmd.full_name(),
                "description": cmd.description(),
                "inputSchema": cmd.inputs_schema(),
            }
            for cmd in self._commands.values()
        ]

    def get_manifest(self) -> dict:
        """Generate full registry manifest"""
        return {
            "registry": self.name,
            "domains": {name: domain.get_manifest() for name, domain in self._domains.items()},
            "commands": {name: cmd.manifest() for name, cmd in self._commands.items()},
        }


class DomainRegistry:
    """
    Registry for a specific domain.

    Corresponds to Foobara's Domain concept for grouping
    related commands and types.
    """

    def __init__(self, name: str, organization: str = None):
        self.name = name
        self.organization = organization
        self._commands: Dict[str, Type[Command]] = {}
        self._types: Dict[str, Type[BaseModel]] = {}

    def register(self, command_class: Type[Command]) -> None:
        """Register command in this domain"""
        self._commands[command_class.__name__] = command_class

    def register_type(self, name: str, model: Type[BaseModel]) -> None:
        """Register a type in this domain"""
        self._types[name] = model

    def get_command(self, name: str) -> Optional[Type[Command]]:
        """Get command by simple name"""
        return self._commands.get(name)

    def list_commands(self) -> List[Type[Command]]:
        """List all commands in domain"""
        return list(self._commands.values())

    def get_manifest(self) -> dict:
        """Generate domain manifest"""
        return {
            "name": self.name,
            "organization": self.organization,
            "commands": {name: cmd.manifest() for name, cmd in self._commands.items()},
            "types": {name: model.model_json_schema() for name, model in self._types.items()},
        }


class TypeRegistry:
    """
    Registry for custom types.

    Tracks Pydantic models and their JSON schemas
    for manifest generation and type resolution.
    """

    def __init__(self):
        self._types: Dict[str, Type[BaseModel]] = {}
        self._schemas: Dict[str, dict] = {}

    def register(self, name: str, model: Type[BaseModel]) -> None:
        """Register a Pydantic model"""
        self._types[name] = model
        self._schemas[name] = model.model_json_schema()

    def get(self, name: str) -> Optional[Type[BaseModel]]:
        """Get model by name"""
        return self._types.get(name)

    def get_schema(self, name: str) -> Optional[dict]:
        """Get JSON schema by name"""
        return self._schemas.get(name)

    def list_types(self) -> List[str]:
        """List all registered type names"""
        return list(self._types.keys())

    def get_all_schemas(self) -> Dict[str, dict]:
        """Get all schemas"""
        return self._schemas.copy()


# Global default registry
_default_registry = CommandRegistry("global")


def get_default_registry() -> CommandRegistry:
    """Get the default global registry"""
    return _default_registry


def register(command_class: Type[Command]) -> Type[Command]:
    """
    Decorator to register command in default registry.

    Usage:
        @register
        class CreateUser(Command[CreateUserInputs, User]):
            ...
    """
    _default_registry.register(command_class)
    return command_class
