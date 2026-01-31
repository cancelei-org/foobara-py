"""
Base Request class for Foobara connectors.

Provides a unified request abstraction that can work with or without
a command connector instance (matching Ruby foobara v0.5.1 commit e34ce225).
"""

from typing import Any, Dict, Optional

from foobara_py.auth.authenticator import AuthContext, Authenticator


class Request:
    """
    Base request class for command connectors.

    Can operate independently without a command_connector instance,
    supporting standalone authentication and request handling.

    Attributes:
        inputs: Command input data
        full_command_name: Fully qualified command name
        action: Action to perform (optional, connector-specific)
        authenticator: Authenticator instance for authentication
        auth_mappers: Dict mapping attribute names to transformation functions
        authenticated_user: User data after successful authentication
        authenticated_context: Full authentication context
    """

    def __init__(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        full_command_name: Optional[str] = None,
        action: Optional[str] = None,
        authenticator: Optional[Authenticator] = None,
        auth_mappers: Optional[Dict[str, Any]] = None,
        serializers: Optional[list] = None,
    ):
        """
        Initialize request.

        Args:
            inputs: Command input dictionary
            full_command_name: Full command name (e.g., "Org::Domain::Command")
            action: Optional action identifier
            authenticator: Authenticator to use for authentication
            auth_mappers: Mapping of attribute names to value transformers
            serializers: List of serializers for response
        """
        self.inputs = inputs or {}
        self.full_command_name = full_command_name
        self.action = action
        self.authenticator = authenticator
        self.auth_mappers = auth_mappers or {}
        self.serializers = serializers or []

        # Authentication state
        self.authenticated_user: Any = None
        self.authenticated_context: Optional[AuthContext] = None

        # Can be set by connector
        self.command_class: Any = None
        self.command_connector: Any = None

    def authenticate(self) -> bool:
        """
        Authenticate the request using the configured authenticator.

        Returns:
            True if authentication succeeded, False otherwise
        """
        if not self.authenticator:
            # No authenticator configured - treat as unauthenticated
            return False

        context = self.authenticator.authenticate(self)
        if context:
            self.authenticated_context = context
            self.authenticated_user = context.user_id
            return True

        return False

    def is_authenticated(self) -> bool:
        """Check if request has been successfully authenticated"""
        return self.authenticated_user is not None

    def auth_mapped_method(self, method_name: str) -> bool:
        """Check if method is an auth-mapped attribute"""
        return method_name in self.auth_mappers

    def auth_mapped_value_for(self, name: str) -> Any:
        """
        Get auth-mapped value for attribute name.

        Applies transformer from auth_mappers to authenticated_user.

        Args:
            name: Attribute name to retrieve

        Returns:
            Transformed value or None if not authenticated
        """
        if not self.authenticated_user:
            return None

        mapper = self.auth_mappers.get(name)
        if mapper is None:
            return None

        # Apply transformer/mapper to authenticated user
        if callable(mapper):
            return mapper(self.authenticated_user)
        return mapper

    def __getattr__(self, name: str) -> Any:
        """
        Support dynamic attribute access for auth-mapped methods.

        This allows request.some_attribute to work if some_attribute
        is defined in auth_mappers.
        """
        # Avoid infinite recursion on private attributes
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # Check if this is an auth-mapped attribute
        if self.auth_mapped_method(name):
            return self.auth_mapped_value_for(name)

        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def relevant_entity_classes(self) -> list:
        """
        Get relevant entity classes for this request.

        Combines entity classes from authenticator (if it supports them)
        with entity classes from command transformers.

        Returns:
            List of entity classes
        """
        classes = []

        # Get entity classes from authenticator if it supports the method
        if self.authenticator and hasattr(self.authenticator, "relevant_entity_classes"):
            auth_classes = self.authenticator.relevant_entity_classes(self)
            if auth_classes:
                classes.extend(auth_classes)

        # Get entity classes from command (if set and it has transformers)
        if self.command_class:
            # This would need to be implemented based on command structure
            pass

        return classes
