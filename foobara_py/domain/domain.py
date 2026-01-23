"""
Enhanced Domain and Organization system with full Ruby Foobara parity.

Features:
- Domain dependencies with validation
- Cross-domain call validation
- Global domain support
- Automatic command namespace discovery
- Type registry per domain
- Manifest generation
"""

import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Type
from weakref import WeakValueDictionary

from pydantic import BaseModel

if TYPE_CHECKING:
    from foobara_py.core.command import Command


class DomainDependencyError(Exception):
    """Raised when a domain dependency violation occurs"""

    pass


class GlobalDomain:
    """
    Global domain for commands without explicit domain.

    Similar to Ruby Foobara's GlobalDomain.
    All domains can call commands from GlobalDomain.
    """

    name = "Global"
    organization = None

    @classmethod
    def full_name(cls) -> str:
        return "Global"


class Domain:
    """
    Domain for grouping related commands and types.

    Features:
    - Command registration with namespace
    - Type registration
    - Domain dependencies with validation
    - Cross-domain call checking
    - Manifest generation

    Usage:
        users_domain = Domain("Users", organization="MyApp")
        users_domain.depends_on("Auth", "Billing")

        @users_domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                ...

        # Validates cross-domain calls
        if users_domain.can_call_from("Auth"):
            # OK - Auth is in depends_on
            pass
    """

    # Global registry of all domains
    _registry: Dict[str, "Domain"] = {}
    _lock = threading.Lock()

    # Track cross-domain calls for observability
    # Format: {(source_domain, target_domain): count}
    _cross_domain_calls: Dict[tuple[str, str], int] = {}

    __slots__ = ("name", "organization", "_commands", "_types", "_dependencies", "_command_classes")

    def __init__(self, name: str, organization: str = None):
        self.name = name
        self.organization = organization
        self._commands: Dict[str, Type["Command"]] = {}
        self._types: Dict[str, Type[BaseModel]] = {}
        self._dependencies: Set[str] = set()
        self._command_classes: WeakValueDictionary = WeakValueDictionary()

        # Register in global registry
        with Domain._lock:
            Domain._registry[self.full_name()] = self

    def full_name(self) -> str:
        """Get fully qualified domain name"""
        if self.organization:
            return f"{self.organization}::{self.name}"
        return self.name

    # ==================== Dependencies ====================

    def depends_on(self, *domains: str) -> "Domain":
        """
        Declare domain dependencies.

        Commands in this domain can call subcommands from dependent domains.

        Usage:
            users = Domain("Users")
            users.depends_on("Auth", "Billing")

        Raises:
            DomainDependencyError: If adding dependency would create a circular dependency
        """
        for domain in domains:
            # Check for circular dependencies before adding
            if self._would_create_cycle(domain):
                raise DomainDependencyError(
                    f"Adding dependency '{domain}' to '{self.name}' would create a circular dependency"
                )
            self._dependencies.add(domain)
        return self

    def _would_create_cycle(self, new_dependency: str) -> bool:
        """
        Check if adding new_dependency would create a circular dependency.

        Uses DFS to detect cycles in the dependency graph.

        Returns:
            True if adding the dependency would create a cycle, False otherwise
        """
        # If adding self as dependency, immediate cycle
        if new_dependency == self.name:
            return True

        # Get the domain object for the new dependency
        with Domain._lock:
            target_domain = Domain._registry.get(new_dependency)

        if not target_domain:
            # Domain doesn't exist yet, no cycle possible
            return False

        # Check if target domain (directly or transitively) depends on us
        visited = set()

        def has_path_to(from_domain_name: str, to_domain_name: str) -> bool:
            """Check if there's a dependency path from from_domain to to_domain"""
            if from_domain_name in visited:
                return False
            visited.add(from_domain_name)

            with Domain._lock:
                from_domain = Domain._registry.get(from_domain_name)

            if not from_domain:
                return False

            # Direct dependency?
            if to_domain_name in from_domain._dependencies:
                return True

            # Transitive dependency?
            for dep in from_domain._dependencies:
                if has_path_to(dep, to_domain_name):
                    return True

            return False

        # Check if new_dependency has a path back to us
        return has_path_to(new_dependency, self.name)

    def can_call_from(self, other_domain: str) -> bool:
        """
        Check if commands in other_domain can be called from this domain.

        Rules:
        1. Can always call commands in same domain
        2. Can always call commands in GlobalDomain
        3. Can call if other_domain is in dependencies
        """
        if other_domain == self.name:
            return True
        if other_domain == "Global":
            return True
        if other_domain in self._dependencies:
            return True
        return False

    def validate_subcommand_call(self, command_class: Type["Command"], target_domain: str) -> None:
        """
        Validate that calling target domain is allowed.

        Raises DomainDependencyError if not allowed.
        """
        if not self.can_call_from(target_domain):
            raise DomainDependencyError(
                f"Domain '{self.name}' cannot call commands from '{target_domain}'. "
                f"Add '{target_domain}' to depends_on or use GlobalDomain."
            )

    @classmethod
    def track_cross_domain_call(cls, source_domain: str, target_domain: str) -> None:
        """
        Track a cross-domain call for observability.

        Args:
            source_domain: The domain making the call
            target_domain: The domain being called
        """
        if source_domain == target_domain:
            return  # Not a cross-domain call

        key = (source_domain, target_domain)
        with cls._lock:
            cls._cross_domain_calls[key] = cls._cross_domain_calls.get(key, 0) + 1

    @classmethod
    def get_cross_domain_call_stats(cls) -> Dict[tuple[str, str], int]:
        """
        Get statistics on cross-domain calls.

        Returns:
            Dictionary mapping (source_domain, target_domain) to call count
        """
        with cls._lock:
            return dict(cls._cross_domain_calls)

    @classmethod
    def reset_cross_domain_call_stats(cls) -> None:
        """Reset cross-domain call tracking statistics"""
        with cls._lock:
            cls._cross_domain_calls.clear()

    # ==================== Command Registration ====================

    def command(self, cls: Type["Command"]) -> Type["Command"]:
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

    def register_command(self, command_class: Type["Command"]) -> None:
        """Explicitly register a command"""
        command_class._domain = self.name
        command_class._organization = self.organization
        self._commands[command_class.__name__] = command_class

    def get_command(self, name: str) -> Optional[Type["Command"]]:
        """Get command by simple name"""
        return self._commands.get(name)

    def list_commands(self) -> List[Type["Command"]]:
        """List all commands in domain"""
        return list(self._commands.values())

    def command_names(self) -> List[str]:
        """Get all command names"""
        return list(self._commands.keys())

    # ==================== Type Registration ====================

    def type(self, name: str = None) -> Callable:
        """
        Decorator to register type in this domain.

        Usage:
            @domain.type()
            class UserModel(BaseModel):
                ...
        """

        def decorator(cls: Type[BaseModel]) -> Type[BaseModel]:
            type_name = name or cls.__name__
            self._types[type_name] = cls
            return cls

        return decorator

    def register_type(self, name: str, model: Type[BaseModel]) -> None:
        """Explicitly register a type"""
        self._types[name] = model

    def get_type(self, name: str) -> Optional[Type[BaseModel]]:
        """Get type by name"""
        return self._types.get(name)

    def list_types(self) -> List[Type[BaseModel]]:
        """List all types in domain"""
        return list(self._types.values())

    # ==================== Manifest ====================

    def manifest(self) -> dict:
        """Generate domain manifest"""
        return {
            "name": self.name,
            "organization": self.organization,
            "full_name": self.full_name(),
            "depends_on": list(self._dependencies),
            "commands": {name: cmd.manifest() for name, cmd in self._commands.items()},
            "types": {name: model.model_json_schema() for name, model in self._types.items()},
        }

    # ==================== Class Methods ====================

    @classmethod
    def get(cls, name: str) -> Optional["Domain"]:
        """Get domain by full name"""
        with cls._lock:
            return cls._registry.get(name)

    @classmethod
    def all(cls) -> List["Domain"]:
        """List all registered domains"""
        with cls._lock:
            return list(cls._registry.values())

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered domains (for testing)"""
        with cls._lock:
            cls._registry.clear()

    @classmethod
    def find_domain_for_command(cls, command_class: Type["Command"]) -> Optional["Domain"]:
        """Find the domain containing a command class"""
        domain_name = getattr(command_class, "_domain", None)
        org_name = getattr(command_class, "_organization", None)

        if domain_name:
            full_name = f"{org_name}::{domain_name}" if org_name else domain_name
            return cls.get(full_name)
        return None


class Organization:
    """
    Organization for grouping domains.

    Features:
    - Domain creation and management
    - Organization-level manifest
    - Cross-domain dependency validation

    Usage:
        org = Organization("MyCompany")
        users = org.domain("Users")
        billing = org.domain("Billing")

        users.depends_on("Billing")
    """

    _registry: Dict[str, "Organization"] = {}
    _lock = threading.Lock()

    __slots__ = ("name", "_domains")

    def __init__(self, name: str):
        self.name = name
        self._domains: Dict[str, Domain] = {}

        # Register in global registry
        with Organization._lock:
            Organization._registry[name] = self

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

    def domain_names(self) -> List[str]:
        """Get all domain names"""
        return list(self._domains.keys())

    def manifest(self) -> dict:
        """Generate organization manifest"""
        return {
            "name": self.name,
            "domains": {name: domain.manifest() for name, domain in self._domains.items()},
        }

    @classmethod
    def get(cls, name: str) -> Optional["Organization"]:
        """Get organization by name"""
        with cls._lock:
            return cls._registry.get(name)

    @classmethod
    def all(cls) -> List["Organization"]:
        """List all registered organizations"""
        with cls._lock:
            return list(cls._registry.values())

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered organizations (for testing)"""
        with cls._lock:
            cls._registry.clear()


