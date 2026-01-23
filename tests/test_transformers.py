"""Tests for transformers system"""

import pytest
from pydantic import BaseModel

from foobara_py.transformers import (
    Transformer,
    TransformerPipeline,
    TransformerRegistry,
    EntityToPrimaryKeyInputsTransformer,
    NormalizeKeysTransformer,
    StripWhitespaceTransformer,
    DefaultValuesTransformer,
    RemoveNullValuesTransformer,
    ResultToJsonTransformer,
    EntityToPrimaryKeyResultTransformer,
    PaginationTransformer,
    AuthErrorsTransformer,
    UserFriendlyErrorsTransformer,
    StripRuntimePathTransformer,
    GroupErrorsByPathTransformer
)
from foobara_py.persistence.entity import EntityBase
from foobara_py.core.errors import FoobaraError, ErrorCollection


# Test entities
class User(EntityBase):
    _primary_key_field = 'id'
    id: int
    name: str
    email: str


class Post(EntityBase):
    _primary_key_field = 'id'
    id: int
    title: str
    content: str


class TestTransformerBase:
    """Test base transformer functionality"""

    def test_custom_transformer(self):
        """Should create and use custom transformer"""

        class UppercaseTransformer(Transformer[str]):
            def transform(self, value: str) -> str:
                return value.upper()

        transformer = UppercaseTransformer()
        result = transformer.transform("hello")

        assert result == "HELLO"

    def test_transformer_callable(self):
        """Should be callable as function"""

        class DoubleTransformer(Transformer[int]):
            def transform(self, value: int) -> int:
                return value * 2

        transformer = DoubleTransformer()
        result = transformer(5)

        assert result == 10


class TestTransformerPipeline:
    """Test TransformerPipeline"""

    def test_pipeline_execution(self):
        """Should execute transformers in sequence"""

        class AddOneTransformer(Transformer[int]):
            def transform(self, value: int) -> int:
                return value + 1

        class DoubleTransformer(Transformer[int]):
            def transform(self, value: int) -> int:
                return value * 2

        pipeline = TransformerPipeline(
            AddOneTransformer(),
            DoubleTransformer()
        )

        result = pipeline.transform(5)  # (5 + 1) * 2 = 12
        assert result == 12

    def test_pipeline_add(self):
        """Should add transformer to pipeline"""

        class AddOneTransformer(Transformer[int]):
            def transform(self, value: int) -> int:
                return value + 1

        pipeline = TransformerPipeline()
        pipeline.add(AddOneTransformer())

        result = pipeline.transform(5)
        assert result == 6

    def test_pipeline_prepend(self):
        """Should prepend transformer to pipeline"""

        class AddOneTransformer(Transformer[int]):
            def transform(self, value: int) -> int:
                return value + 1

        class DoubleTransformer(Transformer[int]):
            def transform(self, value: int) -> int:
                return value * 2

        pipeline = TransformerPipeline(AddOneTransformer())
        pipeline.prepend(DoubleTransformer())

        result = pipeline.transform(5)  # (5 * 2) + 1 = 11
        assert result == 11


class TestTransformerRegistry:
    """Test TransformerRegistry"""

    def setup_method(self):
        """Clear registry before each test"""
        TransformerRegistry.clear()

    def test_register_transformer(self):
        """Should register transformer"""

        class TestTransformer(Transformer[str]):
            def transform(self, value: str) -> str:
                return value

        TransformerRegistry.register("test", TestTransformer, "test_category")

        assert TransformerRegistry.get("test") == TestTransformer

    def test_by_category(self):
        """Should retrieve transformers by category"""

        class Trans1(Transformer[str]):
            def transform(self, value: str) -> str:
                return value

        class Trans2(Transformer[str]):
            def transform(self, value: str) -> str:
                return value

        TransformerRegistry.register("trans1", Trans1, "input")
        TransformerRegistry.register("trans2", Trans2, "input")

        input_transformers = TransformerRegistry.by_category("input")
        assert len(input_transformers) == 2
        assert Trans1 in input_transformers
        assert Trans2 in input_transformers


