"""Tests for Authentication Commands (Login/Logout)"""

import pytest
from datetime import datetime, timedelta

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

from foobara_py.domain.auth import (
    Login, LoginInputs, LoginResult,
    Logout, LogoutInputs, LogoutResult,
    RefreshToken, RefreshTokenInputs, RefreshTokenResult,
    hash_password,
)


class TestLogin:
    """Test Login command"""

    def test_login_requires_jwt(self):
        """Should require PyJWT"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

    def test_login_with_custom_user_finder(self):
        """Should login with custom user finder"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        # Create custom Login command
        class TestLogin(Login):
            jwt_secret = "test-secret"

            def find_user(self, username):
                if username == "john@example.com":
                    return {
                        "id": 123,
                        "username": "john",
                        "email": "john@example.com",
                        "password_hash": hash_password("secret123"),
                        "roles": ["user"],
                        "permissions": ["read", "write"]
                    }
                return None

        # Test successful login
        outcome = TestLogin.run(username="john@example.com", password="secret123")

        assert outcome.is_success()
        result = outcome.unwrap()
        assert isinstance(result, LoginResult)
        assert result.access_token is not None
        assert result.token_type == "Bearer"
        assert result.expires_in == 3600  # Default 1 hour
        assert result.user_id == 123

    def test_login_invalid_username(self):
        """Should fail on invalid username"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        class TestLogin(Login):
            def find_user(self, username):
                return None  # User not found

        outcome = TestLogin.run(username="unknown@example.com", password="password")

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("invalid_credentials" in error.symbol for error in errors)

    def test_login_invalid_password(self):
        """Should fail on invalid password"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        class TestLogin(Login):
            def find_user(self, username):
                return {
                    "id": 123,
                    "username": "john",
                    "password_hash": hash_password("correct-password")
                }

        outcome = TestLogin.run(username="john", password="wrong-password")

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("invalid_credentials" in error.symbol for error in errors)

    def test_login_with_remember_me(self):
        """Should extend token TTL with remember_me"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        class TestLogin(Login):
            jwt_secret = "test-secret"

            def find_user(self, username):
                return {
                    "id": 123,
                    "username": "john",
                    "password_hash": hash_password("password")
                }

        outcome = TestLogin.run(
            username="john",
            password="password",
            remember_me=True
        )

        assert outcome.is_success()
        result = outcome.unwrap()
        # Should be extended (3600 * 30 = 108000)
        assert result.expires_in == 108000
        assert result.refresh_token is not None

    def test_login_creates_valid_jwt_token(self):
        """Should create valid JWT token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        class TestLogin(Login):
            jwt_secret = "test-secret"

            def find_user(self, username):
                return {
                    "id": 123,
                    "username": "john",
                    "email": "john@example.com",
                    "password_hash": hash_password("password"),
                    "roles": ["admin"],
                    "permissions": ["read", "write", "delete"]
                }

        outcome = TestLogin.run(username="john", password="password")
        assert outcome.is_success()

        # Decode token
        token = outcome.unwrap().access_token
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])

        assert payload["sub"] == "123"
        assert payload["username"] == "john"
        assert payload["roles"] == ["admin"]
        assert payload["permissions"] == ["read", "write", "delete"]
        assert "exp" in payload
        assert "iat" in payload

    def test_login_token_expiration(self):
        """Should set correct token expiration"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        class TestLogin(Login):
            jwt_secret = "test-secret"
            access_token_ttl = 7200  # 2 hours

            def find_user(self, username):
                return {
                    "id": 123,
                    "username": "john",
                    "password_hash": hash_password("password")
                }

        outcome = TestLogin.run(username="john", password="password")
        assert outcome.is_success()

        result = outcome.unwrap()
        assert result.expires_in == 7200

        # Verify expiration in token
        token = result.access_token
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        difference = (exp_time - iat_time).total_seconds()
        assert abs(difference - 7200) < 5  # Within 5 seconds


class TestLogout:
    """Test Logout command"""

    def test_logout_with_valid_token(self):
        """Should logout with valid token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        # First, create a token
        secret = "test-secret"
        token = jwt.encode(
            {"sub": "123", "username": "john"},
            secret,
            algorithm="HS256"
        )

        class TestLogout(Logout):
            jwt_secret = secret

        outcome = TestLogout.run(token=token)

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.success is True
        assert result.tokens_revoked == 1

    def test_logout_with_invalid_token(self):
        """Should fail with invalid token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        class TestLogout(Logout):
            jwt_secret = "test-secret"

        outcome = TestLogout.run(token="invalid-token")

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("invalid_token" in error.symbol for error in errors)

    def test_logout_with_expired_token(self):
        """Should fail with expired token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        # Create expired token
        secret = "test-secret"
        token = jwt.encode(
            {
                "sub": "123",
                "exp": datetime.utcnow() - timedelta(hours=1)  # Expired
            },
            secret,
            algorithm="HS256"
        )

        class TestLogout(Logout):
            jwt_secret = secret

        outcome = TestLogout.run(token=token)

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("invalid_token" in error.symbol for error in errors)

    def test_logout_revoke_all_tokens(self):
        """Should revoke all user tokens"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"
        token = jwt.encode(
            {"sub": "123", "username": "john"},
            secret,
            algorithm="HS256"
        )

        class TestLogout(Logout):
            jwt_secret = secret

            def revoke_all_user_tokens(self, user_id):
                # Simulate revoking 3 tokens
                return 3

        outcome = TestLogout.run(token=token, revoke_all=True)

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.tokens_revoked == 3

    def test_logout_token_revocation(self):
        """Should add token to revoked list"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"
        token = jwt.encode(
            {"sub": "123"},
            secret,
            algorithm="HS256"
        )

        class TestLogout(Logout):
            jwt_secret = secret

        # Clear any previous revoked tokens
        if hasattr(TestLogout, '_revoked_tokens'):
            TestLogout._revoked_tokens.clear()

        outcome = TestLogout.run(token=token)
        assert outcome.is_success()

        # Check token was revoked
        assert hasattr(TestLogout, '_revoked_tokens')
        assert token in TestLogout._revoked_tokens


