"""
⚠️  DEPRECATED V1 IMPLEMENTATION ⚠️

This file is deprecated as of v0.3.0 and will be removed in v0.4.0.

DO NOT USE THIS FILE. Use the current implementation instead:
    from foobara_py import Domain, Organization

---

Domain and Organization support for foobara-py (LEGACY V1)

Provides namespace organization for commands and types,
similar to Foobara's Domain and Organization modules.
"""

import warnings

warnings.warn(
    "foobara_py._deprecated.domain.domain_v1 is deprecated and will be removed in v0.4.0. "
    "Use 'from foobara_py import Domain, Organization' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from typing import Dict, List, Optional, Type

from pydantic import BaseModel

from foobara_py.core.command import Command
from foobara_py.core.registry import CommandRegistry, TypeRegistry


class Domain:
    """
    Domain for grouping related commands and types.

    Corresponds to Foobara's Domain concept:
    - Groups related commands
    - Contains domain-specific types
    - Provides namespace for command names

    Usage:
        users_domain = Domain("Users", organization="MyApp")

        @users_domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                ...

        # Commands are registered as "MyApp::Users::CreateUser"
    """

    _registry: Dict[str, "Domain"] = {}

    def __init__(self, name: str, organization: str = None):
        self.name = name
        self.organization = organization
        self._commands: Dict[str, Type[Command]] = {}
        self._types: Dict[str, Type[BaseModel]] = {}

        # Register in global domain registry
        full_name = f"{organization}::{name}" if organization else name
        Domain._registry[full_name] = self

    @classmethod
    def get(cls, name: str) -> Optional["Domain"]:
        """Get domain by name"""
        return cls._registry.get(name)

    @classmethod
    def all(cls) -> List["Domain"]:
        """List all registered domains"""
        return list(cls._registry.values())

    def full_name(self) -> str:
        """Get fully qualified domain name"""
        if self.organization:
            return f"{self.organization}::{self.name}"
        return self.name

    def command(self, cls: Type[Command]) -> Type[Command]:
        """
        Decorator to register command in this domain.

        Usage:
            @domain.command
            class CreateUser(Command[...]):
                ...
        """
        cls._domain = self.name
        cls._organization = self.organization
        self._commands[cls.__name__] = cls
        return cls

    def type(self, name: str = None):
        """
        Decorator to register type in this domain.

        Usage:
            @domain.type()
            class UserModel(BaseModel):
                ...
        """

        def decorator(cls: Type[BaseModel]):
            type_name = name or cls.__name__
            self._types[type_name] = cls
            return cls

        return decorator

    def register_command(self, command_class: Type[Command]) -> None:
        """Explicitly register a command"""
        command_class._domain = self.name
        command_class._organization = self.organization
        self._commands[command_class.__name__] = command_class

    def register_type(self, name: str, model: Type[BaseModel]) -> None:
        """Explicitly register a type"""
        self._types[name] = model

    def get_command(self, name: str) -> Optional[Type[Command]]:
        """Get command by simple name"""
        return self._commands.get(name)

    def get_type(self, name: str) -> Optional[Type[BaseModel]]:
        """Get type by name"""
        return self._types.get(name)

    def list_commands(self) -> List[Type[Command]]:
        """List all commands in domain"""
        return list(self._commands.values())

    def list_types(self) -> List[Type[BaseModel]]:
        """List all types in domain"""
        return list(self._types.values())

    def manifest(self) -> dict:
        """Generate domain manifest"""
        return {
            "name": self.name,
            "organization": self.organization,
            "full_name": self.full_name(),
            "commands": {name: cmd.manifest() for name, cmd in self._commands.items()},
            "types": {name: model.model_json_schema() for name, model in self._types.items()},
        }


class Organization:
    """
    Organization for grouping domains.

    Corresponds to Foobara's Organization concept:
    - Groups related domains
    - Provides top-level namespace

    Usage:
        my_org = Organization("MyCompany")
        users_domain = my_org.domain("Users")
        billing_domain = my_org.domain("Billing")
    """

    _registry: Dict[str, "Organization"] = {}

    def __init__(self, name: str):
        self.name = name
        self._domains: Dict[str, Domain] = {}

        # Register in global registry
        Organization._registry[name] = self

    @classmethod
    def get(cls, name: str) -> Optional["Organization"]:
        """Get organization by name"""
        return cls._registry.get(name)

    @classmethod
    def all(cls) -> List["Organization"]:
        """List all registered organizations"""
        return list(cls._registry.values())

    def domain(self, name: str) -> Domain:
        """
        Create or get a domain in this organization.

        Usage:
            org = Organization("MyCompany")
            users = org.domain("Users")
        """
        if name not in self._domains:
            self._domains[name] = Domain(name, organization=self.name)
        return self._domains[name]

    def get_domain(self, name: str) -> Optional[Domain]:
        """Get domain by name"""
        return self._domains.get(name)

    def list_domains(self) -> List[Domain]:
        """List all domains in organization"""
        return list(self._domains.values())

    def manifest(self) -> dict:
        """Generate organization manifest"""
        return {
            "name": self.name,
            "domains": {name: domain.manifest() for name, domain in self._domains.items()},
        }


# Convenience function for creating domains
def create_domain(name: str, organization: str = None) -> Domain:
    """
    Create a new domain, optionally in an organization.

    Usage:
        users = create_domain("Users", organization="MyApp")
    """
    return Domain(name, organization=organization)
