"""Tests for Command module"""

import pytest
from pydantic import BaseModel, Field
from foobara_py.core.command import Command, command, SimpleCommand, simple_command
from foobara_py.core.errors import DataError


class AddInputs(BaseModel):
    a: int
    b: int


class Add(Command[AddInputs, int]):
    """Add two numbers"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


class TestCommand:
    def test_run_success(self):
        outcome = Add.run(a=5, b=3)
        assert outcome.is_success()
        assert outcome.unwrap() == 8

    def test_run_with_validation_error(self):
        outcome = Add.run(a="not_a_number", b=3)
        assert outcome.is_failure()
        assert len(outcome.errors) > 0

    def test_inputs_type(self):
        assert Add.inputs_type() == AddInputs

    def test_inputs_schema(self):
        schema = Add.inputs_schema()
        assert "properties" in schema
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]

    def test_full_name_without_domain(self):
        assert Add.full_name() == "Add"

    def test_description(self):
        assert Add.description() == "Add two numbers"

    def test_manifest(self):
        manifest = Add.manifest()
        assert manifest["name"] == "Add"
        assert manifest["description"] == "Add two numbers"
        assert "inputs_type" in manifest


class TestCommandWithDomain:
    def test_command_decorator(self):
        @command(domain="Math", organization="TestOrg")
        class Multiply(Command[AddInputs, int]):
            def execute(self) -> int:
                return self.inputs.a * self.inputs.b

        assert Multiply._domain == "Math"
        assert Multiply._organization == "TestOrg"
        assert Multiply.full_name() == "TestOrg::Math::Multiply"


class TestCommandWithErrors:
    def test_add_error_during_execute(self):
        class DivideInputs(BaseModel):
            a: int
            b: int

        class Divide(Command[DivideInputs, float]):
            def execute(self) -> float:
                if self.inputs.b == 0:
                    self.add_runtime_error(
                        symbol="division_by_zero",
                        message="Cannot divide by zero"
                    )
                    return None
                return self.inputs.a / self.inputs.b

        # Normal case
        outcome = Divide.run(a=10, b=2)
        assert outcome.is_success()
        assert outcome.unwrap() == 5.0

        # Error case
        outcome = Divide.run(a=10, b=0)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "division_by_zero"

    def test_add_input_error(self):
        class ValidateInputs(BaseModel):
            email: str

        class ValidateEmail(Command[ValidateInputs, bool]):
            def execute(self) -> bool:
                if "@" not in self.inputs.email:
                    self.add_input_error(
                        path=["email"],
                        symbol="invalid_format",
                        message="Email must contain @"
                    )
                    return False
                return True

        outcome = ValidateEmail.run(email="invalid")
        assert outcome.is_failure()
        assert outcome.errors[0].path == ("email",)


class TestSimpleCommand:
    def test_simple_command_decorator(self):
        @simple_command
        def multiply(a: int, b: int) -> int:
            return a * b

        outcome = multiply.run(a=3, b=4)
        assert outcome.is_success()
        assert outcome.unwrap() == 12

    def test_simple_command_validation(self):
        @simple_command
        def add(a: int, b: int) -> int:
            return a + b

        outcome = add.run(a="not_int", b=3)
        assert outcome.is_failure()

    def test_simple_command_direct_call(self):
        @simple_command
        def add(a: int, b: int) -> int:
            return a + b

        result = add(a=5, b=3)
        assert result == 8

    def test_simple_command_schema(self):
        @simple_command
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        schema = greet.inputs_schema()
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "greeting" in schema["properties"]
