"""Tests for sensitive types"""

import pytest
import json
from pydantic import BaseModel, ValidationError
from foobara_py.types import (
    Sensitive,
    SensitiveStr,
    Password,
    APIKey,
    SecretToken,
    BearerToken,
    SensitiveModel,
    is_sensitive,
    get_sensitive_fields,
    redact_dict,
)


class TestSensitiveWrapper:
    """Test Sensitive wrapper class"""

    def test_create_sensitive(self):
        """Should create sensitive value"""
        secret = Sensitive("my_secret")
        assert secret.get() == "my_secret"

    def test_redacted_repr(self):
        """Should redact in repr"""
        secret = Sensitive("my_secret")
        assert repr(secret) == "[REDACTED]"

    def test_redacted_str(self):
        """Should redact in str"""
        secret = Sensitive("my_secret")
        assert str(secret) == "[REDACTED]"

    def test_equality(self):
        """Should compare values correctly"""
        secret1 = Sensitive("value")
        secret2 = Sensitive("value")
        secret3 = Sensitive("other")

        assert secret1 == secret2
        assert secret1 != secret3
        assert secret1 == "value"  # Can compare with raw value

    def test_hash(self):
        """Should be hashable"""
        secret1 = Sensitive("value")
        secret2 = Sensitive("value")

        # Can be used in sets/dicts
        sensitive_set = {secret1, secret2}
        assert len(sensitive_set) == 1  # Same value

    def test_bool_conversion(self):
        """Should convert to bool based on value"""
        assert bool(Sensitive("value")) is True
        assert bool(Sensitive("")) is False
        assert bool(Sensitive(0)) is False
        assert bool(Sensitive(1)) is True

    def test_immutable(self):
        """Should be immutable"""
        secret = Sensitive("value")

        with pytest.raises(AttributeError):
            secret._value = "new"

        with pytest.raises(AttributeError):
            del secret._value

    def test_type_generic(self):
        """Should work with different types"""
        int_secret = Sensitive(42)
        assert int_secret.get() == 42

        dict_secret = Sensitive({"key": "value"})
        assert dict_secret.get() == {"key": "value"}


class TestSensitiveWithPydantic:
    """Test Sensitive integration with Pydantic"""

    def test_pydantic_field(self):
        """Should work as Pydantic field"""
        class User(BaseModel):
            email: str
            password: Sensitive[str]

        user = User(email="john@example.com", password="secret123")

        assert user.email == "john@example.com"
        assert user.password.get() == "secret123"
        assert str(user.password) == "[REDACTED]"

    def test_pydantic_validation(self):
        """Should validate inner type"""
        class Config(BaseModel):
            api_key: Sensitive[str]
            max_retries: Sensitive[int]

        config = Config(api_key="key123", max_retries=5)

        assert config.api_key.get() == "key123"
        assert config.max_retries.get() == 5

    def test_pydantic_from_dict(self):
        """Should load from dict"""
        class User(BaseModel):
            email: str
            password: Sensitive[str]

        data = {"email": "john@example.com", "password": "secret123"}
        user = User(**data)

        assert user.password.get() == "secret123"

    def test_pydantic_model_dump_default(self):
        """Should dump model (raw values by default)"""
        class User(BaseModel):
            email: str
            password: Sensitive[str]

        user = User(email="john@example.com", password="secret123")
        data = user.model_dump()

        # Pydantic model_dump shows the Sensitive object
        assert data['email'] == "john@example.com"
        assert isinstance(data['password'], Sensitive)


class TestSensitiveModel:
    """Test SensitiveModel base class"""

    def test_model_dump_redacts_by_default(self):
        """Should redact sensitive fields by default"""
        class User(SensitiveModel):
            email: str
            password: Sensitive[str]
            api_key: Sensitive[str]

        user = User(
            email="john@example.com",
            password="secret123",
            api_key="key456"
        )

        data = user.model_dump()

        assert data['email'] == "john@example.com"
        assert data['password'] == "[REDACTED]"
        assert data['api_key'] == "[REDACTED]"

    def test_model_dump_include_sensitive(self):
        """Should include sensitive values when requested"""
        class User(SensitiveModel):
            email: str
            password: Sensitive[str]

        user = User(email="john@example.com", password="secret123")
        data = user.model_dump(include_sensitive=True)

        assert data['email'] == "john@example.com"
        assert data['password'].get() == "secret123"

    def test_model_dump_sensitive(self):
        """Should expose actual sensitive values via model_dump_sensitive"""
        class User(SensitiveModel):
            email: str
            password: Sensitive[str]

        user = User(email="john@example.com", password="secret123")
        data = user.model_dump_sensitive()

        assert data['password'].get() == "secret123"

    def test_model_dump_json_redacts(self):
        """Should redact sensitive fields in JSON"""
        class User(SensitiveModel):
            email: str
            password: Sensitive[str]

        user = User(email="john@example.com", password="secret123")
        json_str = user.model_dump_json()

        data = json.loads(json_str)
        assert data['password'] == "[REDACTED]"

    def test_nested_redaction(self):
        """Should redact nested sensitive values"""
        class Address(SensitiveModel):
            street: str
            access_code: Sensitive[str]

        class User(SensitiveModel):
            name: str
            address: Address

        # Note: Pydantic will need proper setup for nested models
        # This test shows the intent but may need adjustment
        user = User(
            name="John",
            address=Address(street="123 Main St", access_code="1234")
        )

        data = user.model_dump()
        assert data['address']['access_code'] == "[REDACTED]"


