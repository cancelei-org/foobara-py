"""
NamingConcern - Command naming and identification.

Handles:
- Fully qualified names (Organization::Domain::Command)
- Command symbols (snake_case identifiers)
- Description extraction

Pattern: Ruby Foobara's Namespace concern
"""

from typing import ClassVar, Optional


class NamingConcern:
    """Mixin for command naming and identification."""

    # Class-level configuration
    _domain: ClassVar[Optional[str]] = None
    _organization: ClassVar[Optional[str]] = None
    _description: ClassVar[Optional[str]] = None

    @classmethod
    def full_name(cls) -> str:
        """
        Get fully qualified command name.

        Format: Organization::Domain::Command

        Returns:
            Fully qualified name (e.g., "MyOrg::Users::CreateUser")
        """
        parts = []
        if cls._organization:
            parts.append(cls._organization)
        if cls._domain:
            parts.append(cls._domain)
        parts.append(cls.__name__)
        return "::".join(parts)

    @classmethod
    def full_command_symbol(cls) -> str:
        """
        Get command symbol (snake_case full name).

        Returns:
            Snake case identifier (e.g., "my_org_users_create_user")
        """
        return cls.full_name().replace("::", "_").lower()

    @classmethod
    def description(cls) -> str:
        """
        Get command description.

        Returns description from:
        1. _description class attribute (if set)
        2. Class docstring (if present)
        3. Empty string (fallback)

        Returns:
            Command description string
        """
        if cls._description:
            return cls._description
        return cls.__doc__ or ""
