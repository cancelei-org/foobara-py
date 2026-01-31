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
    _cached_full_symbol: ClassVar[Optional[str]] = None

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
        Get command symbol (snake_case full name) with lazy computation and caching.

        The symbol is computed once and cached for subsequent calls,
        improving performance for repeated access.

        Returns:
            Snake case identifier (e.g., "my_org_users_create_user")
        """
        # Return cached value if available
        if cls._cached_full_symbol is not None:
            return cls._cached_full_symbol

        # Compute and cache the symbol
        cls._cached_full_symbol = cls.full_name().replace("::", "_").lower()

        return cls._cached_full_symbol

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
