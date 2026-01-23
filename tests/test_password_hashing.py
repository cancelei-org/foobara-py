"""Tests for password hashing utilities"""

import pytest
from argon2 import PasswordHasher
from foobara_py.domain.auth import (
    hash_password,
    verify_password,
    needs_rehash,
    verify_and_rehash,
    PasswordHashingError,
    get_default_hasher,
)


class TestPasswordHashing:
    """Test password hashing functionality"""

    def test_hash_password_basic(self):
        """Should hash password successfully"""
        password = "my_secure_password"
        hashed = hash_password(password)

        # Check it's a valid Argon2 hash
        assert hashed.startswith("$argon2id$")
        assert len(hashed) > 50  # Argon2 hashes are long

    def test_hash_password_empty_raises_error(self):
        """Should raise error for empty password"""
        with pytest.raises(PasswordHashingError, match="Password cannot be empty"):
            hash_password("")

    def test_hash_password_different_each_time(self):
        """Should produce different hashes due to salt"""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Same password should produce different hashes (different salts)
        assert hash1 != hash2

    def test_hash_password_custom_hasher(self):
        """Should use custom hasher if provided"""
        custom_hasher = PasswordHasher(time_cost=1, memory_cost=8192)
        password = "test_password"

        hashed = hash_password(password, hasher=custom_hasher)

        # Should be able to verify with same hasher
        assert custom_hasher.verify(hashed, password)


