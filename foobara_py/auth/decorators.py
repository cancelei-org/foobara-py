"""
Authentication and Authorization Decorators.

Provides convenient decorators for securing commands.
"""

from functools import wraps
from typing import List, Type

from foobara_py.auth.rules import (
    AllowedRule,
    AllPermissionsRequired,
    AllRolesRequired,
    Authenticated,
    PermissionRequired,
    RoleRequired,
    get_global_registry,
)


def requires_auth(command_class: Type) -> Type:
    """
    Require authentication for command.

    Usage:
        @requires_auth
        class GetProfile(Command[GetProfileInputs, Profile]):
            def execute(self) -> Profile:
                # Only authenticated users can access
                return load_profile(self.auth_context.user_id)
    """
    registry = get_global_registry()
    registry.register(command_class, Authenticated())
    return command_class


def requires_role(*roles: str):
    """
    Require specific role(s) for command.

    Args:
        *roles: Required roles (any one is sufficient)

    Usage:
        @requires_role("admin")
        class DeleteUser(Command[DeleteUserInputs, None]):
            def execute(self) -> None:
                # Only admins can delete users
                delete_user(self.inputs.user_id)

        @requires_role("admin", "moderator")
        class BanUser(Command[BanUserInputs, None]):
            def execute(self) -> None:
                # Admins OR moderators can ban users
                ban_user(self.inputs.user_id)
    """

    def decorator(command_class: Type) -> Type:
        registry = get_global_registry()
        registry.register(command_class, RoleRequired(*roles))
        return command_class

    return decorator


def requires_all_roles(*roles: str):
    """
    Require all specified roles for command.

    Args:
        *roles: Required roles (all are necessary)

    Usage:
        @requires_all_roles("admin", "superuser")
        class SystemConfig(Command[SystemConfigInputs, None]):
            def execute(self) -> None:
                # Only users with BOTH admin AND superuser roles
                update_system_config(self.inputs.config)
    """

    def decorator(command_class: Type) -> Type:
        registry = get_global_registry()
        registry.register(command_class, AllRolesRequired(*roles))
        return command_class

    return decorator


def requires_permission(*permissions: str):
    """
    Require specific permission(s) for command.

    Args:
        *permissions: Required permissions (any one is sufficient)

    Usage:
        @requires_permission("users:write")
        class UpdateUser(Command[UpdateUserInputs, User]):
            def execute(self) -> User:
                # Only users with users:write permission
                return update_user(self.inputs)
    """

    def decorator(command_class: Type) -> Type:
        registry = get_global_registry()
        registry.register(command_class, PermissionRequired(*permissions))
        return command_class

    return decorator


def requires_all_permissions(*permissions: str):
    """
    Require all specified permissions for command.

    Args:
        *permissions: Required permissions (all are necessary)

    Usage:
        @requires_all_permissions("users:read", "users:write")
        class MigrateUsers(Command[MigrateUsersInputs, None]):
            def execute(self) -> None:
                # Requires both read AND write permissions
                migrate_users()
    """

    def decorator(command_class: Type) -> Type:
        registry = get_global_registry()
        registry.register(command_class, AllPermissionsRequired(*permissions))
        return command_class

    return decorator


def requires_rules(*rules: AllowedRule):
    """
    Require custom rules for command.

    Args:
        *rules: Custom authorization rules

    Usage:
        def same_tenant(context, command):
            return context.metadata.get("tenant_id") == "acme"

        @requires_rules(CustomRule(same_tenant))
        class AccessTenantData(Command[AccessInputs, Data]):
            def execute(self) -> Data:
                # Only users from same tenant
                return load_data(self.inputs.data_id)
    """

    def decorator(command_class: Type) -> Type:
        registry = get_global_registry()
        registry.register(command_class, *rules)
        return command_class

    return decorator


def public(command_class: Type) -> Type:
    """
    Mark command as publicly accessible (no auth required).

    This explicitly documents that a command requires no authentication.
    It doesn't add any rules but serves as documentation.

    Usage:
        @public
        class GetPublicConfig(Command[NoInputs, Config]):
            def execute(self) -> Config:
                # Anyone can access this
                return load_public_config()
    """
    # Just mark it, don't add any rules
    # Could add metadata in the future if needed
    return command_class