class TestTypeAliases:
    """Test type aliases (Password, APIKey, etc.)"""

    def test_password_alias(self):
        """Should use Password alias"""
        class User(BaseModel):
            email: str
            password: Password

        user = User(email="john@example.com", password="secret123")
        assert user.password.get() == "secret123"

    def test_api_key_alias(self):
        """Should use APIKey alias"""
        class Config(BaseModel):
            endpoint: str
            api_key: APIKey

        config = Config(endpoint="https://api.example.com", api_key="key123")
        assert config.api_key.get() == "key123"

    def test_secret_token_alias(self):
        """Should use SecretToken alias"""
        class Session(BaseModel):
            user_id: int
            token: SecretToken

        session = Session(user_id=1, token="token123")
        assert session.token.get() == "token123"

    def test_bearer_token_alias(self):
        """Should use BearerToken alias"""
        class AuthHeader(BaseModel):
            bearer_token: BearerToken

        header = AuthHeader(bearer_token="bearer123")
        assert header.bearer_token.get() == "bearer123"


class TestUtilityFunctions:
    """Test utility functions"""

    def test_is_sensitive(self):
        """Should detect sensitive values"""
        assert is_sensitive(Sensitive("value")) is True
        assert is_sensitive("value") is False
        assert is_sensitive(42) is False

    def test_get_sensitive_fields(self):
        """Should identify sensitive fields in model"""
        class User(BaseModel):
            email: str
            password: Sensitive[str]
            name: str
            api_key: Sensitive[str]
            age: int

        fields = get_sensitive_fields(User)
        assert set(fields) == {'password', 'api_key'}

    def test_get_sensitive_fields_with_aliases(self):
        """Should identify sensitive fields with type aliases"""
        class User(BaseModel):
            email: str
            password: Password

        fields = get_sensitive_fields(User)
        assert 'password' in fields

    def test_redact_dict_common_keys(self):
        """Should redact common sensitive keys"""
        data = {
            "username": "john",
            "password": "secret123",
            "email": "john@example.com",
            "api_key": "key456",
            "token": "token789"
        }

        redacted = redact_dict(data)

        assert redacted['username'] == "john"
        assert redacted['email'] == "john@example.com"
        assert redacted['password'] == "[REDACTED]"
        assert redacted['api_key'] == "[REDACTED]"
        assert redacted['token'] == "[REDACTED]"

    def test_redact_dict_custom_keys(self):
        """Should redact custom sensitive keys"""
        data = {
            "name": "John",
            "ssn": "123-45-6789",
            "phone": "555-1234"
        }

        redacted = redact_dict(data, sensitive_keys=['ssn', 'phone'])

        assert redacted['name'] == "John"
        assert redacted['ssn'] == "[REDACTED]"
        assert redacted['phone'] == "[REDACTED]"

    def test_redact_dict_nested(self):
        """Should redact nested dictionaries"""
        data = {
            "user": {
                "name": "John",
                "password": "secret"
            },
            "config": {
                "timeout": 30,
                "api_key": "key123"
            }
        }

        redacted = redact_dict(data)

        assert redacted['user']['name'] == "John"
        assert redacted['user']['password'] == "[REDACTED]"
        assert redacted['config']['timeout'] == 30
        assert redacted['config']['api_key'] == "[REDACTED]"

    def test_redact_dict_with_lists(self):
        """Should handle lists in dictionaries"""
        data = {
            "users": [
                {"name": "John", "password": "secret1"},
                {"name": "Jane", "password": "secret2"}
            ]
        }

        redacted = redact_dict(data)

        assert redacted['users'][0]['name'] == "John"
        assert redacted['users'][0]['password'] == "[REDACTED]"
        assert redacted['users'][1]['name'] == "Jane"
        assert redacted['users'][1]['password'] == "[REDACTED]"

    def test_redact_dict_case_insensitive(self):
        """Should redact case-insensitively"""
        data = {
            "Password": "secret",
            "API_KEY": "key",
            "AccessToken": "token"
        }

        redacted = redact_dict(data)

        assert redacted['Password'] == "[REDACTED]"
        assert redacted['API_KEY'] == "[REDACTED]"
        assert redacted['AccessToken'] == "[REDACTED]"


class TestRealWorldScenarios:
    """Test real-world usage scenarios"""

    def test_api_config(self):
        """Should handle API configuration safely"""
        class APIConfig(SensitiveModel):
            endpoint: str
            api_key: APIKey
            timeout: int

        config = APIConfig(
            endpoint="https://api.example.com",
            api_key="sk-123456789",
            timeout=30
        )

        # Safe logging
        log_data = config.model_dump()
        assert log_data['api_key'] == "[REDACTED]"

        # Actual usage
        actual_key = config.api_key.get()
        assert actual_key == "sk-123456789"

    def test_user_credentials(self):
        """Should handle user credentials safely"""
        class LoginRequest(SensitiveModel):
            username: str
            password: Password

        request = LoginRequest(username="john", password="secret123")

        # Logging request should redact password
        print(f"Login attempt: {request.model_dump()}")
        # Output: {'username': 'john', 'password': '[REDACTED]'}

        # Actual authentication uses real password
        assert request.password.get() == "secret123"

    def test_error_messages_safe(self):
        """Should not leak sensitive data in error messages"""
        class User(SensitiveModel):
            email: str
            password: Password

        user = User(email="john@example.com", password="secret123")

        # Even if user object is included in error, password is redacted
        error_context = {
            "user": user.model_dump(),
            "error": "Authentication failed"
        }

        assert error_context['user']['password'] == "[REDACTED]"
