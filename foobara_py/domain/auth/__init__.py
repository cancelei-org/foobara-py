"""
Auth domain for Foobara Python.

Provides authentication and authorization functionality including:
- Token management
- Password hashing and verification
- Login/Logout commands
"""

from foobara_py.domain.auth.commands import (
    Login,
    LoginInputs,
    LoginResult,
    Logout,
    LogoutInputs,
    LogoutResult,
    RefreshToken,
    RefreshTokenInputs,
    RefreshTokenResult,
)
from foobara_py.domain.auth.entities import Token
from foobara_py.domain.auth.password import (
    PasswordHashingError,
    PasswordVerificationError,
    get_default_hasher,
    hash_password,
    needs_rehash,
    verify_and_rehash,
    verify_password,
)

__all__ = [
    # Entities
    "Token",
    # Password utilities
    "hash_password",
    "verify_password",
    "needs_rehash",
    "verify_and_rehash",
    "PasswordHashingError",
    "PasswordVerificationError",
    "get_default_hasher",
    # Commands
    "Login",
    "LoginInputs",
    "LoginResult",
    "Logout",
    "LogoutInputs",
    "LogoutResult",
    "RefreshToken",
    "RefreshTokenInputs",
    "RefreshTokenResult",
]
