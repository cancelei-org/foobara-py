"""Tests for Authentication and Authorization system"""

import pytest
from pydantic import BaseModel
from foobara_py.core.command import Command

# Import auth components
from foobara_py.auth import (
    AuthContext,
    Authenticator,
    AuthenticatorSelector,
    BearerTokenAuthenticator,
    ApiKeyAuthenticator,
    BasicAuthAuthenticator,
    SessionCookieAuthenticator,
    RoleRequired,
    AllRolesRequired,
    PermissionRequired,
    AllPermissionsRequired,
    Authenticated,
    CustomRule,
    RuleRegistry,
    requires_auth,
    requires_role,
    requires_all_roles,
    requires_permission,
    requires_all_permissions,
    requires_rules,
    public,
    get_global_registry,
    reset_global_registry,
)


# Test fixtures
class MockRequest:
    """Mock HTTP request for testing"""
    def __init__(self, headers=None, cookies=None, query_params=None):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.query_params = query_params or {}


class TestAuthContext:
    """Test AuthContext class"""

    def test_create_empty_context(self):
        """Should create empty auth context"""
        context = AuthContext()

        assert context.user_id is None
        assert context.roles == []
        assert context.permissions == []
        assert context.metadata == {}

    def test_create_context_with_data(self):
        """Should create context with data"""
        context = AuthContext(
            user_id=42,
            roles=["admin", "user"],
            permissions=["read", "write"],
            metadata={"tenant": "acme"}
        )

        assert context.user_id == 42
        assert context.roles == ["admin", "user"]
        assert context.permissions == ["read", "write"]
        assert context.metadata == {"tenant": "acme"}

    def test_has_role(self):
        """Should check if has role"""
        context = AuthContext(roles=["admin", "user"])

        assert context.has_role("admin")
        assert context.has_role("user")
        assert not context.has_role("moderator")

    def test_has_any_role(self):
        """Should check if has any role"""
        context = AuthContext(roles=["admin"])

        assert context.has_any_role("admin", "moderator")
        assert not context.has_any_role("user", "moderator")

    def test_has_all_roles(self):
        """Should check if has all roles"""
        context = AuthContext(roles=["admin", "user", "moderator"])

        assert context.has_all_roles("admin", "user")
        assert not context.has_all_roles("admin", "superuser")

    def test_has_permission(self):
        """Should check if has permission"""
        context = AuthContext(permissions=["read", "write"])

        assert context.has_permission("read")
        assert context.has_permission("write")
        assert not context.has_permission("delete")

    def test_has_any_permission(self):
        """Should check if has any permission"""
        context = AuthContext(permissions=["read"])

        assert context.has_any_permission("read", "write")
        assert not context.has_any_permission("write", "delete")

    def test_has_all_permissions(self):
        """Should check if has all permissions"""
        context = AuthContext(permissions=["read", "write", "delete"])

        assert context.has_all_permissions("read", "write")
        assert not context.has_all_permissions("read", "admin")


class TestAuthenticatorSelector:
    """Test AuthenticatorSelector class"""

    def test_empty_selector(self):
        """Should return None for empty selector"""
        selector = AuthenticatorSelector()
        request = MockRequest()

        assert selector.authenticate(request) is None

    def test_register_authenticator(self):
        """Should register authenticator"""
        selector = AuthenticatorSelector()

        class TestAuth(Authenticator):
            def applies_to(self, request):
                return True

            def authenticate(self, request):
                return AuthContext(user_id=42)

        selector.register(TestAuth())
        context = selector.authenticate(MockRequest())

        assert context is not None
        assert context.user_id == 42

    def test_chaining(self):
        """Should support chaining"""
        class Auth1(Authenticator):
            def applies_to(self, r):
                return False

            def authenticate(self, r):
                return None

        selector = AuthenticatorSelector()
        result = selector.register(Auth1())

        assert result is selector

    def test_first_matching_wins(self):
        """Should use first matching authenticator"""
        class Auth1(Authenticator):
            def applies_to(self, r):
                return True

            def authenticate(self, r):
                return AuthContext(user_id=1)

        class Auth2(Authenticator):
            def applies_to(self, r):
                return True

            def authenticate(self, r):
                return AuthContext(user_id=2)

        selector = AuthenticatorSelector()
        selector.register(Auth1())
        selector.register(Auth2())

        context = selector.authenticate(MockRequest())
        assert context.user_id == 1

    def test_clear(self):
        """Should clear authenticators"""
        class TestAuth(Authenticator):
            def applies_to(self, r):
                return True

            def authenticate(self, r):
                return AuthContext(user_id=42)

        selector = AuthenticatorSelector()
        selector.register(TestAuth())
        selector.clear()

        assert selector.authenticate(MockRequest()) is None