class TestInputTransformers:
    """Test input transformers"""

    def test_entity_to_pk_transformer(self):
        """Should convert entities to primary keys"""
        user = User(id=1, name="John", email="john@example.com")
        post = Post(id=10, title="Test", content="Content")

        inputs = {
            "user": user,
            "post": post,
            "name": "Test"
        }

        transformer = EntityToPrimaryKeyInputsTransformer()
        result = transformer.transform(inputs)

        assert result["user"] == 1
        assert result["post"] == 10
        assert result["name"] == "Test"

    def test_entity_to_pk_with_list(self):
        """Should handle lists of entities"""
        users = [
            User(id=1, name="John", email="john@example.com"),
            User(id=2, name="Jane", email="jane@example.com")
        ]

        inputs = {"users": users}

        transformer = EntityToPrimaryKeyInputsTransformer()
        result = transformer.transform(inputs)

        assert result["users"] == [1, 2]

    def test_normalize_keys_to_snake_case(self):
        """Should normalize keys to snake_case"""
        inputs = {
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john@example.com"
        }

        transformer = NormalizeKeysTransformer(to_case="snake")
        result = transformer.transform(inputs)

        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["email_address"] == "john@example.com"

    def test_normalize_keys_to_camel_case(self):
        """Should normalize keys to camelCase"""
        inputs = {
            "first_name": "John",
            "last_name": "Doe"
        }

        transformer = NormalizeKeysTransformer(to_case="camel")
        result = transformer.transform(inputs)

        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"

    def test_strip_whitespace(self):
        """Should strip whitespace from strings"""
        inputs = {
            "name": "  John  ",
            "email": " john@example.com ",
            "age": 30
        }

        transformer = StripWhitespaceTransformer()
        result = transformer.transform(inputs)

        assert result["name"] == "John"
        assert result["email"] == "john@example.com"
        assert result["age"] == 30

    def test_default_values(self):
        """Should set default values"""
        inputs = {"name": "John"}

        transformer = DefaultValuesTransformer(status="active", count=0)
        result = transformer.transform(inputs)

        assert result["name"] == "John"
        assert result["status"] == "active"
        assert result["count"] == 0

    def test_remove_null_values(self):
        """Should remove None values"""
        inputs = {
            "name": "John",
            "age": None,
            "email": "john@example.com",
            "address": None
        }

        transformer = RemoveNullValuesTransformer()
        result = transformer.transform(inputs)

        assert "name" in result
        assert "email" in result
        assert "age" not in result
        assert "address" not in result


class TestResultTransformers:
    """Test result transformers"""

    def test_result_to_json(self):
        """Should convert result to JSON-serializable format"""
        from datetime import datetime

        class UserModel(BaseModel):
            id: int
            name: str

        result = {
            "user": UserModel(id=1, name="John"),
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "count": 5
        }

        transformer = ResultToJsonTransformer()
        json_result = transformer.transform(result)

        assert json_result["user"]["id"] == 1
        assert json_result["user"]["name"] == "John"
        assert json_result["timestamp"] == "2024-01-01T12:00:00"
        assert json_result["count"] == 5

    def test_entity_to_pk_result(self):
        """Should convert entities in result to PKs"""
        user = User(id=1, name="John", email="john@example.com")

        result = {
            "user": user,
            "name": "Test"
        }

        transformer = EntityToPrimaryKeyResultTransformer()
        transformed = transformer.transform(result)

        assert transformed["user"] == 1
        assert transformed["name"] == "Test"

    def test_pagination_transformer(self):
        """Should add pagination metadata"""
        items = [1, 2, 3, 4, 5]

        transformer = PaginationTransformer(page=1, per_page=10, total=50)
        result = transformer.transform(items)

        assert result["items"] == items
        assert result["page"] == 1
        assert result["per_page"] == 10
        assert result["total"] == 50
        assert result["total_pages"] == 5


class TestErrorTransformers:
    """Test error transformers"""

    def test_auth_errors_transformer(self):
        """Should transform auth error messages"""
        errors = ErrorCollection()
        errors.add(FoobaraError.runtime_error("not_authenticated", "Auth required"))
        errors.add(FoobaraError.runtime_error("forbidden", "Forbidden"))

        transformer = AuthErrorsTransformer()
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert len(error_list) == 2
        assert error_list[0].message == "Please log in to continue"
        assert error_list[1].message == "Access denied"

    def test_user_friendly_errors_transformer(self):
        """Should make errors user-friendly"""
        errors = ErrorCollection()
        errors.add(FoobaraError.data_error("required", ["name"], "Name is required"))
        errors.add(FoobaraError.data_error("too_short", ["password"], "Too short"))

        transformer = UserFriendlyErrorsTransformer()
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert "This field is required" in error_list[0].message
        assert "Value is too short" in error_list[1].message

    def test_strip_runtime_path_transformer(self):
        """Should remove runtime paths from errors"""
        error = FoobaraError(
            category="data",
            symbol="invalid_value",
            path=("field",),
            message="Invalid",
            runtime_path=("command1", "command2")
        )

        errors = ErrorCollection()
        errors.add(error)

        transformer = StripRuntimePathTransformer()
        transformed = transformer.transform(errors)

        transformed_error = transformed.all()[0]
        assert len(transformed_error.runtime_path) == 0

    def test_group_errors_by_path(self):
        """Should group errors by data path"""
        errors = ErrorCollection()
        errors.add(FoobaraError.data_error("required", ["user", "email"], "Required"))
        errors.add(FoobaraError.data_error("invalid_format", ["user", "email"], "Invalid"))
        errors.add(FoobaraError.data_error("too_short", ["user", "name"], "Too short"))

        transformer = GroupErrorsByPathTransformer()
        grouped = transformer.transform(errors)

        assert "user.email" in grouped
        assert "user.name" in grouped
        assert len(grouped["user.email"]) == 2
        assert len(grouped["user.name"]) == 1
