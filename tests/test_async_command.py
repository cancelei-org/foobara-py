"""Tests for AsyncCommand module"""

import pytest
import asyncio
from pydantic import BaseModel
from foobara_py.core.command import (
    AsyncCommand, async_command, AsyncSimpleCommand, async_simple_command
)
from foobara_py.core.errors import DataError


class AddInputs(BaseModel):
    a: int
    b: int


class Add(AsyncCommand[AddInputs, int]):
    """Add two numbers asynchronously"""

    async def execute(self) -> int:
        # Simulate async operation
        await asyncio.sleep(0)
        return self.inputs.a + self.inputs.b


class TestAsyncCommand:
    @pytest.mark.asyncio
    async def test_run_success(self):
        outcome = await Add.run(a=5, b=3)
        assert outcome.is_success()
        assert outcome.unwrap() == 8

    @pytest.mark.asyncio
    async def test_run_with_validation_error(self):
        outcome = await Add.run(a="not_a_number", b=3)
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
        assert Add.description() == "Add two numbers asynchronously"

    def test_manifest(self):
        manifest = Add.manifest()
        assert manifest["name"] == "Add"
        assert manifest["description"] == "Add two numbers asynchronously"
        assert "inputs_type" in manifest
        assert manifest["async"] is True


class TestAsyncCommandWithDomain:
    def test_async_command_decorator(self):
        @async_command(domain="Math", organization="TestOrg")
        class Multiply(AsyncCommand[AddInputs, int]):
            async def execute(self) -> int:
                return self.inputs.a * self.inputs.b

        assert Multiply._domain == "Math"
        assert Multiply._organization == "TestOrg"
        assert Multiply.full_name() == "TestOrg::Math::Multiply"


class TestAsyncCommandWithErrors:
    @pytest.mark.asyncio
    async def test_add_error_during_execute(self):
        class DivideInputs(BaseModel):
            a: int
            b: int

        class Divide(AsyncCommand[DivideInputs, float]):
            async def execute(self) -> float:
                if self.inputs.b == 0:
                    self.add_runtime_error(
                        symbol="division_by_zero",
                        message="Cannot divide by zero"
                    )
                    return None
                return self.inputs.a / self.inputs.b

        # Normal case
        outcome = await Divide.run(a=10, b=2)
        assert outcome.is_success()
        assert outcome.unwrap() == 5.0

        # Error case
        outcome = await Divide.run(a=10, b=0)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "division_by_zero"

    @pytest.mark.asyncio
    async def test_add_input_error(self):
        class ValidateInputs(BaseModel):
            email: str

        class ValidateEmail(AsyncCommand[ValidateInputs, bool]):
            async def execute(self) -> bool:
                if "@" not in self.inputs.email:
                    self.add_input_error(
                        path=["email"],
                        symbol="invalid_format",
                        message="Email must contain @"
                    )
                    return False
                return True

        outcome = await ValidateEmail.run(email="invalid")
        assert outcome.is_failure()
        assert outcome.errors[0].path == ("email",)


class TestAsyncCommandExceptionHandling:
    @pytest.mark.asyncio
    async def test_exception_converted_to_error(self):
        class FailInputs(BaseModel):
            fail: bool = True

        class FailingCommand(AsyncCommand[FailInputs, str]):
            async def execute(self) -> str:
                if self.inputs.fail:
                    raise ValueError("Something went wrong")
                return "success"

        outcome = await FailingCommand.run(fail=True)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "execution_error"
        assert "Something went wrong" in outcome.errors[0].message


class TestAsyncSimpleCommand:
    @pytest.mark.asyncio
    async def test_async_simple_command_decorator(self):
        @async_simple_command
        async def multiply(a: int, b: int) -> int:
            await asyncio.sleep(0)
            return a * b

        outcome = await multiply.run(a=3, b=4)
        assert outcome.is_success()
        assert outcome.unwrap() == 12

    @pytest.mark.asyncio
    async def test_async_simple_command_validation(self):
        @async_simple_command
        async def add(a: int, b: int) -> int:
            return a + b

        outcome = await add.run(a="not_int", b=3)
        assert outcome.is_failure()

    @pytest.mark.asyncio
    async def test_async_simple_command_direct_call(self):
        @async_simple_command
        async def add(a: int, b: int) -> int:
            return a + b

        result = await add(a=5, b=3)
        assert result == 8

    def test_async_simple_command_schema(self):
        @async_simple_command
        async def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        schema = greet.inputs_schema()
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "greeting" in schema["properties"]

    def test_async_simple_command_requires_async_function(self):
        with pytest.raises(TypeError, match="async_simple_command requires an async function"):
            @async_simple_command
            def sync_function(x: int) -> int:
                return x * 2

    @pytest.mark.asyncio
    async def test_async_simple_command_exception_handling(self):
        @async_simple_command
        async def failing_func(x: int) -> int:
            raise RuntimeError("Async failure")

        outcome = await failing_func.run(x=1)
        assert outcome.is_failure()
        assert outcome.errors[0].symbol == "execution_error"
        assert "Async failure" in outcome.errors[0].message


class TestAsyncCommandConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Test that multiple async commands can run concurrently"""
        class SlowAddInputs(BaseModel):
            a: int
            delay: float = 0.01

        class SlowAdd(AsyncCommand[SlowAddInputs, int]):
            async def execute(self) -> int:
                await asyncio.sleep(self.inputs.delay)
                return self.inputs.a + 1

        # Run multiple commands concurrently
        tasks = [
            SlowAdd.run(a=1, delay=0.01),
            SlowAdd.run(a=2, delay=0.01),
            SlowAdd.run(a=3, delay=0.01),
        ]
        outcomes = await asyncio.gather(*tasks)

        # All should succeed
        assert all(o.is_success() for o in outcomes)
        results = [o.unwrap() for o in outcomes]
        assert results == [2, 3, 4]
