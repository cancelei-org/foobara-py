"""
Foobara Authentication and Authorization.

Provides authentication and authorization infrastructure for foobara-py commands.

Usage:
    # Authentication
    from foobara_py.auth import (
        AuthContext,
        BearerTokenAuthenticator,
        AuthenticatorSelector
    )

    selector = AuthenticatorSelector()
    selector.register(BearerTokenAuthenticator(secret="secret"))

    context = selector.authenticate(request)

    # Authorization
    from foobara_py.auth import (
        requires_auth,
        requires_role,
        requires_permission
    )

    @requires_auth
    @requires_role("admin")
    class DeleteUser(Command[DeleteUserInputs, None]):
        def execute(self) -> None:
            delete_user(self.inputs.user_id)
"""

from foobara_py.auth.authenticator import (
    AuthContext,
    Authenticator,
    AuthenticatorSelector,
)
from foobara_py.auth.decorators import (
    public,
    requires_all_permissions,
    requires_all_roles,
    requires_auth,
    requires_permission,
    requires_role,
    requires_rules,
)
from foobara_py.auth.http import (
    AuthMiddleware,
    bearer_token_dependency,
    configure_cors,
    create_auth_dependency,
    create_auth_selector,
    get_auth_context,
    require_auth,
    require_permission,
    require_role,
)
from foobara_py.auth.http_auth import (
    ApiKeyAuthenticator,
    BasicAuthAuthenticator,
    BearerTokenAuthenticator,
    SessionCookieAuthenticator,
)
from foobara_py.auth.rules import (
    AllowedRule,
    AllPermissionsRequired,
    AllRolesRequired,
    Authenticated,
    CustomRule,
    PermissionRequired,
    RoleRequired,
    RuleRegistry,
    get_global_registry,
    reset_global_registry,
)

__all__ = [
    # Core
    "AuthContext",
    "Authenticator",
    "AuthenticatorSelector",
    # HTTP Authenticators
    "BearerTokenAuthenticator",
    "ApiKeyAuthenticator",
    "BasicAuthAuthenticator",
    "SessionCookieAuthenticator",
    # Rules
    "AllowedRule",
    "RoleRequired",
    "AllRolesRequired",
    "PermissionRequired",
    "AllPermissionsRequired",
    "Authenticated",
    "CustomRule",
    "RuleRegistry",
    "get_global_registry",
    "reset_global_registry",
    # Decorators
    "requires_auth",
    "requires_role",
    "requires_all_roles",
    "requires_permission",
    "requires_all_permissions",
    "requires_rules",
    "public",
    # HTTP Integration
    "AuthMiddleware",
    "create_auth_selector",
    "get_auth_context",
    "require_auth",
    "require_permission",
    "create_auth_dependency",
    "configure_cors",
    "bearer_token_dependency",
]
