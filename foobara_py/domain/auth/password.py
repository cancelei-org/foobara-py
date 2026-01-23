"""
Password hashing utilities for Foobara Python.

Provides secure password hashing using Argon2id algorithm.
"""

from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError


class PasswordHashingError(Exception):
    """Base exception for password hashing errors."""

    pass


class PasswordVerificationError(Exception):
    """Raised when password verification fails."""

    pass


# Default password hasher using Argon2id
# Parameters chosen for security/performance balance
_default_hasher: Optional[PasswordHasher] = None


def get_default_hasher() -> PasswordHasher:
    """
    Get the default password hasher instance.

    Uses Argon2id with secure default parameters:
    - time_cost: 2 iterations
    - memory_cost: 65536 KB (64 MB)
    - parallelism: 4 threads
    - hash_len: 32 bytes
    - salt_len: 16 bytes

    Returns:
        PasswordHasher instance
    """
    global _default_hasher

    if _default_hasher is None:
        _default_hasher = PasswordHasher(
            time_cost=2,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )

    return _default_hasher


def hash_password(password: str, hasher: Optional[PasswordHasher] = None) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: Plain text password to hash
        hasher: Optional custom PasswordHasher instance (uses default if None)

    Returns:
        Hashed password string in PHC format

    Raises:
        PasswordHashingError: If hashing fails

    Example:
        >>> hashed = hash_password("my_secure_password")
        >>> print(hashed)
        $argon2id$v=19$m=65536,t=2,p=4$...
    """
    if not password:
        raise PasswordHashingError("Password cannot be empty")

    hasher = hasher or get_default_hasher()

    try:
        return hasher.hash(password)
    except Exception as e:
        raise PasswordHashingError(f"Failed to hash password: {e}") from e


def verify_password(
    password: str, hashed_password: str, hasher: Optional[PasswordHasher] = None
) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed_password: Hashed password to check against
        hasher: Optional custom PasswordHasher instance (uses default if None)

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("my_password")
        >>> verify_password("my_password", hashed)
        True
        >>> verify_password("wrong_password", hashed)
        False
    """
    hasher = hasher or get_default_hasher()

    try:
        hasher.verify(hashed_password, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False
    except Exception:
        return False


def needs_rehash(hashed_password: str, hasher: Optional[PasswordHasher] = None) -> bool:
    """
    Check if a password hash needs to be rehashed.

    Returns True if the hash uses outdated parameters and should be
    regenerated with current security settings.

    Args:
        hashed_password: Hashed password to check
        hasher: Optional custom PasswordHasher instance (uses default if None)

    Returns:
        True if hash should be regenerated, False otherwise

    Example:
        >>> hashed = hash_password("password")
        >>> needs_rehash(hashed)  # False with current params
        False

        # After updating hasher params, old hashes will need rehashing
        >>> custom_hasher = PasswordHasher(time_cost=3)
        >>> needs_rehash(hashed, custom_hasher)  # True with new params
        True
    """
    hasher = hasher or get_default_hasher()

    try:
        return hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True  # If we can't check, assume it needs rehashing


def verify_and_rehash(
    password: str, hashed_password: str, hasher: Optional[PasswordHasher] = None
) -> tuple[bool, Optional[str]]:
    """
    Verify password and return new hash if rehashing is needed.

    This is a convenience method for the common pattern of verifying
    a password and immediately rehashing if the hash uses outdated parameters.

    Args:
        password: Plain text password to verify
        hashed_password: Hashed password to check against
        hasher: Optional custom PasswordHasher instance (uses default if None)

    Returns:
        Tuple of (is_valid, new_hash)
        - is_valid: True if password matches
        - new_hash: New hash if rehashing needed, None otherwise

    Example:
        >>> hashed = hash_password("password")
        >>> is_valid, new_hash = verify_and_rehash("password", hashed)
        >>> if is_valid and new_hash:
        ...     # Update stored hash
        ...     user.password_hash = new_hash
        ...     user.save()
    """
    hasher = hasher or get_default_hasher()

    # Verify password
    is_valid = verify_password(password, hashed_password, hasher)

    if not is_valid:
        return False, None

    # Check if rehashing needed
    if needs_rehash(hashed_password, hasher):
        try:
            new_hash = hash_password(password, hasher)
            return True, new_hash
        except PasswordHashingError:
            return True, None

    return True, None
