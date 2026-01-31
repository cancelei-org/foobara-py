"""Tests for Outcome module"""

import pytest
from foobara_py.core.outcome import Success, Failure, CommandOutcome
from foobara_py.core.errors import FoobaraError


class TestSuccess:
    def test_is_success(self):
        outcome = Success(result=42)
        assert outcome.is_success() is True
        assert outcome.is_failure() is False

    def test_unwrap(self):
        outcome = Success(result="hello")
        assert outcome.unwrap() == "hello"

    def test_unwrap_or(self):
        outcome = Success(result=42)
        assert outcome.unwrap_or(0) == 42

    def test_map(self):
        outcome = Success(result=5)
        mapped = outcome.map(lambda x: x * 2)
        assert mapped.unwrap() == 10


class TestFailure:
    def test_is_failure(self):
        error = FoobaraError(category="data", symbol="test", path=[], message="test error")
        outcome = Failure(errors=[error])
        assert outcome.is_failure() is True
        assert outcome.is_success() is False

    def test_unwrap_raises(self):
        error = FoobaraError(category="data", symbol="test", path=[], message="test error")
        outcome = Failure(errors=[error])
        with pytest.raises(ValueError):
            outcome.unwrap()

    def test_unwrap_or(self):
        error = FoobaraError(category="data", symbol="test", path=[], message="test error")
        outcome = Failure(errors=[error])
        assert outcome.unwrap_or("default") == "default"

    def test_error_messages(self):
        error1 = FoobaraError(category="data", symbol="e1", path=[], message="Error 1")
        error2 = FoobaraError(category="data", symbol="e2", path=[], message="Error 2")
        outcome = Failure(errors=[error1, error2])
        messages = outcome.error_messages()
        assert "Error 1" in messages
        assert "Error 2" in messages

    def test_first_error(self):
        error = FoobaraError(category="data", symbol="first", path=[], message="First error")
        outcome = Failure(errors=[error])
        assert outcome.first_error().symbol == "first"


class TestCommandOutcome:
    def test_success_from_result(self):
        outcome = CommandOutcome.from_result({"id": 1, "name": "test"})
        assert outcome.is_success() is True
        assert outcome.result["id"] == 1

    def test_failure_from_errors(self):
        error = FoobaraError(category="data", symbol="test", path=["field"], message="Invalid")
        outcome = CommandOutcome.from_errors(error)
        assert outcome.is_failure() is True
        assert len(outcome.errors) == 1

    def test_unwrap_success(self):
        outcome = CommandOutcome.from_result(42)
        assert outcome.unwrap() == 42

    def test_unwrap_failure_raises(self):
        error = FoobaraError(category="data", symbol="test", path=[], message="Error")
        outcome = CommandOutcome.from_errors(error)
        with pytest.raises(ValueError):
            outcome.unwrap()

    def test_map(self):
        outcome = CommandOutcome.from_result(5)
        mapped = outcome.map(lambda x: x * 2)
        assert mapped.unwrap() == 10

    def test_map_failure_unchanged(self):
        error = FoobaraError(category="data", symbol="test", path=[], message="Error")
        outcome = CommandOutcome.from_errors(error)
        mapped = outcome.map(lambda x: x * 2)
        assert mapped.is_failure()

    def test_to_dict_success(self):
        outcome = CommandOutcome.from_result({"key": "value"})
        d = outcome.to_dict()
        assert d["success"] is True
        assert d["result"]["key"] == "value"

    def test_to_dict_failure(self):
        error = FoobaraError(category="data", symbol="test", path=[], message="Error")
        outcome = CommandOutcome.from_errors(error)
        d = outcome.to_dict()
        assert d["success"] is False
        assert len(d["errors"]) == 1

    def test_add_error(self):
        outcome = CommandOutcome.from_result(42)
        error = FoobaraError(category="data", symbol="test", path=[], message="Error")
        outcome.add_error(error)
        assert outcome.is_failure()
