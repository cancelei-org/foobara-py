"""Tests for HTTP Authentication Integration"""

import pytest
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from foobara_py.core.command import Command
from foobara_py.auth import (
    AuthContext,
    BearerTokenAuthenticator,
    ApiKeyAuthenticator,
    create_auth_selector,
    AuthMiddleware,
    get_auth_context,
    require_auth,
    require_role,
    require_permission,
    create_auth_dependency,
    configure_cors,
)


class TestAuthMiddleware:
    """Test AuthMiddleware"""

    @pytest.fixture
    def app(self):
        """Create FastAPI app with auth middleware"""
        app = FastAPI()

        # Create selector
        selector = create_auth_selector(
            BearerTokenAuthenticator(secret="test-secret"),
            ApiKeyAuthenticator(
                api_keys={"key123": {"user_id": 42, "roles": ["api"]}},
                header_name="X-API-Key"
            )
        )

        # Add middleware
        app.add_middleware(AuthMiddleware, selector=selector, required=False)

        # Test endpoint
        @app.get("/test")
        async def test_endpoint(request: Request):
            context = get_auth_context(request)
            if context:
                return {"authenticated": True, "user_id": context.user_id}
            return {"authenticated": False}

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_unauthenticated_request(self, client):
        """Should handle unauthenticated request"""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"authenticated": False}

    def test_bearer_token_auth(self, client):
        """Should authenticate with Bearer token"""
        import jwt

        token = jwt.encode({"sub": "99"}, "test-secret", algorithm="HS256")
        response = client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user_id"] == "99"

    def test_api_key_auth(self, client):
        """Should authenticate with API key"""
        response = client.get(
            "/test",
            headers={"X-API-Key": "key123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user_id"] == 42

    def test_invalid_token(self, client):
        """Should reject invalid token"""
        response = client.get(
            "/test",
            headers={"Authorization": "Bearer invalid"}
        )

        assert response.status_code == 200
        assert response.json() == {"authenticated": False}


class TestAuthMiddlewareRequired:
    """Test AuthMiddleware with required=True"""

    @pytest.fixture
    def app(self):
        """Create app with required auth"""
        app = FastAPI()

        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"valid": {"user_id": 1}},
                header_name="X-API-Key"
            )
        )

        app.add_middleware(AuthMiddleware, selector=selector, required=True)

        @app.get("/protected")
        async def protected():
            return {"message": "success"}

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_rejects_unauthenticated(self, client):
        """Should reject unauthenticated requests"""
        response = client.get("/protected")

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "unauthorized" in data["errors"][0]["symbol"]

    def test_allows_authenticated(self, client):
        """Should allow authenticated requests"""
        response = client.get(
            "/protected",
            headers={"X-API-Key": "valid"}
        )

        assert response.status_code == 200
        assert response.json() == {"message": "success"}


class TestAuthDependencies:
    """Test FastAPI auth dependencies"""

    @pytest.fixture
    def app(self):
        """Create app with auth dependencies"""
        app = FastAPI()

        selector = create_auth_selector(
            BearerTokenAuthenticator(secret="test-secret")
        )

        app.add_middleware(AuthMiddleware, selector=selector)

        @app.get("/public")
        async def public_endpoint():
            return {"public": True}

        @app.get("/authenticated")
        async def auth_endpoint(context: AuthContext = Depends(require_auth)):
            return {"user_id": context.user_id}

        @app.get("/admin")
        async def admin_endpoint(context: AuthContext = Depends(require_role("admin"))):
            return {"admin": True}

        @app.get("/write")
        async def write_endpoint(context: AuthContext = Depends(require_permission("write"))):
            return {"can_write": True}

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_public_endpoint(self, client):
        """Public endpoint should work without auth"""
        response = client.get("/public")
        assert response.status_code == 200
        assert response.json() == {"public": True}

    def test_require_auth_success(self, client):
        """Should allow authenticated user"""
        import jwt

        token = jwt.encode({"sub": "42"}, "test-secret", algorithm="HS256")
        response = client.get(
            "/authenticated",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json() == {"user_id": "42"}

    def test_require_auth_failure(self, client):
        """Should reject unauthenticated user"""
        response = client.get("/authenticated")

        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_require_role_success(self, client):
        """Should allow user with role"""
        import jwt

        token = jwt.encode(
            {"sub": "42", "roles": ["admin"]},
            "test-secret",
            algorithm="HS256"
        )
        response = client.get(
            "/admin",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json() == {"admin": True}

    def test_require_role_failure(self, client):
        """Should reject user without role"""
        import jwt

        token = jwt.encode(
            {"sub": "42", "roles": ["user"]},
            "test-secret",
            algorithm="HS256"
        )
        response = client.get(
            "/admin",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "admin" in response.json()["detail"]

    def test_require_permission_success(self, client):
        """Should allow user with permission"""
        import jwt

        token = jwt.encode(
            {"sub": "42", "permissions": ["write"]},
            "test-secret",
            algorithm="HS256"
        )
        response = client.get(
            "/write",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json() == {"can_write": True}

    def test_require_permission_failure(self, client):
        """Should reject user without permission"""
        import jwt

        token = jwt.encode(
            {"sub": "42", "permissions": ["read"]},
            "test-secret",
            algorithm="HS256"
        )
        response = client.get(
            "/write",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "write" in response.json()["detail"]


class TestCreateAuthDependency:
    """Test create_auth_dependency"""

    def test_creates_dependency(self):
        """Should create auth dependency"""
        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"key": {"user_id": 1}},
                header_name="X-API-Key"
            )
        )

        dep = create_auth_dependency(selector)
        assert callable(dep)

    def test_dependency_usage(self):
        """Should work as FastAPI dependency"""
        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"valid": {"user_id": 99, "roles": ["admin"]}},
                header_name="X-API-Key"
            )
        )

        app = FastAPI()
        auth_dep = create_auth_dependency(selector)

        @app.get("/test")
        async def test_endpoint(context: AuthContext = Depends(auth_dep)):
            return {
                "user_id": context.user_id if context else None,
                "roles": context.roles if context else []
            }

        client = TestClient(app)

        # Without auth
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["user_id"] is None

        # With auth
        response = client.get("/test", headers={"X-API-Key": "valid"})
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 99
        assert data["roles"] == ["admin"]


