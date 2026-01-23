"""Tests for desugarizers system"""

import pytest
from foobara_py.desugarizers import (
    Desugarizer,
    DesugarizePipeline,
    DesugarizerRegistry,
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


class TestDesugarizerBase:
    """Test base desugarizer functionality"""

    def test_custom_desugarizer(self):
        """Should create and use custom desugarizer"""

        class UppercaseKeysDesugarizer(Desugarizer):
            def desugarize(self, data):
                return {k.upper(): v for k, v in data.items()}

        desugarizer = UppercaseKeysDesugarizer()
        result = desugarizer.desugarize({"name": "John"})

        assert result == {"NAME": "John"}


class TestDesugarizePipeline:
    """Test DesugarizePipeline"""

    def test_pipeline_execution(self):
        """Should execute desugarizers in sequence"""
        pipeline = DesugarizePipeline(
            SetInputs(status="active"),
            OnlyInputs("name", "status")
        )

        data = {"name": "John", "extra": "value"}
        result = pipeline.process(data)

        assert result == {"name": "John", "status": "active"}


class TestAttributeDesugarizers:
    """Test attribute desugarizers"""

    def test_only_inputs(self):
        """Should keep only specified keys"""
        desugarizer = OnlyInputs("name", "email")
        data = {"name": "John", "email": "john@example.com", "extra": "value"}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com"}

    def test_reject_inputs(self):
        """Should remove specified keys"""
        desugarizer = RejectInputs("password", "secret")
        data = {"name": "John", "password": "secret123", "email": "john@example.com"}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com"}

    def test_rename_key(self):
        """Should rename keys"""
        desugarizer = RenameKey(old_name="name", old_email="email")
        data = {"old_name": "John", "old_email": "john@example.com"}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "email": "john@example.com"}

    def test_set_inputs(self):
        """Should set default values"""
        desugarizer = SetInputs(status="active", count=0)
        data = {"name": "John"}
        result = desugarizer.desugarize(data)

        assert result == {"name": "John", "status": "active", "count": 0}

    def test_merge_inputs(self):
        """Should merge nested dicts"""
        desugarizer = MergeInputs("user")
        data = {
            "name": "John",
            "user": {"email": "john@example.com", "age": 30},
            "count": 5
        }
        result = desugarizer.desugarize(data)

        assert "email" in result
        assert "age" in result
        assert result["name"] == "John"

    def test_symbols_to_true(self):
        """Should convert symbols to True"""
        desugarizer = SymbolsToTrue("verbose", "debug")
        data = {"verbose": None, "name": "John"}
        result = desugarizer.desugarize(data)

        assert result["verbose"] is True
        assert result["name"] == "John"


class TestFormatDesugarizers:
    """Test format desugarizers"""

    def test_inputs_from_json(self):
        """Should parse JSON strings"""
        desugarizer = InputsFromJson("data")
        data = {"data": '{"name": "John", "age": 30}'}
        result = desugarizer.desugarize(data)

        assert result["data"]["name"] == "John"
        assert result["data"]["age"] == 30

    def test_parse_booleans(self):
        """Should parse boolean strings"""
        desugarizer = ParseBooleans("active", "verified")
        data = {"active": "true", "verified": "yes", "count": "5"}
        result = desugarizer.desugarize(data)

        assert result["active"] is True
        assert result["verified"] is True
        assert result["count"] == "5"

    def test_parse_numbers(self):
        """Should parse numeric strings"""
        desugarizer = ParseNumbers("count", "price")
        data = {"count": "42", "price": "19.99", "name": "Product"}
        result = desugarizer.desugarize(data)

        assert result["count"] == 42
        assert result["price"] == 19.99
        assert result["name"] == "Product"