class TestPasswordVerification:
    """Test password verification functionality"""

    def test_verify_password_correct(self):
        """Should verify correct password"""
        password = "my_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Should reject incorrect password"""
        password = "my_password"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Should be case sensitive"""
        password = "MyPassword"
        hashed = hash_password(password)

        assert verify_password("MyPassword", hashed) is True
        assert verify_password("mypassword", hashed) is False
        assert verify_password("MYPASSWORD", hashed) is False

    def test_verify_password_invalid_hash(self):
        """Should return False for invalid hash format"""
        assert verify_password("password", "not_a_valid_hash") is False
        assert verify_password("password", "") is False
        assert verify_password("password", "$invalid$hash") is False

    def test_verify_password_custom_hasher(self):
        """Should use custom hasher if provided"""
        custom_hasher = PasswordHasher(time_cost=1)
        password = "test_password"
        hashed = hash_password(password, hasher=custom_hasher)

        # Verify with same custom hasher
        assert verify_password(password, hashed, hasher=custom_hasher) is True

    def test_verify_password_empty_inputs(self):
        """Should handle empty inputs gracefully"""
        hashed = hash_password("password")

        assert verify_password("", hashed) is False


class TestNeedsRehash:
    """Test rehashing detection"""

    def test_needs_rehash_current_params(self):
        """Should not need rehash with current params"""
        password = "password"
        hashed = hash_password(password)

        # Hash with default params should not need rehash
        assert needs_rehash(hashed) is False

    def test_needs_rehash_outdated_params(self):
        """Should need rehash with outdated params"""
        # Create hash with weak params
        weak_hasher = PasswordHasher(time_cost=1, memory_cost=8192)
        password = "password"
        weak_hash = hash_password(password, hasher=weak_hasher)

        # Check with default (stronger) hasher
        assert needs_rehash(weak_hash) is True

    def test_needs_rehash_invalid_hash(self):
        """Should return True for invalid hash"""
        assert needs_rehash("invalid_hash") is True
        assert needs_rehash("") is True

    def test_needs_rehash_custom_hasher(self):
        """Should check against custom hasher params"""
        hasher1 = PasswordHasher(time_cost=1)
        hasher2 = PasswordHasher(time_cost=2)

        password = "password"
        hashed = hash_password(password, hasher=hasher1)

        # Same params - no rehash needed
        assert needs_rehash(hashed, hasher=hasher1) is False

        # Different params - rehash needed
        assert needs_rehash(hashed, hasher=hasher2) is True


class TestVerifyAndRehash:
    """Test combined verify and rehash functionality"""

    def test_verify_and_rehash_valid_current_hash(self):
        """Should verify without rehashing for current hash"""
        password = "my_password"
        hashed = hash_password(password)

        is_valid, new_hash = verify_and_rehash(password, hashed)

        assert is_valid is True
        assert new_hash is None  # No rehash needed

    def test_verify_and_rehash_valid_outdated_hash(self):
        """Should verify and provide new hash for outdated params"""
        # Create hash with weak params
        weak_hasher = PasswordHasher(time_cost=1, memory_cost=8192)
        password = "my_password"
        weak_hash = hash_password(password, hasher=weak_hasher)

        # Verify with default (stronger) hasher
        is_valid, new_hash = verify_and_rehash(password, weak_hash)

        assert is_valid is True
        assert new_hash is not None
        assert new_hash != weak_hash

        # New hash should verify
        assert verify_password(password, new_hash) is True

    def test_verify_and_rehash_invalid_password(self):
        """Should return False for wrong password"""
        password = "my_password"
        hashed = hash_password(password)

        is_valid, new_hash = verify_and_rehash("wrong_password", hashed)

        assert is_valid is False
        assert new_hash is None

    def test_verify_and_rehash_custom_hasher(self):
        """Should work with custom hasher"""
        hasher1 = PasswordHasher(time_cost=1)
        hasher2 = PasswordHasher(time_cost=2)

        password = "password"
        old_hash = hash_password(password, hasher=hasher1)

        # Verify with stronger hasher - should trigger rehash
        is_valid, new_hash = verify_and_rehash(password, old_hash, hasher=hasher2)

        assert is_valid is True
        assert new_hash is not None

        # New hash should work with hasher2
        assert verify_password(password, new_hash, hasher=hasher2) is True


class TestRealWorldScenarios:
    """Test real-world usage patterns"""

    def test_user_registration_flow(self):
        """Should handle typical user registration"""
        # User registers with password
        user_password = "SecureP@ssw0rd123"
        password_hash = hash_password(user_password)

        # Store password_hash in database (simulated)
        stored_hash = password_hash

        # User logs in later
        login_password = "SecureP@ssw0rd123"
        assert verify_password(login_password, stored_hash) is True

    def test_password_upgrade_flow(self):
        """Should handle password hash upgrades"""
        # User registered with old system
        old_hasher = PasswordHasher(time_cost=1, memory_cost=8192)
        password = "user_password"
        old_hash = hash_password(password, hasher=old_hasher)

        # System upgraded to stronger hashing
        # User logs in
        is_valid, new_hash = verify_and_rehash(password, old_hash)

        assert is_valid is True
        assert new_hash is not None

        # Update user's stored hash
        stored_hash = new_hash

        # Future logins use new hash
        assert verify_password(password, stored_hash) is True
        is_valid, rehash_again = verify_and_rehash(password, stored_hash)
        assert is_valid is True
        assert rehash_again is None  # No longer needs rehashing

    def test_failed_login_attempts(self):
        """Should handle failed login attempts"""
        password = "correct_password"
        hashed = hash_password(password)

        # Multiple wrong attempts
        assert verify_password("wrong1", hashed) is False
        assert verify_password("wrong2", hashed) is False
        assert verify_password("wrong3", hashed) is False

        # Correct password still works
        assert verify_password(password, hashed) is True

    def test_unicode_passwords(self):
        """Should handle unicode characters in passwords"""
        passwords = [
            "пароль",  # Russian
            "密码",  # Chinese
            "パスワード",  # Japanese
            "🔐🔑🗝️",  # Emojis
            "café",  # Accented characters
        ]

        for password in passwords:
            hashed = hash_password(password)
            assert verify_password(password, hashed) is True

    def test_long_passwords(self):
        """Should handle very long passwords"""
        # 100 character password
        long_password = "a" * 100
        hashed = hash_password(long_password)

        assert verify_password(long_password, hashed) is True
        assert verify_password(long_password[:-1], hashed) is False

    def test_special_characters_in_passwords(self):
        """Should handle special characters"""
        password = "p@$$w0rd!#%^&*()_+-=[]{}|;:',.<>?/~`"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True


class TestDefaultHasher:
    """Test default hasher functionality"""

    def test_get_default_hasher(self):
        """Should return singleton instance"""
        hasher1 = get_default_hasher()
        hasher2 = get_default_hasher()

        # Should be same instance
        assert hasher1 is hasher2

    def test_default_hasher_params(self):
        """Should have secure default parameters"""
        hasher = get_default_hasher()

        # Check params are set to secure defaults
        assert hasher.time_cost == 2
        assert hasher.memory_cost == 65536  # 64 MB
        assert hasher.parallelism == 4
        assert hasher.hash_len == 32
        assert hasher.salt_len == 16