class TestConfigureCORS:
    """Test configure_cors"""

    def test_adds_cors_middleware(self):
        """Should add CORS middleware"""
        from foobara_py.auth import configure_cors
        from starlette.middleware.cors import CORSMiddleware

        app = FastAPI()
        configure_cors(app, allow_origins=["https://example.com"])

        # Check middleware was added
        # FastAPI wraps middleware in Middleware objects
        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_cors_headers(self):
        """Should set CORS headers"""
        from foobara_py.auth import configure_cors

        app = FastAPI()
        configure_cors(app, allow_origins=["https://example.com"])

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Origin": "https://example.com"}
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


class TestCreateAuthSelector:
    """Test create_auth_selector"""

    def test_creates_selector(self):
        """Should create selector with authenticators"""
        from foobara_py.auth.authenticator import AuthenticatorSelector

        selector = create_auth_selector(
            BearerTokenAuthenticator(secret="secret"),
            ApiKeyAuthenticator(api_keys={"key": {"user_id": 1}})
        )

        assert isinstance(selector, AuthenticatorSelector)
        assert len(selector._authenticators) == 2

    def test_empty_selector(self):
        """Should create empty selector"""
        selector = create_auth_selector()
        assert len(selector._authenticators) == 0


class TestGetAuthContext:
    """Test get_auth_context"""

    def test_gets_context_from_request(self):
        """Should extract context from request state"""
        app = FastAPI()

        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"key": {"user_id": 42}},
                header_name="X-API-Key"
            )
        )

        app.add_middleware(AuthMiddleware, selector=selector)

        @app.get("/test")
        async def test(request: Request):
            context = get_auth_context(request)
            if context:
                return {"user_id": context.user_id}
            return {"user_id": None}

        client = TestClient(app)
        response = client.get("/test", headers={"X-API-Key": "key"})

        assert response.status_code == 200
        assert response.json() == {"user_id": 42}

    def test_returns_none_without_middleware(self):
        """Should return None without middleware"""
        app = FastAPI()

        @app.get("/test")
        async def test(request: Request):
            context = get_auth_context(request)
            return {"has_context": context is not None}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"has_context": False}


class TestIntegrationWithHTTPConnector:
    """Test integration with HTTPConnector"""

    def test_http_connector_with_auth(self):
        """Should integrate auth with HTTP connector"""
        from foobara_py.connectors.http import HTTPConnector, AuthConfig

        app = FastAPI()

        # Create auth selector
        selector = create_auth_selector(
            BearerTokenAuthenticator(secret="test-secret")
        )

        # Add middleware
        app.add_middleware(AuthMiddleware, selector=selector)

        # Create auth dependency
        auth_dep = create_auth_dependency(selector)

        # Create connector with auth
        connector = HTTPConnector(
            app,
            auth_config=AuthConfig(enabled=True, dependency=auth_dep)
        )

        # Register a command
        class TestInputs(BaseModel):
            message: str

        class TestCommand(Command[TestInputs, str]):
            """Test command"""

            def execute(self) -> str:
                return f"Echo: {self.inputs.message}"

        connector.register(TestCommand)

        # Test
        client = TestClient(app)

        import jwt
        token = jwt.encode({"sub": "99"}, "test-secret", algorithm="HS256")

        response = client.post(
            "/testcommand",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"] == "Echo: hello"
