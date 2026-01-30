"""Comprehensive tests for transformers system

This test suite provides extensive coverage of all transformer functionality:
- Desugarizers (15+ tests): OnlyInputs, RejectInputs, RenameKey, SetInputs, MergeInputs
- Input transformers (10+ tests): EntityToPrimaryKey, NormalizeKeys
- Result transformers (10+ tests): LoadAggregates, ResultToJson
- Error transformers (10+ tests): AuthErrors, UserFriendlyErrors

Total: 45+ transformer tests
"""

import pytest
from datetime import datetime, date
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
    LoadAggregatesTransformer,
    AuthErrorsTransformer,
    UserFriendlyErrorsTransformer,
    StripRuntimePathTransformer,
    GroupErrorsByPathTransformer
)
from foobara_py.desugarizers import (
    OnlyInputs,
    RejectInputs,
    RenameKey,
    SetInputs,
    MergeInputs,
    SymbolsToTrue,
    InputsFromJson,
    ParseBooleans,
    ParseNumbers
)
from foobara_py.persistence.entity import EntityBase, Model
from foobara_py.core.errors import FoobaraError, ErrorCollection


# Test entities and models
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


class Address(Model):
    street: str
    city: str
    zip_code: str = None


class TestDesugarizersComprehensive:
    """Comprehensive tests for desugarizers (15+ tests)"""

    def test_only_inputs_keeps_specified_keys(self):
        """Should keep only specified input keys"""
        desugarizer = OnlyInputs("name", "email")
        data = {"name": "John", "email": "john@example.com", "extra": "value", "another": "field"}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com"}
        assert "extra" not in result
        assert "another" not in result

    def test_only_inputs_with_missing_keys(self):
        """Should handle when specified keys are missing"""
        desugarizer = OnlyInputs("name", "email", "age")
        data = {"name": "John", "email": "john@example.com"}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com"}

    def test_reject_inputs_removes_specified_keys(self):
        """Should remove specified input keys"""
        desugarizer = RejectInputs("password", "secret", "token")
        data = {
            "name": "John",
            "password": "secret123",
            "email": "john@example.com",
            "secret": "key",
            "token": "abc"
        }
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com"}

    def test_reject_inputs_with_nonexistent_keys(self):
        """Should handle when rejected keys don't exist"""
        desugarizer = RejectInputs("password", "secret")
        data = {"name": "John", "email": "john@example.com"}
        result = desugarizer.desugarize(data)

        assert result == data

    def test_rename_key_maps_old_to_new(self):
        """Should rename keys according to mappings"""
        desugarizer = RenameKey(old_name="name", old_email="email", old_age="age")
        data = {"old_name": "John", "old_email": "john@example.com", "old_age": 30}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com", "age": 30}

    def test_rename_key_preserves_unmapped_keys(self):
        """Should preserve keys that aren't mapped"""
        desugarizer = RenameKey(old_name="name")
        data = {"old_name": "John", "email": "john@example.com", "age": 30}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com", "age": 30}

    def test_set_inputs_adds_defaults(self):
        """Should add default values for missing keys"""
        desugarizer = SetInputs(status="active", count=0, verified=False)
        data = {"name": "John"}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "status": "active", "count": 0, "verified": False}

    def test_set_inputs_preserves_existing_values(self):
        """Should not override existing values"""
        desugarizer = SetInputs(status="active", count=0)
        data = {"name": "John", "status": "inactive"}
        result = desugarizer.desugarize(data)

        assert result["status"] == "inactive"  # Preserved
        assert result["count"] == 0  # Added

    def test_merge_inputs_flattens_nested_dicts(self):
        """Should merge nested dictionaries into top level"""
        desugarizer = MergeInputs("user", "settings")
        data = {
            "name": "John",
            "user": {"email": "john@example.com", "age": 30},
            "settings": {"theme": "dark", "notifications": True},
            "count": 5
        }
        result = desugarizer.desugarize(data)

        assert "email" in result
        assert "age" in result
        assert "theme" in result
        assert "notifications" in result
        assert result["name"] == "John"
        assert result["count"] == 5

    def test_merge_inputs_handles_conflicts(self):
        """Should handle key conflicts when merging"""
        desugarizer = MergeInputs("nested")
        data = {
            "name": "Original",
            "nested": {"name": "Nested", "email": "test@example.com"}
        }
        result = desugarizer.desugarize(data)

        # Merged values should override
        assert result["name"] == "Nested"
        assert result["email"] == "test@example.com"

    def test_symbols_to_true_converts_flags(self):
        """Should convert presence of keys to boolean true"""
        desugarizer = SymbolsToTrue("verbose", "debug", "force")
        data = {"verbose": None, "debug": "", "name": "John", "force": False}
        result = desugarizer.desugarize(data)

        assert result["verbose"] is True
        assert result["debug"] is True
        assert result["force"] is True
        assert result["name"] == "John"

    def test_inputs_from_json_parses_json_strings(self):
        """Should parse JSON strings in specified keys"""
        desugarizer = InputsFromJson("data", "payload")
        data = {
            "data": '{"name": "John", "age": 30}',
            "payload": '["item1", "item2", "item3"]',
            "string": "regular string"
        }
        result = desugarizer.desugarize(data)

        assert result["data"]["name"] == "John"
        assert result["data"]["age"] == 30
        assert result["payload"] == ["item1", "item2", "item3"]
        assert result["string"] == "regular string"

    def test_inputs_from_json_handles_invalid_json(self):
        """Should leave invalid JSON as string"""
        desugarizer = InputsFromJson("data")
        data = {"data": "not valid json {"}
        result = desugarizer.desugarize(data)

        assert result["data"] == "not valid json {"

    def test_parse_booleans_converts_boolean_strings(self):
        """Should parse boolean string values"""
        desugarizer = ParseBooleans("active", "verified", "enabled")
        data = {
            "active": "true",
            "verified": "yes",
            "enabled": "1",
            "count": "5"
        }
        result = desugarizer.desugarize(data)

        assert result["active"] is True
        assert result["verified"] is True
        assert result["enabled"] is True
        assert result["count"] == "5"  # Not a boolean key

    def test_parse_booleans_handles_false_values(self):
        """Should parse false boolean values"""
        desugarizer = ParseBooleans("active", "verified")
        data = {
            "active": "false",
            "verified": "no"
        }
        result = desugarizer.desugarize(data)

        assert result["active"] is False
        assert result["verified"] is False

    def test_parse_numbers_converts_numeric_strings(self):
        """Should parse numeric string values"""
        desugarizer = ParseNumbers("count", "price", "quantity")
        data = {
            "count": "42",
            "price": "19.99",
            "quantity": "100",
            "name": "Product"
        }
        result = desugarizer.desugarize(data)

        assert result["count"] == 42
        assert result["price"] == 19.99
        assert result["quantity"] == 100
        assert result["name"] == "Product"