class TestBearerTokenAuthenticator:
    """Test BearerTokenAuthenticator"""

    @pytest.fixture
    def authenticator(self):
        return BearerTokenAuthenticator(secret="test-secret")

    def test_applies_to_bearer_token(self, authenticator):
        """Should apply to Bearer token requests"""
        request = MockRequest(headers={"Authorization": "Bearer token"})
        assert authenticator.applies_to(request)

    def test_not_applies_to_other_auth(self, authenticator):
        """Should not apply to non-Bearer requests"""
        request = MockRequest(headers={"Authorization": "Basic xyz"})
        assert not authenticator.applies_to(request)

    def test_not_applies_without_auth_header(self, authenticator):
        """Should not apply without Authorization header"""
        request = MockRequest()
        assert not authenticator.applies_to(request)

    def test_authenticate_valid_token(self, authenticator):
        """Should authenticate valid JWT token"""
        import jwt

        token = jwt.encode(
            {"sub": "42", "roles": ["admin"], "permissions": ["read"]},
            "test-secret",
            algorithm="HS256"
        )

        request = MockRequest(headers={"Authorization": f"Bearer {token}"})
        context = authenticator.authenticate(request)

        assert context is not None
        assert context.user_id == "42"
        assert context.roles == ["admin"]
        assert context.permissions == ["read"]

    def test_authenticate_invalid_token(self, authenticator):
        """Should reject invalid token"""
        request = MockRequest(headers={"Authorization": "Bearer invalid"})
        context = authenticator.authenticate(request)

        assert context is None


class TestApiKeyAuthenticator:
    """Test ApiKeyAuthenticator"""

    def test_applies_to_header(self):
        """Should apply to requests with API key header"""
        auth = ApiKeyAuthenticator(
            api_keys={"key123": {"user_id": 1}},
            header_name="X-API-Key"
        )

        request = MockRequest(headers={"X-API-Key": "key123"})
        assert auth.applies_to(request)

    def test_applies_to_query_param(self):
        """Should apply to requests with API key query param"""
        auth = ApiKeyAuthenticator(
            api_keys={"key123": {"user_id": 1}},
            query_param="api_key"
        )

        request = MockRequest(query_params={"api_key": "key123"})
        assert auth.applies_to(request)

    def test_authenticate_valid_key(self):
        """Should authenticate valid API key"""
        auth = ApiKeyAuthenticator(
            api_keys={"key123": {
                "user_id": 42,
                "roles": ["api"],
                "permissions": ["read"]
            }},
            header_name="X-API-Key"
        )

        request = MockRequest(headers={"X-API-Key": "key123"})
        context = auth.authenticate(request)

        assert context is not None
        assert context.user_id == 42
        assert context.roles == ["api"]
        assert context.permissions == ["read"]

    def test_authenticate_invalid_key(self):
        """Should reject invalid API key"""
        auth = ApiKeyAuthenticator(
            api_keys={"key123": {"user_id": 1}},
            header_name="X-API-Key"
        )

        request = MockRequest(headers={"X-API-Key": "wrong"})
        context = auth.authenticate(request)

        assert context is None


class TestBasicAuthAuthenticator:
    """Test BasicAuthAuthenticator"""

    def test_applies_to_basic_auth(self):
        """Should apply to Basic auth requests"""
        def verify(u, p):
            return {"user_id": 1}

        auth = BasicAuthAuthenticator(verify=verify)
        request = MockRequest(headers={"Authorization": "Basic dXNlcjpwYXNz"})

        assert auth.applies_to(request)

    def test_authenticate_valid_credentials(self):
        """Should authenticate valid credentials"""
        def verify(username, password):
            if username == "admin" and password == "secret":
                return {"user_id": 1, "roles": ["admin"]}
            return None

        auth = BasicAuthAuthenticator(verify=verify)

        # "admin:secret" in base64
        import base64
        credentials = base64.b64encode(b"admin:secret").decode()
        request = MockRequest(headers={"Authorization": f"Basic {credentials}"})

        context = auth.authenticate(request)

        assert context is not None
        assert context.user_id == 1
        assert context.roles == ["admin"]

    def test_authenticate_invalid_credentials(self):
        """Should reject invalid credentials"""
        def verify(username, password):
            return None

        auth = BasicAuthAuthenticator(verify=verify)

        import base64
        credentials = base64.b64encode(b"wrong:wrong").decode()
        request = MockRequest(headers={"Authorization": f"Basic {credentials}"})

        context = auth.authenticate(request)
        assert context is None