class TestRefreshToken:
    """Test RefreshToken command"""

    def test_refresh_token_success(self):
        """Should refresh token with valid refresh token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"
        refresh_token = jwt.encode(
            {
                "sub": "123",
                "type": "refresh",
                "exp": datetime.utcnow() + timedelta(days=30)
            },
            secret,
            algorithm="HS256"
        )

        class TestRefreshToken(RefreshToken):
            jwt_secret = secret

        outcome = TestRefreshToken.run(refresh_token=refresh_token)

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.access_token is not None
        assert result.expires_in == 3600

    def test_refresh_token_invalid(self):
        """Should fail with invalid refresh token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        class TestRefreshToken(RefreshToken):
            jwt_secret = "test-secret"

        outcome = TestRefreshToken.run(refresh_token="invalid-token")

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("invalid_refresh_token" in error.symbol for error in errors)

    def test_refresh_token_wrong_type(self):
        """Should fail if token is not a refresh token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"
        # Create access token, not refresh token
        access_token = jwt.encode(
            {
                "sub": "123",
                "username": "john",
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            secret,
            algorithm="HS256"
        )

        class TestRefreshToken(RefreshToken):
            jwt_secret = secret

        outcome = TestRefreshToken.run(refresh_token=access_token)

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("invalid_refresh_token" in error.symbol for error in errors)

    def test_refresh_token_creates_valid_jwt(self):
        """Should create valid JWT access token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"
        refresh_token = jwt.encode(
            {
                "sub": "123",
                "type": "refresh",
                "exp": datetime.utcnow() + timedelta(days=30)
            },
            secret,
            algorithm="HS256"
        )

        class TestRefreshToken(RefreshToken):
            jwt_secret = secret

        outcome = TestRefreshToken.run(refresh_token=refresh_token)
        assert outcome.is_success()

        # Decode new access token
        new_token = outcome.unwrap().access_token
        payload = jwt.decode(new_token, secret, algorithms=["HS256"])

        assert payload["sub"] == "123"
        assert "exp" in payload
        assert "iat" in payload

    def test_refresh_token_expired(self):
        """Should fail with expired refresh token"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"
        refresh_token = jwt.encode(
            {
                "sub": "123",
                "type": "refresh",
                "exp": datetime.utcnow() - timedelta(days=1)  # Expired
            },
            secret,
            algorithm="HS256"
        )

        class TestRefreshToken(RefreshToken):
            jwt_secret = secret

        outcome = TestRefreshToken.run(refresh_token=refresh_token)

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("invalid_refresh_token" in error.symbol for error in errors)


class TestAuthCommandIntegration:
    """Integration tests for auth commands"""

    def test_full_auth_flow(self):
        """Should handle complete login -> logout flow"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"

        class TestLogin(Login):
            jwt_secret = secret

            def find_user(self, username):
                if username == "john":
                    return {
                        "id": 123,
                        "username": "john",
                        "password_hash": hash_password("password")
                    }
                return None

        class TestLogout(Logout):
            jwt_secret = secret

        # Login
        login_outcome = TestLogin.run(username="john", password="password")
        assert login_outcome.is_success()
        token = login_outcome.unwrap().access_token

        # Verify token is valid
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        assert payload["sub"] == "123"

        # Logout
        logout_outcome = TestLogout.run(token=token)
        assert logout_outcome.is_success()

    def test_login_refresh_flow(self):
        """Should handle login with remember_me and token refresh"""
        if not JWT_AVAILABLE:
            pytest.skip("PyJWT not installed")

        secret = "test-secret"

        class TestLogin(Login):
            jwt_secret = secret

            def find_user(self, username):
                return {
                    "id": 123,
                    "username": "john",
                    "password_hash": hash_password("password")
                }

        class TestRefreshToken(RefreshToken):
            jwt_secret = secret

        # Login with remember_me
        login_outcome = TestLogin.run(
            username="john",
            password="password",
            remember_me=True
        )
        assert login_outcome.is_success()
        login_result = login_outcome.unwrap()
        assert login_result.refresh_token is not None

        # Refresh token
        refresh_outcome = TestRefreshToken.run(
            refresh_token=login_result.refresh_token
        )
        assert refresh_outcome.is_success()
        new_token = refresh_outcome.unwrap().access_token

        # Verify new token is valid
        payload = jwt.decode(new_token, secret, algorithms=["HS256"])
        assert payload["sub"] == "123"
