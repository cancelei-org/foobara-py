"""
Authentication commands for Login and Logout.

Provides commands for user authentication and session management.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from foobara_py.core.command import Command
from foobara_py.domain.auth.password import verify_password as verify_password_hash


class LoginInputs(BaseModel):
    """Inputs for Login command"""

    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(default=False, description="Extended session duration")


class LoginResult(BaseModel):
    """Result of successful login"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user_id: Any = Field(..., description="Authenticated user ID")


class Login(Command[LoginInputs, LoginResult]):
    """
    Login command for user authentication.

    Validates credentials and issues JWT tokens.

    Usage:
        outcome = Login.run(username="john@example.com", password="secret123")
        if outcome.is_success():
            print(f"Access token: {outcome.result.access_token}")

    To customize, subclass and override:
    - find_user(): Locate user by username/email
    - verify_password(): Verify password matches
    - create_access_token(): Generate JWT token
    - create_refresh_token(): Generate refresh token (optional)
    """

    _organization = "Foobara"
    _domain = "Auth"

    # Configuration
    access_token_ttl: int = 3600  # 1 hour in seconds
    refresh_token_ttl: int = 2592000  # 30 days in seconds
    remember_me_multiplier: int = 30  # Extend TTL by this factor

    def validate(self) -> None:
        """Validate credentials"""
        # Find user
        user = self.find_user(self.inputs.username)
        if not user:
            self.add_runtime_error("invalid_credentials", "Invalid username or password", halt=True)
            return

        # Verify password
        if not self.verify_password(self.inputs.password, user):
            self.add_runtime_error("invalid_credentials", "Invalid username or password", halt=True)
            return

        # Store user for execute phase
        self._user = user

    def execute(self) -> LoginResult:
        """Execute login and create tokens"""
        user = self._user

        # Calculate TTL
        ttl = self.access_token_ttl
        if self.inputs.remember_me:
            ttl *= self.remember_me_multiplier

        # Create tokens
        access_token = self.create_access_token(user, ttl)
        refresh_token = None
        if self.inputs.remember_me:
            refresh_token = self.create_refresh_token(user, self.refresh_token_ttl)

        return LoginResult(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ttl,
            user_id=user.get("id"),
        )

    # ==================== Override Methods ====================

    def find_user(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Find user by username or email.

        Override this method to integrate with your user storage.

        Args:
            username: Username or email to find

        Returns:
            User dict with id, username, password_hash, etc., or None

        Example:
            def find_user(self, username):
                from myapp.models import User
                user = User.query.filter_by(email=username).first()
                if user:
                    return {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "password_hash": user.password_hash,
                        "roles": user.roles,
                        "permissions": user.permissions
                    }
                return None
        """
        # Default implementation - override this
        return None

    def verify_password(self, password: str, user: Dict[str, Any]) -> bool:
        """
        Verify password matches user's password hash.

        Override for custom password verification.

        Args:
            password: Plain text password
            user: User dict with password_hash

        Returns:
            True if password matches, False otherwise

        Example:
            def verify_password(self, password, user):
                return bcrypt.checkpw(
                    password.encode(),
                    user["password_hash"].encode()
                )
        """
        try:
            return verify_password_hash(password, user.get("password_hash", ""))
        except Exception:
            return False

    def create_access_token(self, user: Dict[str, Any], ttl: int) -> str:
        """
        Create JWT access token.

        Override for custom token generation.

        Args:
            user: User dict
            ttl: Token TTL in seconds

        Returns:
            JWT token string

        Example:
            def create_access_token(self, user, ttl):
                import jwt
                from datetime import datetime, timedelta

                payload = {
                    "sub": str(user["id"]),
                    "username": user["username"],
                    "roles": user.get("roles", []),
                    "exp": datetime.utcnow() + timedelta(seconds=ttl)
                }
                return jwt.encode(payload, "your-secret-key", algorithm="HS256")
        """
        try:
            import jwt
        except ImportError:
            self.add_runtime_error(
                "jwt_not_available", "PyJWT package required for token generation", halt=True
            )
            return ""

        payload = {
            "sub": str(user.get("id")),
            "username": user.get("username", user.get("email", "")),
            "roles": user.get("roles", []),
            "permissions": user.get("permissions", []),
            "exp": datetime.utcnow() + timedelta(seconds=ttl),
            "iat": datetime.utcnow(),
        }

        # Override this secret in production
        secret = getattr(self, "jwt_secret", "default-secret-change-me")
        return jwt.encode(payload, secret, algorithm="HS256")

    def create_refresh_token(self, user: Dict[str, Any], ttl: int) -> str:
        """
        Create JWT refresh token.

        Override for custom refresh token generation.

        Args:
            user: User dict
            ttl: Token TTL in seconds

        Returns:
            JWT refresh token string
        """
        try:
            import jwt
        except ImportError:
            return ""

        payload = {
            "sub": str(user.get("id")),
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(seconds=ttl),
            "iat": datetime.utcnow(),
        }

        secret = getattr(self, "jwt_secret", "default-secret-change-me")
        return jwt.encode(payload, secret, algorithm="HS256")


class LogoutInputs(BaseModel):
    """Inputs for Logout command"""

    token: str = Field(..., description="Access token to revoke")
    revoke_all: bool = Field(default=False, description="Revoke all tokens for this user")


class LogoutResult(BaseModel):
    """Result of successful logout"""

    success: bool = Field(default=True, description="Logout successful")
    tokens_revoked: int = Field(default=1, description="Number of tokens revoked")


class Logout(Command[LogoutInputs, LogoutResult]):
    """
    Logout command for session termination.

    Revokes tokens and ends user session.

    Usage:
        outcome = Logout.run(token="<jwt-token>")
        if outcome.is_success():
            print("Logged out successfully")

    To customize, subclass and override:
    - decode_token(): Decode and validate JWT
    - revoke_token(): Revoke single token
    - revoke_all_user_tokens(): Revoke all user tokens
    """

    _organization = "Foobara"
    _domain = "Auth"

    def validate(self) -> None:
        """Validate token"""
        # Decode token to get user ID
        user_id = self.decode_token(self.inputs.token)
        if not user_id:
            self.add_runtime_error("invalid_token", "Invalid or expired token", halt=True)
            return

        self._user_id = user_id

    def execute(self) -> LogoutResult:
        """Execute logout"""
        if self.inputs.revoke_all:
            # Revoke all tokens for user
            count = self.revoke_all_user_tokens(self._user_id)
        else:
            # Revoke single token
            self.revoke_token(self.inputs.token)
            count = 1

        return LogoutResult(success=True, tokens_revoked=count)

    # ==================== Override Methods ====================

    def decode_token(self, token: str) -> Optional[Any]:
        """
        Decode and validate JWT token.

        Override for custom token validation.

        Args:
            token: JWT token string

        Returns:
            User ID if valid, None otherwise

        Example:
            def decode_token(self, token):
                import jwt
                try:
                    payload = jwt.decode(
                        token,
                        "your-secret-key",
                        algorithms=["HS256"]
                    )
                    return payload["sub"]
                except jwt.InvalidTokenError:
                    return None
        """
        try:
            import jwt
        except ImportError:
            return None

        try:
            secret = getattr(self, "jwt_secret", "default-secret-change-me")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload.get("sub")
        except jwt.InvalidTokenError:
            return None

    def revoke_token(self, token: str) -> None:
        """
        Revoke a single token.

        Override to integrate with your token storage.

        Args:
            token: Token to revoke

        Example:
            def revoke_token(self, token):
                from myapp.models import RevokedToken
                RevokedToken.create(token=token, revoked_at=datetime.utcnow())
        """
        # Default implementation - store in-memory (not persistent)
        # Override this for production use
        if not hasattr(self.__class__, "_revoked_tokens"):
            self.__class__._revoked_tokens = set()
        self.__class__._revoked_tokens.add(token)

    def revoke_all_user_tokens(self, user_id: Any) -> int:
        """
        Revoke all tokens for a user.

        Override to integrate with your token storage.

        Args:
            user_id: User ID

        Returns:
            Number of tokens revoked

        Example:
            def revoke_all_user_tokens(self, user_id):
                from myapp.models import Token
                tokens = Token.query.filter_by(user_id=user_id, revoked=False).all()
                for token in tokens:
                    token.revoked = True
                db.session.commit()
                return len(tokens)
        """
        # Default implementation - return 1
        # Override this for production use
        self.revoke_token(self.inputs.token)
        return 1


class RefreshTokenInputs(BaseModel):
    """Inputs for RefreshToken command"""

    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResult(BaseModel):
    """Result of token refresh"""

    access_token: str = Field(..., description="New access token")
    expires_in: int = Field(..., description="Token expiration in seconds")


class RefreshToken(Command[RefreshTokenInputs, RefreshTokenResult]):
    """
    Refresh access token using refresh token.

    Issues new access token without requiring credentials.

    Usage:
        outcome = RefreshToken.run(refresh_token="<refresh-token>")
        if outcome.is_success():
            print(f"New token: {outcome.result.access_token}")
    """

    _organization = "Foobara"
    _domain = "Auth"

    access_token_ttl: int = 3600  # 1 hour

    def validate(self) -> None:
        """Validate refresh token"""
        user_info = self.decode_refresh_token(self.inputs.refresh_token)
        if not user_info:
            self.add_runtime_error(
                "invalid_refresh_token", "Invalid or expired refresh token", halt=True
            )
            return

        self._user_id = user_info.get("sub")

    def execute(self) -> RefreshTokenResult:
        """Execute token refresh"""
        # Create new access token
        access_token = self.create_access_token(self._user_id, self.access_token_ttl)

        return RefreshTokenResult(access_token=access_token, expires_in=self.access_token_ttl)

    def decode_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate refresh token"""
        try:
            import jwt
        except ImportError:
            return None

        try:
            secret = getattr(self, "jwt_secret", "default-secret-change-me")
            payload = jwt.decode(token, secret, algorithms=["HS256"])

            # Verify it's a refresh token
            if payload.get("type") != "refresh":
                return None

            return payload
        except jwt.InvalidTokenError:
            return None

    def create_access_token(self, user_id: Any, ttl: int) -> str:
        """Create new access token"""
        try:
            import jwt
        except ImportError:
            self.add_runtime_error("jwt_not_available", "PyJWT package required", halt=True)
            return ""

        payload = {
            "sub": str(user_id),
            "exp": datetime.utcnow() + timedelta(seconds=ttl),
            "iat": datetime.utcnow(),
        }

        secret = getattr(self, "jwt_secret", "default-secret-change-me")
        return jwt.encode(payload, secret, algorithm="HS256")