class TestInputTransformersComprehensive:
    """Comprehensive tests for input transformers (10+ tests)"""

    def test_entity_to_pk_converts_single_entity(self):
        """Should convert entity objects to primary keys"""
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

    def test_entity_to_pk_handles_list_of_entities(self):
        """Should handle lists of entities"""
        users = [
            User(id=1, name="John", email="john@example.com"),
            User(id=2, name="Jane", email="jane@example.com"),
            User(id=3, name="Bob", email="bob@example.com")
        ]

        inputs = {"users": users, "count": 3}

        transformer = EntityToPrimaryKeyInputsTransformer()
        result = transformer.transform(inputs)

        assert result["users"] == [1, 2, 3]
        assert result["count"] == 3

    def test_entity_to_pk_handles_nested_dicts(self):
        """Should recursively process nested dictionaries"""
        user = User(id=1, name="John", email="john@example.com")

        inputs = {
            "data": {
                "user": user,
                "meta": {
                    "count": 5
                }
            }
        }

        transformer = EntityToPrimaryKeyInputsTransformer()
        result = transformer.transform(inputs)

        assert result["data"]["user"] == 1
        assert result["data"]["meta"]["count"] == 5

    def test_normalize_keys_to_snake_case(self):
        """Should normalize keys to snake_case"""
        inputs = {
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john@example.com",
            "phoneNumber": "555-1234"
        }

        transformer = NormalizeKeysTransformer(to_case="snake")
        result = transformer.transform(inputs)

        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["email_address"] == "john@example.com"
        assert result["phone_number"] == "555-1234"

    def test_normalize_keys_to_camel_case(self):
        """Should normalize keys to camelCase"""
        inputs = {
            "first_name": "John",
            "last_name": "Doe",
            "email_address": "john@example.com"
        }

        transformer = NormalizeKeysTransformer(to_case="camel")
        result = transformer.transform(inputs)

        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"
        assert result["emailAddress"] == "john@example.com"

    def test_normalize_keys_handles_nested_dicts(self):
        """Should recursively normalize nested dictionaries"""
        inputs = {
            "firstName": "John",
            "userProfile": {
                "emailAddress": "john@example.com",
                "homeAddress": {
                    "streetName": "Main St"
                }
            }
        }

        transformer = NormalizeKeysTransformer(to_case="snake")
        result = transformer.transform(inputs)

        assert "first_name" in result
        assert "user_profile" in result
        assert "email_address" in result["user_profile"]
        assert "home_address" in result["user_profile"]
        assert "street_name" in result["user_profile"]["home_address"]

    def test_strip_whitespace_from_strings(self):
        """Should strip whitespace from string values"""
        inputs = {
            "name": "  John  ",
            "email": " john@example.com ",
            "city": "   New York   ",
            "age": 30
        }

        transformer = StripWhitespaceTransformer()
        result = transformer.transform(inputs)

        assert result["name"] == "John"
        assert result["email"] == "john@example.com"
        assert result["city"] == "New York"
        assert result["age"] == 30

    def test_strip_whitespace_recursive(self):
        """Should strip whitespace recursively in nested structures"""
        inputs = {
            "name": "  John  ",
            "profile": {
                "email": "  test@example.com  ",
                "tags": ["  python  ", "  testing  "]
            }
        }

        transformer = StripWhitespaceTransformer(recursive=True)
        result = transformer.transform(inputs)

        assert result["name"] == "John"
        assert result["profile"]["email"] == "test@example.com"
        assert result["profile"]["tags"] == ["python", "testing"]

    def test_default_values_adds_missing_keys(self):
        """Should set default values for missing keys"""
        inputs = {"name": "John"}

        transformer = DefaultValuesTransformer(status="active", count=0, verified=False)
        result = transformer.transform(inputs)

        assert result["name"] == "John"
        assert result["status"] == "active"
        assert result["count"] == 0
        assert result["verified"] is False

    def test_remove_null_values_filters_none(self):
        """Should remove None values from dictionary"""
        inputs = {
            "name": "John",
            "age": None,
            "email": "john@example.com",
            "address": None,
            "verified": False,
            "count": 0
        }

        transformer = RemoveNullValuesTransformer()
        result = transformer.transform(inputs)

        assert "name" in result
        assert "email" in result
        assert "verified" in result
        assert "count" in result
        assert "age" not in result
        assert "address" not in result

    def test_remove_null_values_recursive(self):
        """Should remove None values recursively"""
        inputs = {
            "name": "John",
            "profile": {
                "email": "test@example.com",
                "phone": None,
                "address": {
                    "street": "Main St",
                    "apt": None
                }
            }
        }

        transformer = RemoveNullValuesTransformer(recursive=True)
        result = transformer.transform(inputs)

        assert "phone" not in result["profile"]
        assert "apt" not in result["profile"]["address"]
        assert result["profile"]["address"]["street"] == "Main St"


