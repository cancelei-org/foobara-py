"""
Authorization Rules.

Provides rule-based authorization for commands.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Type

from foobara_py.auth.authenticator import AuthContext


class AllowedRule(ABC):
    """
    Base class for authorization rules.

    Subclass to implement custom authorization logic.

    Usage:
        class AdminOnly(AllowedRule):
            def allowed(self, context: AuthContext, command: Type) -> bool:
                return context.has_role("admin")
    """

    @abstractmethod
    def allowed(self, context: AuthContext, command: Type) -> bool:
        """
        Check if action is allowed.

        Args:
            context: Authentication context
            command: Command class being executed

        Returns:
            True if allowed, False otherwise
        """
        pass


class RoleRequired(AllowedRule):
    """
    Require specific role(s).

    Usage:
        # Require admin role
        RoleRequired("admin")

        # Require any of multiple roles
        RoleRequired("admin", "moderator")
    """

    def __init__(self, *roles: str):
        """
        Initialize role requirement.

        Args:
            *roles: Required roles (any one is sufficient)
        """
        self.roles = set(roles)

    def allowed(self, context: AuthContext, command: Type) -> bool:
        """Check if context has any of the required roles."""
        return bool(set(context.roles) & self.roles)


class AllRolesRequired(AllowedRule):
    """
    Require all specified roles.

    Usage:
        # Require both admin AND moderator roles
        AllRolesRequired("admin", "moderator")
    """

    def __init__(self, *roles: str):
        """
        Initialize all-roles requirement.

        Args:
            *roles: Required roles (all are necessary)
        """
        self.roles = set(roles)

    def allowed(self, context: AuthContext, command: Type) -> bool:
        """Check if context has all of the required roles."""
        return self.roles.issubset(set(context.roles))


class PermissionRequired(AllowedRule):
    """
    Require specific permission(s).

    Usage:
        # Require write permission
        PermissionRequired("write")

        # Require any of multiple permissions
        PermissionRequired("write", "admin")
    """

    def __init__(self, *permissions: str):
        """
        Initialize permission requirement.

        Args:
            *permissions: Required permissions (any one is sufficient)
        """
        self.permissions = set(permissions)

    def allowed(self, context: AuthContext, command: Type) -> bool:
        """Check if context has any of the required permissions."""
        return bool(set(context.permissions) & self.permissions)


class AllPermissionsRequired(AllowedRule):
    """
    Require all specified permissions.

    Usage:
        # Require both read AND write permissions
        AllPermissionsRequired("read", "write")
    """

    def __init__(self, *permissions: str):
        """
        Initialize all-permissions requirement.

        Args:
            *permissions: Required permissions (all are necessary)
        """
        self.permissions = set(permissions)

    def allowed(self, context: AuthContext, command: Type) -> bool:
        """Check if context has all of the required permissions."""
        return self.permissions.issubset(set(context.permissions))


class Authenticated(AllowedRule):
    """
    Require any authenticated user.

    Usage:
        Authenticated()
    """

    def allowed(self, context: AuthContext, command: Type) -> bool:
        """Check if context has a user ID (is authenticated)."""
        return context.user_id is not None


class CustomRule(AllowedRule):
    """
    Custom authorization rule using a function.

    Usage:
        def check_access(context, command):
            return context.metadata.get("tenant_id") == "acme"

        CustomRule(check_access)
    """

    def __init__(self, check: Callable[[AuthContext, Type], bool]):
        """
        Initialize custom rule.

        Args:
            check: Function to check authorization
        """
        self.check = check

    def allowed(self, context: AuthContext, command: Type) -> bool:
        """Check authorization using custom function."""
        return self.check(context, command)


class RuleRegistry:
    """
    Registry of authorization rules per command.

    Manages which rules apply to which commands.

    Usage:
        registry = RuleRegistry()

        # Require admin role for DeleteUser command
        registry.register(DeleteUser, RoleRequired("admin"))

        # Require authentication for any command
        registry.set_default(Authenticated())

        # Check if allowed
        context = AuthContext(user_id=42, roles=["admin"])
        if registry.check(context, DeleteUser):
            print("Allowed to delete user")
    """

    def __init__(self):
        self._rules: dict[Type, List[AllowedRule]] = {}
        self._default_rules: List[AllowedRule] = []

    def register(self, command: Type, *rules: AllowedRule) -> "RuleRegistry":
        """
        Register rules for a command.

        Args:
            command: Command class
            *rules: Rules to apply to this command

        Returns:
            Self for chaining
        """
        if command not in self._rules:
            self._rules[command] = []
        self._rules[command].extend(rules)
        return self

    def set_default(self, *rules: AllowedRule) -> "RuleRegistry":
        """
        Set default rules that apply to all commands.

        Args:
            *rules: Default rules

        Returns:
            Self for chaining
        """
        self._default_rules.extend(rules)
        return self

    def check(self, context: AuthContext, command: Type) -> bool:
        """
        Check if action is allowed.

        All rules must pass (AND logic).

        Args:
            context: Authentication context
            command: Command class being executed

        Returns:
            True if all rules allow, False otherwise
        """
        # Check command-specific rules
        command_rules = self._rules.get(command, [])

        # Check default rules
        all_rules = self._default_rules + command_rules

        # If no rules, allow by default
        if not all_rules:
            return True

        # All rules must pass
        return all(rule.allowed(context, command) for rule in all_rules)

    def get_rules(self, command: Type) -> List[AllowedRule]:
        """
        Get all rules for a command (including defaults).

        Args:
            command: Command class

        Returns:
            List of rules
        """
        return self._default_rules + self._rules.get(command, [])

    def clear(self, command: Optional[Type] = None) -> None:
        """
        Clear rules.

        Args:
            command: If specified, clear rules for this command only.
                    If None, clear all rules including defaults.
        """
        if command is None:
            self._rules.clear()
            self._default_rules.clear()
        else:
            self._rules.pop(command, None)


# Global rule registry
_global_registry = RuleRegistry()


def get_global_registry() -> RuleRegistry:
    """Get the global rule registry."""
    return _global_registry


def reset_global_registry() -> None:
    """Reset the global rule registry."""
    global _global_registry
    _global_registry = RuleRegistry()
