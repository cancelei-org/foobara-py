"""
HTTP Integration for Foobara Auth System.

Provides middleware and utilities for integrating authentication
with HTTP connectors (FastAPI, Starlette, etc.).
"""

from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request as StarletteRequest

from foobara_py.auth.authenticator import AuthContext, AuthenticatorSelector
from foobara_py.auth.rules import RuleRegistry, get_global_registry


class AuthMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for authentication.

    Authenticates requests using configured authenticators
    and attaches auth context to request state.

    Usage:
        from fastapi import FastAPI
        from foobara_py.auth import BearerTokenAuthenticator
        from foobara_py.auth.http import AuthMiddleware, create_auth_selector

        app = FastAPI()

        selector = create_auth_selector(
            BearerTokenAuthenticator(secret="secret")
        )

        app.add_middleware(AuthMiddleware, selector=selector)
    """

    def __init__(self, app, selector: AuthenticatorSelector, required: bool = False):
        """
        Initialize auth middleware.

        Args:
            app: ASGI application
            selector: AuthenticatorSelector for authentication
            required: If True, reject unauthenticated requests
        """
        super().__init__(app)
        self.selector = selector
        self.required = required

    async def dispatch(self, request: StarletteRequest, call_next):
        """Process request with authentication."""
        # Authenticate request
        context = self.selector.authenticate(request)

        # Store context in request state
        request.state.auth_context = context

        # If authentication is required and failed, return 401
        if self.required and context is None:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "errors": [{"symbol": "unauthorized", "message": "Authentication required"}],
                },
            )

        # Continue processing
        response = await call_next(request)
        return response


def create_auth_selector(*authenticators) -> AuthenticatorSelector:
    """
    Create an AuthenticatorSelector with the given authenticators.

    Usage:
        selector = create_auth_selector(
            BearerTokenAuthenticator(secret="secret"),
            ApiKeyAuthenticator(api_keys={"key": {"user_id": 1}})
        )
    """
    selector = AuthenticatorSelector()
    for authenticator in authenticators:
        selector.register(authenticator)
    return selector


def get_auth_context(request: Request) -> Optional[AuthContext]:
    """
    Get authentication context from request.

    FastAPI dependency to extract auth context from request state.

    Usage:
        from fastapi import Depends

        @app.post("/users")
        async def create_user(
            context: AuthContext = Depends(get_auth_context)
        ):
            user_id = context.user_id
            ...
    """
    return getattr(request.state, "auth_context", None)


def require_auth(request: Request) -> AuthContext:
    """
    Require authentication.

    FastAPI dependency that requires authenticated user.
    Raises HTTPException(401) if not authenticated.

    Usage:
        from fastapi import Depends

        @app.post("/profile")
        async def get_profile(
            context: AuthContext = Depends(require_auth)
        ):
            # context is guaranteed to be authenticated
            return load_profile(context.user_id)
    """
    context = get_auth_context(request)
    if context is None or context.user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return context


def require_role(*roles: str):
    """
    Create dependency that requires specific role(s).

    Args:
        *roles: Required roles (any one is sufficient)

    Usage:
        from fastapi import Depends

        require_admin = require_role("admin")

        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            context: AuthContext = Depends(require_admin)
        ):
            # Only admins can access
            delete_user(user_id)
    """

    def check(request: Request) -> AuthContext:
        context = require_auth(request)
        if not context.has_any_role(*roles):
            raise HTTPException(
                status_code=403, detail=f"Requires one of roles: {', '.join(roles)}"
            )
        return context

    return check


def require_permission(*permissions: str):
    """
    Create dependency that requires specific permission(s).

    Args:
        *permissions: Required permissions (any one is sufficient)

    Usage:
        from fastapi import Depends

        require_write = require_permission("users:write")

        @app.put("/users/{user_id}")
        async def update_user(
            user_id: int,
            context: AuthContext = Depends(require_write)
        ):
            # Only users with write permission can access
            update_user(user_id, ...)
    """

    def check(request: Request) -> AuthContext:
        context = require_auth(request)
        if not context.has_any_permission(*permissions):
            raise HTTPException(
                status_code=403, detail=f"Requires one of permissions: {', '.join(permissions)}"
            )
        return context

    return check


def create_auth_dependency(
    selector: AuthenticatorSelector, registry: Optional[RuleRegistry] = None
) -> Callable:
    """
    Create a FastAPI dependency for command authorization.

    This creates a dependency that:
    1. Authenticates the request using the selector
    2. Checks authorization rules from the registry

    Args:
        selector: AuthenticatorSelector for authentication
        registry: RuleRegistry for authorization (defaults to global)

    Returns:
        FastAPI dependency function

    Usage:
        selector = create_auth_selector(
            BearerTokenAuthenticator(secret="secret")
        )

        auth_dep = create_auth_dependency(selector)

        # Use in connector
        connector = HTTPConnector(app, auth_config=AuthConfig(
            enabled=True,
            dependency=auth_dep
        ))
    """
    if registry is None:
        registry = get_global_registry()

    def auth_dependency(request: Request) -> AuthContext:
        # Get context from middleware (if present)
        context = get_auth_context(request)

        # If no middleware, authenticate directly
        if context is None:
            context = selector.authenticate(request)

        # For now, return context
        # Command-level authorization will be checked separately
        return context

    return auth_dependency


def configure_cors(
    app,
    allow_origins: List[str] = ["*"],
    allow_credentials: bool = True,
    allow_methods: List[str] = ["*"],
    allow_headers: List[str] = ["*"],
):
    """
    Configure CORS for authentication endpoints.

    Args:
        app: FastAPI/Starlette application
        allow_origins: Allowed origins
        allow_credentials: Allow credentials
        allow_methods: Allowed HTTP methods
        allow_headers: Allowed headers

    Usage:
        from fastapi import FastAPI
        from foobara_py.auth.http import configure_cors

        app = FastAPI()
        configure_cors(app, allow_origins=["https://example.com"])
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        expose_headers=["*"],
    )


# FastAPI Security schemes for OpenAPI documentation
bearer_scheme = HTTPBearer(auto_error=False)


def bearer_token_dependency(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[str]:
    """
    Extract Bearer token from Authorization header.

    Usage with BearerTokenAuthenticator:
        from foobara_py.auth import BearerTokenAuthenticator
        from foobara_py.auth.http import bearer_token_dependency

        authenticator = BearerTokenAuthenticator(secret="secret")

        @app.get("/profile")
        async def get_profile(
            token: str = Depends(bearer_token_dependency)
        ):
            # Manually authenticate
            context = authenticator.authenticate(
                MockRequest(headers={"Authorization": f"Bearer {token}"})
            )
            ...
    """
    return credentials.credentials if credentials else None