# ==================== Namespace Utilities ====================


def foobara_domain(name: str = None, organization: str = None) -> Callable:
    """
    Decorator to convert a module or class into a domain.

    Usage:
        @foobara_domain(organization="MyApp")
        class Users:
            pass

        # Now Users acts as a domain
        @Users.command
        class CreateUser(Command[...]):
            ...
    """

    def decorator(cls):
        domain_name = name or cls.__name__
        domain = Domain(domain_name, organization=organization)

        # Add domain methods to class
        cls._domain_instance = domain
        cls.command = domain.command
        cls.type = domain.type
        cls.register_command = domain.register_command
        cls.register_type = domain.register_type
        cls.get_command = domain.get_command
        cls.list_commands = domain.list_commands
        cls.depends_on = domain.depends_on
        cls.manifest = domain.manifest
        cls.full_name = domain.full_name

        return cls

    return decorator


def foobara_organization(name: str = None) -> Callable:
    """
    Decorator to convert a module or class into an organization.

    Usage:
        @foobara_organization()
        class MyCompany:
            pass

        # Now MyCompany acts as an organization
        users = MyCompany.domain("Users")
    """

    def decorator(cls):
        org_name = name or cls.__name__
        org = Organization(org_name)

        cls._organization_instance = org
        cls.domain = org.domain
        cls.get_domain = org.get_domain
        cls.list_domains = org.list_domains
        cls.manifest = org.manifest

        return cls

    return decorator


# ==================== Convenience Functions ====================


def create_domain(name: str, organization: str = None) -> Domain:
    """Create a new domain"""
    return Domain(name, organization=organization)


def get_domain(name: str) -> Optional[Domain]:
    """Get domain by name"""
    return Domain.get(name)


def get_organization(name: str) -> Optional[Organization]:
    """Get organization by name"""
    return Organization.get(name)


def all_domains() -> List[Domain]:
    """Get all registered domains"""
    return Domain.all()


def all_organizations() -> List[Organization]:
    """Get all registered organizations"""
    return Organization.all()