class TestResultTransformersComprehensive:
    """Comprehensive tests for result transformers (10+ tests)"""

    def test_result_to_json_converts_pydantic_models(self):
        """Should convert Pydantic models to JSON-serializable format"""
        class UserModel(BaseModel):
            id: int
            name: str
            email: str

        result = {
            "user": UserModel(id=1, name="John", email="john@example.com"),
            "count": 5
        }

        transformer = ResultToJsonTransformer()
        json_result = transformer.transform(result)

        assert json_result["user"]["id"] == 1
        assert json_result["user"]["name"] == "John"
        assert json_result["user"]["email"] == "john@example.com"
        assert json_result["count"] == 5

    def test_result_to_json_converts_datetime(self):
        """Should convert datetime objects to ISO format"""
        result = {
            "timestamp": datetime(2024, 1, 15, 12, 30, 45),
            "date": date(2024, 1, 15),
            "name": "Event"
        }

        transformer = ResultToJsonTransformer()
        json_result = transformer.transform(result)

        assert json_result["timestamp"] == "2024-01-15T12:30:45"
        assert json_result["date"] == "2024-01-15"
        assert json_result["name"] == "Event"

    def test_result_to_json_handles_nested_structures(self):
        """Should recursively convert nested structures"""
        class AddressModel(BaseModel):
            street: str
            city: str

        result = {
            "user": {
                "name": "John",
                "address": AddressModel(street="123 Main St", city="NYC"),
                "created_at": datetime(2024, 1, 1, 10, 0, 0)
            }
        }

        transformer = ResultToJsonTransformer()
        json_result = transformer.transform(result)

        assert json_result["user"]["address"]["street"] == "123 Main St"
        assert json_result["user"]["created_at"] == "2024-01-01T10:00:00"

    def test_result_to_json_converts_lists(self):
        """Should convert items in lists"""
        class Item(BaseModel):
            id: int
            name: str

        result = {
            "items": [
                Item(id=1, name="Item 1"),
                Item(id=2, name="Item 2")
            ]
        }

        transformer = ResultToJsonTransformer()
        json_result = transformer.transform(result)

        assert len(json_result["items"]) == 2
        assert json_result["items"][0]["id"] == 1
        assert json_result["items"][1]["name"] == "Item 2"

    def test_result_to_json_handles_sets(self):
        """Should convert sets to lists"""
        result = {
            "tags": {"python", "testing", "automation"}
        }

        transformer = ResultToJsonTransformer()
        json_result = transformer.transform(result)

        assert isinstance(json_result["tags"], list)
        assert len(json_result["tags"]) == 3

    def test_result_to_json_handles_none(self):
        """Should preserve None values"""
        result = {
            "name": "John",
            "age": None,
            "email": "test@example.com"
        }

        transformer = ResultToJsonTransformer()
        json_result = transformer.transform(result)

        assert json_result["age"] is None

    def test_entity_to_pk_result_converts_entities(self):
        """Should convert all entities in result to PKs"""
        user = User(id=1, name="John", email="john@example.com")
        post = Post(id=10, title="Test", content="Content")

        result = {
            "user": user,
            "post": post,
            "name": "Test"
        }

        transformer = EntityToPrimaryKeyResultTransformer()
        transformed = transformer.transform(result)

        assert transformed["user"] == 1
        assert transformed["post"] == 10
        assert transformed["name"] == "Test"

    def test_entity_to_pk_result_handles_nested_structures(self):
        """Should recursively convert nested entities"""
        user = User(id=1, name="John", email="john@example.com")

        result = {
            "data": {
                "user": user,
                "posts": [
                    Post(id=10, title="Post 1", content="Content"),
                    Post(id=20, title="Post 2", content="Content")
                ]
            }
        }

        transformer = EntityToPrimaryKeyResultTransformer()
        transformed = transformer.transform(result)

        assert transformed["data"]["user"] == 1
        assert transformed["data"]["posts"] == [10, 20]

    def test_pagination_adds_metadata(self):
        """Should add pagination metadata to list results"""
        items = [1, 2, 3, 4, 5]

        transformer = PaginationTransformer(page=1, per_page=10, total=50)
        result = transformer.transform(items)

        assert result["items"] == items
        assert result["page"] == 1
        assert result["per_page"] == 10
        assert result["total"] == 50
        assert result["total_pages"] == 5

    def test_pagination_calculates_total_pages(self):
        """Should correctly calculate total pages"""
        items = [1, 2, 3]

        transformer = PaginationTransformer(page=2, per_page=3, total=10)
        result = transformer.transform(items)

        assert result["total_pages"] == 4  # 10 items / 3 per page = 4 pages

    def test_load_aggregates_placeholder(self):
        """Should handle load aggregates transformer (placeholder)"""
        result = {"user": {"id": 1, "name": "John"}}

        transformer = LoadAggregatesTransformer("user", "user.posts")
        loaded = transformer.transform(result)

        # Placeholder implementation returns data as-is
        assert loaded == result


