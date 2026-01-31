"""
Command manifest for Foobara introspection.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from pydantic import Field

from foobara_py.manifest.base import BaseManifest

if TYPE_CHECKING:
    from foobara_py.core.command import Command
    from foobara_py.manifest.error_manifest import ErrorManifest


class CommandManifest(BaseManifest):
    """
    Manifest for a Foobara command.

    Captures all metadata about a command including:
    - Name and full qualified name
    - Input schema (JSON Schema)
    - Result schema (JSON Schema)
    - Possible errors
    - Description and documentation
    """

    name: str = Field(description="Command class name")
    full_name: str = Field(description="Full qualified name (Organization::Domain::Command)")
    description: Optional[str] = Field(default=None, description="Command description")

    # Schemas
    inputs_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema for command inputs"
    )
    result_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema for command result"
    )

    # Metadata
    domain: Optional[str] = Field(default=None, description="Domain name")
    organization: Optional[str] = Field(default=None, description="Organization name")

    # Errors
    possible_errors: List[str] = Field(
        default_factory=list, description="List of possible error types"
    )

    # Additional metadata
    is_async: bool = Field(default=False, description="Whether command is async")
    tags: List[str] = Field(default_factory=list, description="Command tags")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "full_name": self.full_name,
            "description": self.description,
            "inputs_schema": self.inputs_schema,
            "result_schema": self.result_schema,
            "domain": self.domain,
            "organization": self.organization,
            "possible_errors": self.possible_errors,
            "is_async": self.is_async,
            "tags": self.tags,
        }

    @classmethod
    def from_command(cls, command_class: Type["Command"]) -> "CommandManifest":
        """
        Create manifest from a command class.

        Args:
            command_class: The command class to create manifest for.

        Returns:
            CommandManifest instance.
        """
        import inspect

        # Get name
        name = command_class.__name__

        # Build full name
        parts = []
        if hasattr(command_class, "_organization") and command_class._organization:
            parts.append(command_class._organization)
        if hasattr(command_class, "_domain") and command_class._domain:
            parts.append(command_class._domain)
        parts.append(name)
        full_name = "::".join(parts)

        # Get description from docstring
        description = inspect.getdoc(command_class)

        # Get input schema
        inputs_schema = None
        # Try inputs_type() method first (used by Command generic classes)
        if hasattr(command_class, "inputs_type"):
            try:
                inputs_type = command_class.inputs_type()
                if inputs_type is not None:
                    inputs_schema = inputs_type.model_json_schema()
            except (TypeError, AttributeError):
                pass
        # Fallback to Inputs attribute if present
        if (
            inputs_schema is None
            and hasattr(command_class, "Inputs")
            and command_class.Inputs is not None
        ):
            try:
                inputs_schema = command_class.Inputs.model_json_schema()
            except Exception:
                pass

        # Get result schema (from type hints if available)
        result_schema = None
        if hasattr(command_class, "__orig_bases__"):
            for base in command_class.__orig_bases__:
                if hasattr(base, "__args__") and len(base.__args__) > 1:
                    result_type = base.__args__[1] if len(base.__args__) > 1 else None
                    if result_type and hasattr(result_type, "model_json_schema"):
                        try:
                            result_schema = result_type.model_json_schema()
                        except Exception:
                            pass
                    break

        # Get domain and organization
        domain = getattr(command_class, "_domain", None)
        organization = getattr(command_class, "_organization", None)

        # Get possible errors
        possible_errors = []
        if hasattr(command_class, "_possible_errors"):
            possible_errors = [e.__name__ for e in command_class._possible_errors]

        # Check if async
        is_async = inspect.iscoroutinefunction(getattr(command_class, "execute", None))

        # Get tags
        tags = getattr(command_class, "_tags", [])

        return cls(
            name=name,
            full_name=full_name,
            description=description,
            inputs_schema=inputs_schema,
            result_schema=result_schema,
            domain=domain,
            organization=organization,
            possible_errors=possible_errors,
            is_async=is_async,
            tags=tags,
        )

    def domain_reference(self) -> Optional[str]:
        """
        Get the domain reference for this command.

        Returns:
            Domain reference string (e.g., "Organization::Domain") or None.
        """
        if self.domain:
            if self.organization:
                return f"{self.organization}::{self.domain}"
            return self.domain
        return None
