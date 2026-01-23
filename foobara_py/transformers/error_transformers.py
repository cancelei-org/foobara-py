"""
Error transformers for customizing error messages and formatting.

These transformers run on error collections to make errors
more user-friendly or adapt them for specific contexts.
"""


from foobara_py.core.errors import ErrorCollection, FoobaraError
from foobara_py.transformers.base import Transformer


class AuthErrorsTransformer(Transformer[ErrorCollection]):
    """
    Transform auth errors to user-friendly messages.

    Converts technical auth error symbols to messages
    appropriate for end users.

    Usage:
        transformer = AuthErrorsTransformer()
        errors = transformer.transform(error_collection)
        # Auth errors have user-friendly messages
    """

    DEFAULT_MESSAGES = {
        "not_authenticated": "Please log in to continue",
        "not_allowed": "You don't have permission for this action",
        "forbidden": "Access denied",
        "authentication_failed": "Invalid credentials",
        "token_expired": "Your session has expired. Please log in again",
        "invalid_token": "Invalid authentication token",
    }

    def __init__(self, custom_messages: dict[str, str] = None):
        """
        Initialize with optional custom messages.

        Args:
            custom_messages: Override default messages for specific symbols
        """
        self.messages = dict(self.DEFAULT_MESSAGES)
        if custom_messages:
            self.messages.update(custom_messages)

    def transform(self, value: ErrorCollection) -> ErrorCollection:
        """Transform auth error messages"""
        if not isinstance(value, ErrorCollection):
            return value

        # Create new collection with transformed errors
        transformed = ErrorCollection()

        for error in value.all():
            if error.symbol in self.messages:
                # Create new error with friendly message
                new_error = FoobaraError(
                    category=error.category,
                    symbol=error.symbol,
                    path=error.path,
                    message=self.messages[error.symbol],
                    context=error.context,
                    runtime_path=error.runtime_path,
                    is_fatal=error.is_fatal,
                )
                transformed.add(new_error)
            else:
                transformed.add(error)

        return transformed


class UserFriendlyErrorsTransformer(Transformer[ErrorCollection]):
    """
    Make all errors more user-friendly.

    Converts technical error messages and symbols into
    natural language suitable for end users.

    Usage:
        transformer = UserFriendlyErrorsTransformer()
        errors = transformer.transform(error_collection)
    """

    FRIENDLY_MESSAGES = {
        # Data validation
        "required": "This field is required",
        "missing_required_attribute": "Required information is missing",
        "invalid_type": "Invalid data type provided",
        "invalid_format": "Invalid format",
        "invalid_value": "Invalid value",
        "cannot_cast": "Unable to convert value to expected type",
        # String validation
        "too_short": "Value is too short",
        "too_long": "Value is too long",
        "blank": "This field cannot be blank",
        # Numeric validation
        "too_small": "Value is too small",
        "too_large": "Value is too large",
        "not_integer": "Value must be a whole number",
        "not_positive": "Value must be positive",
        # Records
        "not_found": "Record not found",
        "already_exists": "Record already exists",
        "record_not_found": "The requested item could not be found",
        # Runtime
        "execution_error": "An error occurred while processing your request",
        "timeout": "The request timed out. Please try again",
        "external_service_error": "External service unavailable",
        "rate_limit_exceeded": "Too many requests. Please wait and try again",
    }

    def __init__(self, custom_messages: dict[str, str] = None):
        """
        Initialize with optional custom messages.

        Args:
            custom_messages: Override default messages for specific symbols
        """
        self.messages = dict(self.FRIENDLY_MESSAGES)
        if custom_messages:
            self.messages.update(custom_messages)

    def transform(self, value: ErrorCollection) -> ErrorCollection:
        """Transform error messages to be user-friendly"""
        if not isinstance(value, ErrorCollection):
            return value

        transformed = ErrorCollection()

        for error in value.all():
            message = self.messages.get(error.symbol, error.message)

            # Add context to message if available
            if error.context:
                message = self._enrich_message(message, error.context)

            new_error = FoobaraError(
                category=error.category,
                symbol=error.symbol,
                path=error.path,
                message=message,
                context=error.context,
                runtime_path=error.runtime_path,
                is_fatal=error.is_fatal,
            )
            transformed.add(new_error)

        return transformed

    def _enrich_message(self, message: str, context: dict) -> str:
        """Enrich message with context information"""
        # Add min/max constraints if present
        if "min" in context and "max" in context:
            message = f"{message} (must be between {context['min']} and {context['max']})"
        elif "min" in context:
            message = f"{message} (minimum: {context['min']})"
        elif "max" in context:
            message = f"{message} (maximum: {context['max']})"

        return message


class StripRuntimePathTransformer(Transformer[ErrorCollection]):
    """
    Remove runtime path from errors for simpler error responses.

    Useful for API responses where internal command structure
    shouldn't be exposed to clients.

    Usage:
        transformer = StripRuntimePathTransformer()
        errors = transformer.transform(error_collection)
        # Runtime paths removed from all errors
    """

    def transform(self, value: ErrorCollection) -> ErrorCollection:
        """Remove runtime paths from errors"""
        if not isinstance(value, ErrorCollection):
            return value

        transformed = ErrorCollection()

        for error in value.all():
            new_error = FoobaraError(
                category=error.category,
                symbol=error.symbol,
                path=error.path,
                message=error.message,
                context=error.context,
                runtime_path=(),  # Empty runtime path
                is_fatal=error.is_fatal,
            )
            transformed.add(new_error)

        return transformed


class GroupErrorsByPathTransformer(Transformer[ErrorCollection]):
    """
    Group errors by their data path for easier display.

    Returns dict mapping paths to error lists instead of
    flat error collection.

    Usage:
        transformer = GroupErrorsByPathTransformer()
        grouped = transformer.transform(error_collection)
        # Returns: {"user.email": [error1, error2], "user.name": [error3]}
    """

    def transform(self, value: ErrorCollection) -> dict[str, list]:
        """Group errors by path"""
        if not isinstance(value, ErrorCollection):
            return {}

        grouped = {}

        for error in value.all():
            path_key = ".".join(error.path) if error.path else "general"

            if path_key not in grouped:
                grouped[path_key] = []

            grouped[path_key].append(
                {"symbol": error.symbol, "message": error.message, "context": error.context}
            )

        return grouped


# Auto-register transformers
from foobara_py.transformers.base import TransformerRegistry

TransformerRegistry.register("auth_errors", AuthErrorsTransformer, "error")
TransformerRegistry.register("user_friendly_errors", UserFriendlyErrorsTransformer, "error")
TransformerRegistry.register("strip_runtime_path", StripRuntimePathTransformer, "error")
TransformerRegistry.register("group_by_path", GroupErrorsByPathTransformer, "error")