class TestErrorTransformersComprehensive:
    """Comprehensive tests for error transformers (10+ tests)"""

    def test_auth_errors_transforms_messages(self):
        """Should transform auth error messages to user-friendly"""
        errors = ErrorCollection()
        errors.add(FoobaraError.runtime_error("not_authenticated", "Auth required"))
        errors.add(FoobaraError.runtime_error("forbidden", "Forbidden"))

        transformer = AuthErrorsTransformer()
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert len(error_list) == 2
        assert error_list[0].message == "Please log in to continue"
        assert error_list[1].message == "Access denied"

    def test_auth_errors_custom_messages(self):
        """Should support custom auth error messages"""
        errors = ErrorCollection()
        errors.add(FoobaraError.runtime_error("not_authenticated", "Auth required"))

        custom_messages = {"not_authenticated": "You need to sign in first"}
        transformer = AuthErrorsTransformer(custom_messages=custom_messages)
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert error_list[0].message == "You need to sign in first"

    def test_auth_errors_preserves_non_auth_errors(self):
        """Should preserve errors not in auth mapping"""
        errors = ErrorCollection()
        errors.add(FoobaraError.runtime_error("not_authenticated", "Auth required"))
        errors.add(FoobaraError.data_error("invalid_email", ["email"], "Invalid email"))

        transformer = AuthErrorsTransformer()
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert error_list[0].message == "Please log in to continue"
        assert error_list[1].message == "Invalid email"  # Unchanged

    def test_user_friendly_errors_transforms_validation_errors(self):
        """Should make validation errors user-friendly"""
        errors = ErrorCollection()
        errors.add(FoobaraError.data_error("required", ["name"], "Name is required"))
        errors.add(FoobaraError.data_error("too_short", ["password"], "Too short"))
        errors.add(FoobaraError.data_error("invalid_format", ["email"], "Bad format"))

        transformer = UserFriendlyErrorsTransformer()
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert "This field is required" in error_list[0].message
        assert "Value is too short" in error_list[1].message
        assert "Invalid format" in error_list[2].message

    def test_user_friendly_errors_enriches_with_context(self):
        """Should enrich messages with context information"""
        errors = ErrorCollection()
        error = FoobaraError.data_error(
            "too_short",
            ["password"],
            "Password too short",
            min=8
        )
        errors.add(error)

        transformer = UserFriendlyErrorsTransformer()
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert "minimum: 8" in error_list[0].message

    def test_user_friendly_errors_handles_range_context(self):
        """Should handle min/max range in context"""
        errors = ErrorCollection()
        error = FoobaraError.data_error(
            "out_of_range",
            ["age"],
            "Invalid age",
            min=0,
            max=120
        )
        errors.add(error)

        transformer = UserFriendlyErrorsTransformer()
        transformed = transformer.transform(errors)

        error_list = transformed.all()
        assert "between 0 and 120" in error_list[0].message

    def test_strip_runtime_path_removes_paths(self):
        """Should remove runtime paths from errors"""
        errors = ErrorCollection()
        error = FoobaraError(
            category="data",
            symbol="invalid_value",
            path=("field",),
            message="Invalid",
            runtime_path=("command1", "command2", "command3")
        )
        errors.add(error)

        transformer = StripRuntimePathTransformer()
        transformed = transformer.transform(errors)

        transformed_error = transformed.all()[0]
        assert len(transformed_error.runtime_path) == 0

    def test_strip_runtime_path_preserves_other_fields(self):
        """Should preserve all other error fields"""
        errors = ErrorCollection()
        error = FoobaraError(
            category="data",
            symbol="invalid_value",
            path=("field",),
            message="Invalid",
            runtime_path=("command1",),
            context={"key": "value"}
        )
        errors.add(error)

        transformer = StripRuntimePathTransformer()
        transformed = transformer.transform(errors)

        transformed_error = transformed.all()[0]
        assert transformed_error.category == "data"
        assert transformed_error.symbol == "invalid_value"
        assert transformed_error.path == ("field",)
        assert transformed_error.message == "Invalid"
        assert transformed_error.context == {"key": "value"}

    def test_group_errors_by_path_creates_dict(self):
        """Should group errors by their data path"""
        errors = ErrorCollection()
        errors.add(FoobaraError.data_error("required", ["user", "email"], "Required"))
        errors.add(FoobaraError.data_error("invalid_format", ["user", "email"], "Invalid"))
        errors.add(FoobaraError.data_error("too_short", ["user", "name"], "Too short"))
        errors.add(FoobaraError.runtime_error("timeout", "Timeout"))

        transformer = GroupErrorsByPathTransformer()
        grouped = transformer.transform(errors)

        assert "user.email" in grouped
        assert "user.name" in grouped
        assert "general" in grouped
        assert len(grouped["user.email"]) == 2
        assert len(grouped["user.name"]) == 1
        assert len(grouped["general"]) == 1

    def test_group_errors_includes_error_details(self):
        """Should include error details in grouped structure"""
        errors = ErrorCollection()
        error = FoobaraError.data_error(
            "required",
            ["user", "email"],
            "Email is required",
            field_type="string"
        )
        errors.add(error)

        transformer = GroupErrorsByPathTransformer()
        grouped = transformer.transform(errors)

        error_data = grouped["user.email"][0]
        assert error_data["symbol"] == "required"
        assert error_data["message"] == "Email is required"
        assert error_data["context"]["field_type"] == "string"