class TestSessionCookieAuthenticator:
    """Test SessionCookieAuthenticator"""

    def test_applies_to_session_cookie(self):
        """Should apply to requests with session cookie"""
        def load_session(sid):
            return {"user_id": 1}

        auth = SessionCookieAuthenticator(
            cookie_name="session_id",
            load_session=load_session
        )

        request = MockRequest(cookies={"session_id": "abc123"})
        assert auth.applies_to(request)

    def test_authenticate_valid_session(self):
        """Should authenticate valid session"""
        def load_session(session_id):
            if session_id == "valid":
                return {"user_id": 42, "roles": ["user"]}
            return None

        auth = SessionCookieAuthenticator(
            cookie_name="session_id",
            load_session=load_session
        )

        request = MockRequest(cookies={"session_id": "valid"})
        context = auth.authenticate(request)

        assert context is not None
        assert context.user_id == 42
        assert context.roles == ["user"]

    def test_authenticate_invalid_session(self):
        """Should reject invalid session"""
        def load_session(session_id):
            return None

        auth = SessionCookieAuthenticator(
            cookie_name="session_id",
            load_session=load_session
        )

        request = MockRequest(cookies={"session_id": "invalid"})
        context = auth.authenticate(request)

        assert context is None


class TestRules:
    """Test authorization rules"""

    def test_role_required(self):
        """Should check role requirement"""
        rule = RoleRequired("admin")
        context_admin = AuthContext(roles=["admin"])
        context_user = AuthContext(roles=["user"])

        assert rule.allowed(context_admin, None)
        assert not rule.allowed(context_user, None)

    def test_role_required_any(self):
        """Should check any role requirement"""
        rule = RoleRequired("admin", "moderator")
        context_admin = AuthContext(roles=["admin"])
        context_moderator = AuthContext(roles=["moderator"])
        context_user = AuthContext(roles=["user"])

        assert rule.allowed(context_admin, None)
        assert rule.allowed(context_moderator, None)
        assert not rule.allowed(context_user, None)

    def test_all_roles_required(self):
        """Should check all roles requirement"""
        rule = AllRolesRequired("admin", "moderator")
        context_both = AuthContext(roles=["admin", "moderator"])
        context_admin = AuthContext(roles=["admin"])

        assert rule.allowed(context_both, None)
        assert not rule.allowed(context_admin, None)

    def test_permission_required(self):
        """Should check permission requirement"""
        rule = PermissionRequired("write")
        context_write = AuthContext(permissions=["write"])
        context_read = AuthContext(permissions=["read"])

        assert rule.allowed(context_write, None)
        assert not rule.allowed(context_read, None)

    def test_all_permissions_required(self):
        """Should check all permissions requirement"""
        rule = AllPermissionsRequired("read", "write")
        context_both = AuthContext(permissions=["read", "write"])
        context_read = AuthContext(permissions=["read"])

        assert rule.allowed(context_both, None)
        assert not rule.allowed(context_read, None)

    def test_authenticated(self):
        """Should check if authenticated"""
        rule = Authenticated()
        context_auth = AuthContext(user_id=42)
        context_anon = AuthContext()

        assert rule.allowed(context_auth, None)
        assert not rule.allowed(context_anon, None)

    def test_custom_rule(self):
        """Should use custom rule function"""
        def check(context, command):
            return context.metadata.get("tenant") == "acme"

        rule = CustomRule(check)
        context_acme = AuthContext(metadata={"tenant": "acme"})
        context_other = AuthContext(metadata={"tenant": "other"})

        assert rule.allowed(context_acme, None)
        assert not rule.allowed(context_other, None)


