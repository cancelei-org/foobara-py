"""Tests for serializers system"""

import pytest
from pydantic import BaseModel

from foobara_py.serializers import (
    Serializer,
    SerializerRegistry,
    AggregateSerializer,
    AtomicSerializer,
    EntitiesToPrimaryKeysSerializer,
    ErrorsSerializer
)
from foobara_py.persistence.entity import EntityBase, Model
from foobara_py.core.errors import FoobaraError, ErrorCollection


# Test entities and models
class Address(Model):
    street: str
    city: str
    country: str


class User(EntityBase):
    _primary_key_field = 'id'

    id: int
    name: str
    email: str
    address: Address = None


class Post(EntityBase):
    _primary_key_field = 'id'

    id: int
    title: str
    content: str
    author_id: int = None
    author: User = None


class Comment(EntityBase):
    _primary_key_field = 'id'

    id: int
    text: str
    post_id: int = None
    post: Post = None
    user_id: int = None
    user: User = None


class TestSerializerBase:
    """Test Serializer base class"""

    def test_custom_serializer(self):
        """Should create custom serializer"""

        class SimpleModel(BaseModel):
            value: int

        class SimpleSerializer(Serializer[SimpleModel]):
            def serialize(self, obj: SimpleModel) -> dict:
                return {"val": obj.value * 2}

            def deserialize(self, data: dict) -> SimpleModel:
                return SimpleModel(value=data["val"] // 2)

        model = SimpleModel(value=10)
        serializer = SimpleSerializer()

        # Serialize
        result = serializer.serialize(model)
        assert result == {"val": 20}

        # Deserialize
        original = serializer.deserialize(result)
        assert original.value == 10


class TestSerializerRegistry:
    """Test SerializerRegistry"""

    def setup_method(self):
        """Clear registry before each test"""
        # Don't clear - we need the auto-registered serializers
        pass

    def test_register_serializer(self):
        """Should register serializer"""

        class TestSerializer(Serializer[str]):
            def serialize(self, obj: str) -> str:
                return obj.upper()

        SerializerRegistry.register(TestSerializer)

        serializer = SerializerRegistry.get("TestSerializer")
        assert serializer == TestSerializer

    def test_find_serializer(self):
        """Should find appropriate serializer"""
        user = User(id=1, name="Test", email="test@example.com")

        # Should find AtomicSerializer (higher priority for entities)
        serializer = SerializerRegistry.find_serializer(user)
        assert serializer == AtomicSerializer

    def test_auto_serialize(self):
        """Should automatically select and use serializer"""
        user = User(id=1, name="Test", email="test@example.com")

        data = SerializerRegistry.serialize(user)

        assert data["id"] == 1
        assert data["name"] == "Test"
        assert data["email"] == "test@example.com"


class TestAggregateSerializer:
    """Test AggregateSerializer"""

    def test_serialize_simple_entity(self):
        """Should serialize entity with all fields"""
        address = Address(street="123 Main St", city="NYC", country="USA")
        user = User(id=1, name="John", email="john@example.com", address=address)

        serializer = AggregateSerializer()
        data = serializer.serialize(user)

        assert data["id"] == 1
        assert data["name"] == "John"
        assert data["email"] == "john@example.com"
        assert data["address"] == {
            "street": "123 Main St",
            "city": "NYC",
            "country": "USA"
        }

    def test_serialize_nested_entities(self):
        """Should serialize nested entities fully"""
        user = User(id=1, name="John", email="john@example.com")
        post = Post(id=10, title="Test Post", content="Content", author=user)

        serializer = AggregateSerializer()
        data = serializer.serialize(post)

        assert data["id"] == 10
        assert data["title"] == "Test Post"
        assert data["author"]["id"] == 1
        assert data["author"]["name"] == "John"

    def test_serialize_list_of_entities(self):
        """Should serialize list of entities"""
        user = User(id=1, name="John", email="john@example.com")
        post1 = Post(id=10, title="Post 1", content="Content 1")
        post2 = Post(id=20, title="Post 2", content="Content 2")

        # Simulate user with posts
        class UserWithPosts(EntityBase):
            _primary_key_field = 'id'
            id: int
            name: str
            posts: list = []

        user_with_posts = UserWithPosts(id=1, name="John", posts=[post1, post2])

        serializer = AggregateSerializer()
        data = serializer.serialize(user_with_posts)

        assert len(data["posts"]) == 2
        assert data["posts"][0]["id"] == 10
        assert data["posts"][1]["id"] == 20


class TestAtomicSerializer:
    """Test AtomicSerializer"""

    def test_serialize_entity_with_pk_only(self):
        """Should serialize entity associations as primary keys"""
        user = User(id=1, name="John", email="john@example.com")
        post = Post(id=10, title="Test Post", content="Content", author=user, author_id=1)

        serializer = AtomicSerializer()
        data = serializer.serialize(post)

        assert data["id"] == 10
        assert data["title"] == "Test Post"
        assert data["author"] == 1  # Primary key, not full object
        assert data["author_id"] == 1

    def test_serialize_model_fully(self):
        """Should serialize non-entity models fully"""
        address = Address(street="123 Main St", city="NYC", country="USA")
        user = User(id=1, name="John", email="john@example.com", address=address)

        serializer = AtomicSerializer()
        data = serializer.serialize(user)

        # Address is a Model (not Entity), so it's serialized fully
        assert data["address"] == {
            "street": "123 Main St",
            "city": "NYC",
            "country": "USA"
        }

    def test_serialize_list_of_entities_as_pks(self):
        """Should serialize list of entities as list of PKs"""
        post1 = Post(id=10, title="Post 1", content="Content 1")
        post2 = Post(id=20, title="Post 2", content="Content 2")

        class UserWithPosts(EntityBase):
            _primary_key_field = 'id'
            id: int
            name: str
            posts: list = []

        user = UserWithPosts(id=1, name="John", posts=[post1, post2])

        serializer = AtomicSerializer()
        data = serializer.serialize(user)

        assert data["posts"] == [10, 20]  # List of primary keys


class TestEntitiesToPrimaryKeysSerializer:
    """Test EntitiesToPrimaryKeysSerializer"""

    def test_convert_single_entity(self):
        """Should convert entity to primary key"""
        user = User(id=1, name="John", email="john@example.com")

        serializer = EntitiesToPrimaryKeysSerializer()
        result = serializer.serialize(user)

        assert result == 1

    def test_convert_nested_dict(self):
        """Should recursively convert entities in dict"""
        user = User(id=1, name="John", email="john@example.com")
        post = Post(id=10, title="Test", content="Content")

        data = {
            "user": user,
            "post": post,
            "count": 5
        }

        serializer = EntitiesToPrimaryKeysSerializer()
        result = serializer.serialize(data)

        assert result == {
            "user": 1,
            "post": 10,
            "count": 5
        }

    def test_convert_nested_list(self):
        """Should recursively convert entities in list"""
        users = [
            User(id=1, name="John", email="john@example.com"),
            User(id=2, name="Jane", email="jane@example.com"),
            User(id=3, name="Bob", email="bob@example.com")
        ]

        serializer = EntitiesToPrimaryKeysSerializer()
        result = serializer.serialize(users)

        assert result == [1, 2, 3]

    def test_convert_deeply_nested(self):
        """Should handle deeply nested structures"""
        user1 = User(id=1, name="John", email="john@example.com")
        user2 = User(id=2, name="Jane", email="jane@example.com")
        post1 = Post(id=10, title="Post 1", content="Content")
        post2 = Post(id=20, title="Post 2", content="Content")

        data = {
            "users": [user1, user2],
            "posts": {
                "first": post1,
                "second": post2
            },
            "metadata": {
                "author": user1,
                "count": 2
            }
        }

        serializer = EntitiesToPrimaryKeysSerializer()
        result = serializer.serialize(data)

        assert result == {
            "users": [1, 2],
            "posts": {
                "first": 10,
                "second": 20
            },
            "metadata": {
                "author": 1,
                "count": 2
            }
        }

    def test_convert_pydantic_model(self):
        """Should convert Pydantic models to dict first"""
        address = Address(street="123 Main St", city="NYC", country="USA")

        serializer = EntitiesToPrimaryKeysSerializer()
        result = serializer.serialize(address)

        assert result == {
            "street": "123 Main St",
            "city": "NYC",
            "country": "USA"
        }


class TestErrorsSerializer:
    """Test ErrorsSerializer"""

    def test_serialize_single_error(self):
        """Should serialize single error"""
        error = FoobaraError.data_error(
            "invalid_email",
            ["user", "email"],
            "Email is invalid"
        )

        serializer = ErrorsSerializer()
        data = serializer.serialize(error)

        assert "errors" in data
        assert len(data["errors"]) == 1
        assert data["errors"][0]["symbol"] == "invalid_email"
        assert data["errors"][0]["path"] == ["user", "email"]
        assert data["errors"][0]["message"] == "Email is invalid"
        assert data["errors"][0]["category"] == "data"

    def test_serialize_error_collection(self):
        """Should serialize error collection"""
        errors = ErrorCollection()
        errors.add(FoobaraError.data_error("invalid_email", ["email"], "Invalid"))
        errors.add(FoobaraError.data_error("too_short", ["name"], "Too short"))

        serializer = ErrorsSerializer()
        data = serializer.serialize(errors)

        assert len(data["errors"]) == 2
        assert data["errors"][0]["symbol"] == "invalid_email"
        assert data["errors"][1]["symbol"] == "too_short"

    def test_serialize_with_runtime_path(self):
        """Should include runtime path in key"""
        error = FoobaraError(
            category="data",
            symbol="invalid_value",
            path=("field",),
            message="Invalid",
            runtime_path=("create_user", "validate_inputs")
        )

        serializer = ErrorsSerializer()
        data = serializer.serialize(error)

        # Key should be runtime_path.symbol
        assert data["errors"][0]["key"] == "create_user.validate_inputs.invalid_value"
        assert data["errors"][0]["runtime_path"] == ["create_user", "validate_inputs"]

    def test_serialize_with_context(self):
        """Should include error context"""
        error = FoobaraError.data_error(
            "out_of_range",
            ["age"],
            "Age out of range",
            min=0,
            max=120,
            actual=150
        )

        serializer = ErrorsSerializer()
        data = serializer.serialize(error)

        assert data["errors"][0]["context"] == {
            "min": 0,
            "max": 120,
            "actual": 150
        }

    def test_ruby_compatible_format(self):
        """Should produce Ruby Foobara-compatible format"""
        error = FoobaraError.runtime_error(
            "database_connection_failed",
            "Could not connect to database",
            host="localhost",
            port=5432
        )

        serializer = ErrorsSerializer()
        data = serializer.serialize(error)

        # Check all required Ruby fields are present
        error_data = data["errors"][0]
        assert "key" in error_data
        assert "path" in error_data
        assert "runtime_path" in error_data
        assert "category" in error_data
        assert "symbol" in error_data
        assert "message" in error_data
        assert "context" in error_data
        assert "is_fatal" in error_data

        assert error_data["category"] == "runtime"
        assert error_data["symbol"] == "database_connection_failed"
