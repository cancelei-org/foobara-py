"""
Base Authenticator Classes and Authentication Context.

Provides authentication infrastructure for foobara-py commands.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    """
    Authentication context passed to commands.

    Contains authenticated user information and authorization data.

    Usage:
        context = AuthContext(
            user_id=42,
            roles=["admin", "user"],
            permissions=["read", "write"],
            metadata={"tenant_id": "acme"}
        )
    """

    user_id: Any = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        """Check if context has specific role."""
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        """Check if context has any of the specified roles."""
        return bool(set(roles) & set(self.roles))

    def has_all_roles(self, *roles: str) -> bool:
        """Check if context has all of the specified roles."""
        return set(roles).issubset(set(self.roles))

    def has_permission(self, permission: str) -> bool:
        """Check if context has specific permission."""
        return permission in self.permissions

    def has_any_permission(self, *permissions: str) -> bool:
        """Check if context has any of the specified permissions."""
        return bool(set(permissions) & set(self.permissions))

    def has_all_permissions(self, *permissions: str) -> bool:
        """Check if context has all of the specified permissions."""
        return set(permissions).issubset(set(self.permissions))


class Authenticator(ABC):
    """
    Base authenticator interface.

    Subclass to implement custom authentication strategies.

    Usage:
        class MyAuthenticator(Authenticator):
            def applies_to(self, request: Any) -> bool:
                return hasattr(request, 'token')

            def authenticate(self, request: Any) -> Optional[AuthContext]:
                if verify_token(request.token):
                    return AuthContext(user_id=extract_user_id(request.token))
                return None
    """

    @abstractmethod
    def applies_to(self, request: Any) -> bool:
        """
        Check if this authenticator handles this request type.

        Args:
            request: Request object to check

        Returns:
            True if this authenticator should handle the request
        """
        pass

    @abstractmethod
    def authenticate(self, request: Any) -> Optional[AuthContext]:
        """
        Authenticate request and return context.

        Args:
            request: Request object to authenticate

        Returns:
            AuthContext if authentication succeeds, None otherwise
        """
        pass

    def relevant_entity_classes(self, request: Any) -> list:
        """
        Get relevant entity classes for this authenticator.

        This is an optional method that authenticators can implement if they
        work with foobara entities. Authenticators without entity support
        can omit this method (commit 3629b462).

        Args:
            request: Request object

        Returns:
            List of entity classes or empty list
        """
        return []


class AuthenticatorSelector:
    """
    Select appropriate authenticator for a request.

    Manages multiple authenticators and routes requests to the correct one.

    Usage:
        selector = AuthenticatorSelector()
        selector.register(BearerTokenAuthenticator(secret="secret"))
        selector.register(ApiKeyAuthenticator())

        context = selector.authenticate(request)
        if context:
            print(f"Authenticated as user {context.user_id}")
    """

    def __init__(self):
        self._authenticators: List[Authenticator] = []

    def register(self, authenticator: Authenticator) -> "AuthenticatorSelector":
        """
        Register an authenticator.

        Args:
            authenticator: Authenticator to register

        Returns:
            Self for chaining
        """
        self._authenticators.append(authenticator)
        return self

    def authenticate(self, request: Any) -> Optional[AuthContext]:
        """
        Authenticate request using registered authenticators.

        Tries authenticators in registration order until one succeeds.

        Args:
            request: Request to authenticate

        Returns:
            AuthContext if any authenticator succeeds, None otherwise
        """
        for authenticator in self._authenticators:
            if authenticator.applies_to(request):
                context = authenticator.authenticate(request)
                if context is not None:
                    return context
        return None

    def clear(self) -> None:
        """Clear all registered authenticators."""
        self._authenticators.clear()