class TestTransformerPipelineComprehensive:
    """Comprehensive tests for transformer pipelines"""

    def test_pipeline_executes_in_sequence(self):
        """Should execute transformers in sequence"""
        inputs = {
            "firstName": "  John  ",
            "lastName": "  Doe  "
        }

        pipeline = TransformerPipeline(
            StripWhitespaceTransformer(),
            NormalizeKeysTransformer(to_case="snake")
        )

        result = pipeline.transform(inputs)

        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"

    def test_pipeline_with_multiple_transformers(self):
        """Should chain multiple transformers"""
        user = User(id=1, name="John", email="john@example.com")
        inputs = {
            "user": user,
            "firstName": "  John  "
        }

        pipeline = TransformerPipeline(
            StripWhitespaceTransformer(),
            EntityToPrimaryKeyInputsTransformer(),
            DefaultValuesTransformer(status="active")
        )

        result = pipeline.transform(inputs)

        assert result["user"] == 1
        assert result["firstName"] == "John"
        assert result["status"] == "active"

    def test_pipeline_add_transformer(self):
        """Should add transformer to pipeline"""
        pipeline = TransformerPipeline(
            StripWhitespaceTransformer()
        )
        pipeline.add(DefaultValuesTransformer(status="active"))

        inputs = {"name": "  John  "}
        result = pipeline.transform(inputs)

        assert result["name"] == "John"
        assert result["status"] == "active"

    def test_pipeline_prepend_transformer(self):
        """Should prepend transformer to beginning of pipeline"""
        pipeline = TransformerPipeline(
            NormalizeKeysTransformer(to_case="snake")
        )
        pipeline.prepend(StripWhitespaceTransformer())

        inputs = {"firstName": "  John  "}
        result = pipeline.transform(inputs)

        # Strip happens first, then normalize
        assert result["first_name"] == "John"

    def test_complex_transformer_pipeline(self):
        """Should handle complex multi-stage pipeline"""
        user = User(id=1, name="John", email="john@example.com")

        inputs = {
            "userName": user,
            "firstName": "  John  ",
            "extra": "remove me",
            "age": None
        }

        # Create complex pipeline combining multiple transformers
        pipeline = TransformerPipeline(
            StripWhitespaceTransformer(),
            RemoveNullValuesTransformer(),
            EntityToPrimaryKeyInputsTransformer(),
            NormalizeKeysTransformer(to_case="snake")
        )

        result = pipeline.transform(inputs)

        # Verify all transformations were applied
        assert "user_name" in result
        assert result["user_name"] == 1  # Entity converted to PK
        assert result["first_name"] == "John"  # Whitespace stripped and key normalized
        assert "age" not in result  # None removed
        assert "extra" in result  # Not filtered (no RejectInputs in pipeline)