class TestRuleRegistry:
    """Test RuleRegistry"""

    @pytest.fixture
    def registry(self):
        return RuleRegistry()

    @pytest.fixture
    def test_command(self):
        class TestCommand:
            pass
        return TestCommand

    def test_no_rules_allows_all(self, registry, test_command):
        """Should allow when no rules registered"""
        context = AuthContext()
        assert registry.check(context, test_command)

    def test_register_rule(self, registry, test_command):
        """Should register and check rule"""
        registry.register(test_command, RoleRequired("admin"))

        context_admin = AuthContext(roles=["admin"])
        context_user = AuthContext(roles=["user"])

        assert registry.check(context_admin, test_command)
        assert not registry.check(context_user, test_command)

    def test_register_multiple_rules(self, registry, test_command):
        """Should check all rules (AND logic)"""
        registry.register(
            test_command,
            RoleRequired("admin"),
            PermissionRequired("write")
        )

        context_both = AuthContext(roles=["admin"], permissions=["write"])
        context_role_only = AuthContext(roles=["admin"])

        assert registry.check(context_both, test_command)
        assert not registry.check(context_role_only, test_command)

    def test_default_rules(self, registry, test_command):
        """Should apply default rules to all commands"""
        registry.set_default(Authenticated())

        context_auth = AuthContext(user_id=42)
        context_anon = AuthContext()

        assert registry.check(context_auth, test_command)
        assert not registry.check(context_anon, test_command)

    def test_clear_command_rules(self, registry, test_command):
        """Should clear command-specific rules"""
        registry.register(test_command, RoleRequired("admin"))
        registry.clear(test_command)

        context = AuthContext()
        assert registry.check(context, test_command)

    def test_clear_all_rules(self, registry, test_command):
        """Should clear all rules"""
        registry.set_default(Authenticated())
        registry.register(test_command, RoleRequired("admin"))
        registry.clear()

        context = AuthContext()
        assert registry.check(context, test_command)


class TestDecorators:
    """Test authorization decorators"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset global registry before each test"""
        reset_global_registry()
        yield
        reset_global_registry()

    def test_requires_auth(self):
        """Should add authentication requirement"""
        @requires_auth
        class TestCommand:
            pass

        registry = get_global_registry()
        context_auth = AuthContext(user_id=42)
        context_anon = AuthContext()

        assert registry.check(context_auth, TestCommand)
        assert not registry.check(context_anon, TestCommand)

    def test_requires_role(self):
        """Should add role requirement"""
        @requires_role("admin")
        class TestCommand:
            pass

        registry = get_global_registry()
        context_admin = AuthContext(roles=["admin"])
        context_user = AuthContext(roles=["user"])

        assert registry.check(context_admin, TestCommand)
        assert not registry.check(context_user, TestCommand)

    def test_requires_all_roles(self):
        """Should add all-roles requirement"""
        @requires_all_roles("admin", "moderator")
        class TestCommand:
            pass

        registry = get_global_registry()
        context_both = AuthContext(roles=["admin", "moderator"])
        context_admin = AuthContext(roles=["admin"])

        assert registry.check(context_both, TestCommand)
        assert not registry.check(context_admin, TestCommand)

    def test_requires_permission(self):
        """Should add permission requirement"""
        @requires_permission("write")
        class TestCommand:
            pass

        registry = get_global_registry()
        context_write = AuthContext(permissions=["write"])
        context_read = AuthContext(permissions=["read"])

        assert registry.check(context_write, TestCommand)
        assert not registry.check(context_read, TestCommand)

    def test_requires_all_permissions(self):
        """Should add all-permissions requirement"""
        @requires_all_permissions("read", "write")
        class TestCommand:
            pass

        registry = get_global_registry()
        context_both = AuthContext(permissions=["read", "write"])
        context_read = AuthContext(permissions=["read"])

        assert registry.check(context_both, TestCommand)
        assert not registry.check(context_read, TestCommand)

    def test_requires_rules(self):
        """Should add custom rules"""
        def check(ctx, cmd):
            return ctx.user_id == 42

        @requires_rules(CustomRule(check))
        class TestCommand:
            pass

        registry = get_global_registry()
        context_42 = AuthContext(user_id=42)
        context_other = AuthContext(user_id=1)

        assert registry.check(context_42, TestCommand)
        assert not registry.check(context_other, TestCommand)

    def test_public_decorator(self):
        """Should mark command as public (documentation only)"""
        @public
        class TestCommand:
            pass

        # Public decorator doesn't add rules, just documents intent
        registry = get_global_registry()
        context = AuthContext()
        assert registry.check(context, TestCommand)

    def test_multiple_decorators(self):
        """Should stack multiple decorators"""
        @requires_auth
        @requires_role("admin")
        @requires_permission("write")
        class TestCommand:
            pass

        registry = get_global_registry()
        context_valid = AuthContext(
            user_id=42,
            roles=["admin"],
            permissions=["write"]
        )
        context_no_role = AuthContext(
            user_id=42,
            permissions=["write"]
        )

        assert registry.check(context_valid, TestCommand)
        assert not registry.check(context_no_role, TestCommand)
