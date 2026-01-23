"""
HTTP-specific Authenticators.

Provides authentication for HTTP requests (Bearer tokens, API keys, etc.).
"""

from typing import Any, Callable, Dict, Optional

from foobara_py.auth.authenticator import AuthContext, Authenticator


class BearerTokenAuthenticator(Authenticator):
    """
    JWT Bearer token authentication.

    Validates JWT tokens from HTTP Authorization header.

    Usage:
        authenticator = BearerTokenAuthenticator(
            secret="your-secret-key",
            algorithm="HS256"
        )

        context = authenticator.authenticate(request)
        if context:
            print(f"Authenticated as {context.user_id}")
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        verify_exp: bool = True,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
    ):
        """
        Initialize Bearer token authenticator.

        Args:
            secret: Secret key for JWT validation
            algorithm: JWT algorithm (default: HS256)
            verify_exp: Verify token expiration (default: True)
            audience: Expected audience claim
            issuer: Expected issuer claim
        """
        self.secret = secret
        self.algorithm = algorithm
        self.verify_exp = verify_exp
        self.audience = audience
        self.issuer = issuer

    def applies_to(self, request: Any) -> bool:
        """Check if request has Bearer token."""
        if not hasattr(request, "headers"):
            return False

        auth_header = request.headers.get("Authorization", "")
        return auth_header.startswith("Bearer ")

    def authenticate(self, request: Any) -> Optional[AuthContext]:
        """Authenticate Bearer token and return context."""
        try:
            import jwt
        except ImportError:
            raise ImportError(
                "PyJWT required for BearerTokenAuthenticator. Install with: pip install pyjwt"
            )

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            # Build decode options
            options = {"verify_exp": self.verify_exp}

            # Decode token
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options=options,
                audience=self.audience,
                issuer=self.issuer,
            )

            # Extract auth context
            return AuthContext(
                user_id=payload.get("sub"),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                metadata={
                    "token_payload": payload,
                    "exp": payload.get("exp"),
                    "iat": payload.get("iat"),
                },
            )

        except jwt.InvalidTokenError:
            return None


class ApiKeyAuthenticator(Authenticator):
    """
    API key authentication.

    Validates API keys from HTTP header or query parameter.

    Usage:
        # Using header
        authenticator = ApiKeyAuthenticator(
            api_keys={"key123": {"user_id": 42, "roles": ["api"]}},
            header_name="X-API-Key"
        )

        # Using query parameter
        authenticator = ApiKeyAuthenticator(
            api_keys={"key123": {"user_id": 42}},
            query_param="api_key"
        )
    """

    def __init__(
        self,
        api_keys: Dict[str, Dict[str, Any]],
        header_name: Optional[str] = "X-API-Key",
        query_param: Optional[str] = None,
    ):
        """
        Initialize API key authenticator.

        Args:
            api_keys: Dict mapping API keys to context data
            header_name: HTTP header name for API key (default: X-API-Key)
            query_param: Query parameter name for API key (optional)
        """
        self.api_keys = api_keys
        self.header_name = header_name
        self.query_param = query_param

    def applies_to(self, request: Any) -> bool:
        """Check if request has API key."""
        if self.header_name and hasattr(request, "headers"):
            if self.header_name in request.headers:
                return True

        if self.query_param and hasattr(request, "query_params"):
            if self.query_param in request.query_params:
                return True

        return False

    def authenticate(self, request: Any) -> Optional[AuthContext]:
        """Authenticate API key and return context."""
        api_key = None

        # Try header first
        if self.header_name and hasattr(request, "headers"):
            api_key = request.headers.get(self.header_name)

        # Fall back to query param
        if not api_key and self.query_param and hasattr(request, "query_params"):
            api_key = request.query_params.get(self.query_param)

        if not api_key or api_key not in self.api_keys:
            return None

        # Build auth context from API key data
        key_data = self.api_keys[api_key]

        return AuthContext(
            user_id=key_data.get("user_id"),
            roles=key_data.get("roles", []),
            permissions=key_data.get("permissions", []),
            metadata={"api_key": api_key, **key_data.get("metadata", {})},
        )


class BasicAuthAuthenticator(Authenticator):
    """
    HTTP Basic authentication.

    Validates username/password from HTTP Basic Auth header.

    Usage:
        def verify_credentials(username, password):
            # Your verification logic
            if username == "admin" and password == "secret":
                return {"user_id": 1, "roles": ["admin"]}
            return None

        authenticator = BasicAuthAuthenticator(
            verify=verify_credentials
        )
    """

    def __init__(self, verify: Callable[[str, str], Optional[Dict[str, Any]]]):
        """
        Initialize Basic auth authenticator.

        Args:
            verify: Function to verify credentials, returns context data or None
        """
        self.verify = verify

    def applies_to(self, request: Any) -> bool:
        """Check if request has Basic auth."""
        if not hasattr(request, "headers"):
            return False

        auth_header = request.headers.get("Authorization", "")
        return auth_header.startswith("Basic ")

    def authenticate(self, request: Any) -> Optional[AuthContext]:
        """Authenticate Basic auth and return context."""
        import base64

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return None

        # Decode credentials
        try:
            encoded = auth_header[6:]  # Remove "Basic " prefix
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return None

        # Verify credentials
        result = self.verify(username, password)
        if result is None:
            return None

        # Build auth context
        return AuthContext(
            user_id=result.get("user_id"),
            roles=result.get("roles", []),
            permissions=result.get("permissions", []),
            metadata={"username": username, **result.get("metadata", {})},
        )


class SessionCookieAuthenticator(Authenticator):
    """
    Session cookie authentication.

    Validates session IDs from HTTP cookies.

    Usage:
        def load_session(session_id):
            # Load session from store
            session = session_store.get(session_id)
            if session:
                return {
                    "user_id": session.user_id,
                    "roles": session.roles
                }
            return None

        authenticator = SessionCookieAuthenticator(
            cookie_name="session_id",
            load_session=load_session
        )
    """

    def __init__(self, cookie_name: str, load_session: Callable[[str], Optional[Dict[str, Any]]]):
        """
        Initialize session cookie authenticator.

        Args:
            cookie_name: Name of the session cookie
            load_session: Function to load session data, returns context data or None
        """
        self.cookie_name = cookie_name
        self.load_session = load_session

    def applies_to(self, request: Any) -> bool:
        """Check if request has session cookie."""
        if not hasattr(request, "cookies"):
            return False

        return self.cookie_name in request.cookies

    def authenticate(self, request: Any) -> Optional[AuthContext]:
        """Authenticate session cookie and return context."""
        session_id = request.cookies.get(self.cookie_name)
        if not session_id:
            return None

        # Load session data
        session_data = self.load_session(session_id)
        if session_data is None:
            return None

        # Build auth context
        return AuthContext(
            user_id=session_data.get("user_id"),
            roles=session_data.get("roles", []),
            permissions=session_data.get("permissions", []),
            metadata={"session_id": session_id, **session_data.get("metadata", {})},
        )
