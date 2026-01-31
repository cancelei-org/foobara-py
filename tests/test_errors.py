"""Tests for Error module"""

import pytest
from foobara_py.core.errors import FoobaraError, ErrorCollection, ErrorSymbols


class TestFoobaraError:
    def test_data_error_creation(self):
        error = FoobaraError(
            category="data",
            symbol="invalid_format",
            path=["user", "email"],
            message="Invalid email format"
        )
        assert error.category == "data"
        assert error.symbol == "invalid_format"
        assert error.path == ("user", "email")
        assert error.message == "Invalid email format"

    def test_key_generation(self):
        error = FoobaraError(
            category="data",
            symbol="required",
            path=["name"],
            message="Name is required"
        )
        assert error.key() == "data.name.required"

    def test_key_with_nested_path(self):
        error = FoobaraError(
            category="data",
            symbol="invalid",
            path=["user", "address", "zipcode"],
            message="Invalid zipcode"
        )
        assert error.key() == "data.user.address.zipcode.invalid"

    def test_key_with_empty_path(self):
        error = FoobaraError(
            category="data",
            symbol="general",
            path=[],
            message="General error"
        )
        assert error.key() == "data.root.general"

    def test_data_error_factory(self):
        error = FoobaraError.data_error(
            symbol="too_short",
            path=["password"],
            message="Password too short",
            min_length=8
        )
        assert error.category == "data"
        assert error.context["min_length"] == 8

    def test_runtime_error_factory(self):
        error = FoobaraError.runtime_error(
            symbol="connection_failed",
            message="Database connection failed"
        )
        assert error.category == "runtime"
        assert error.path == ()

    def test_system_error_factory(self):
        error = FoobaraError.system_error(
            symbol="out_of_memory",
            message="Out of memory"
        )
        assert error.category == "system"

    def test_with_path_prefix(self):
        error = FoobaraError(
            category="data",
            symbol="invalid",
            path=["email"],
            message="Invalid email"
        )
        prefixed = error.with_path_prefix("user", "contact")
        assert prefixed.path == ("user", "contact", "email")


class TestErrorCollection:
    def test_add_error(self):
        collection = ErrorCollection()
        error = FoobaraError.data_error("required", ["name"], "Required")
        collection.add(error)
        assert collection.has_errors()
        assert collection.count() == 1

    def test_add_multiple_errors(self):
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("required", ["name"], "Name required"),
            FoobaraError.data_error("invalid", ["email"], "Invalid email")
        )
        assert collection.count() == 2

    def test_is_empty(self):
        collection = ErrorCollection()
        assert collection.is_empty()
        collection.add(FoobaraError.data_error("test", [], "test"))
        assert not collection.is_empty()

    def test_at_path(self):
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("required", ["name"], "Name required"),
            FoobaraError.data_error("invalid", ["email"], "Invalid email"),
            FoobaraError.data_error("too_short", ["email"], "Email too short")
        )
        email_errors = collection.at_path(["email"])
        assert len(email_errors) == 2

    def test_with_symbol(self):
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("required", ["name"], "Name required"),
            FoobaraError.data_error("required", ["email"], "Email required")
        )
        required_errors = collection.with_symbol("required")
        assert len(required_errors) == 2

    def test_by_category(self):
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("test", [], "Data error"),
            FoobaraError.runtime_error("test", "Runtime error")
        )
        data_errors = collection.by_category("data")
        assert len(data_errors) == 1

    def test_first(self):
        collection = ErrorCollection()
        assert collection.first() is None
        collection.add(FoobaraError.data_error("first", [], "First"))
        assert collection.first().symbol == "first"

    def test_messages(self):
        collection = ErrorCollection()
        collection.add_all(
            FoobaraError.data_error("e1", [], "Error 1"),
            FoobaraError.data_error("e2", [], "Error 2")
        )
        messages = collection.messages()
        assert "Error 1" in messages
        assert "Error 2" in messages

    def test_to_dict(self):
        collection = ErrorCollection()
        collection.add(FoobaraError.data_error("required", ["name"], "Required"))
        d = collection.to_dict()
        key = "data.name.required"
        assert key in d
        assert d[key]["message"] == "Required"

    def test_merge(self):
        c1 = ErrorCollection()
        c2 = ErrorCollection()
        c1.add(FoobaraError.data_error("e1", [], "Error 1"))
        c2.add(FoobaraError.data_error("e2", [], "Error 2"))
        c1.merge(c2)
        assert c1.count() == 2


class TestErrorSymbols:
    def test_symbols_defined(self):
        assert ErrorSymbols.REQUIRED == "required"
        assert ErrorSymbols.INVALID_FORMAT == "invalid_format"
        assert ErrorSymbols.NOT_FOUND == "not_found"
