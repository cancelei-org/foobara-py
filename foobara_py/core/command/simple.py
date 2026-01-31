"""
SimpleCommand and AsyncSimpleCommand - Decorator-based commands for functions.

Maintained for V1 compatibility. Provides a lightweight decorator pattern
for converting simple functions into commands.
"""

import inspect
from typing import Any, Generic, TypeVar, get_type_hints

from pydantic import ValidationError, create_model

from foobara_py.core.errors import DataError, ErrorCollection
from foobara_py.core.outcome import CommandOutcome

ResultT = TypeVar("ResultT")


class SimpleCommand(Generic[ResultT]):
    """
    Simplified command for functions (decorator-based).

    Usage:
        @simple_command
        def add_numbers(a: int, b: int) -> int:
            return a + b

        outcome = add_numbers.run(a=1, b=2)
        result = outcome.unwrap()  # 3
    """

    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__

        # Extract type hints
        self._hints = get_type_hints(func)
        self._return_type = self._hints.pop("return", Any)

        # Build inputs model dynamically
        sig = inspect.signature(func)
        fields = {}
        for param_name, param in sig.parameters.items():
            param_type = self._hints.get(param_name, Any)
            if param.default is inspect.Parameter.empty:
                fields[param_name] = (param_type, ...)
            else:
                fields[param_name] = (param_type, param.default)

        self._inputs_model = create_model(f"{func.__name__}Inputs", **fields)

    def inputs_schema(self) -> dict:
        """Get JSON Schema for inputs"""
        return self._inputs_model.model_json_schema()

    def run(self, **inputs) -> CommandOutcome[ResultT]:
        """Run the command with given inputs"""
        errors = ErrorCollection()

        # Validate inputs
        try:
            validated = self._inputs_model(**inputs)
        except ValidationError as e:
            for error in e.errors():
                path = [str(p) for p in error["loc"]]
                errors.add_error(
                    DataError(
                        category="data", symbol=error["type"], path=path, message=error["msg"]
                    )
                )
            return CommandOutcome.from_errors(*errors.all())

        # Execute function
        try:
            result = self.func(**validated.model_dump())
            return CommandOutcome.from_result(result)
        except Exception as e:
            return CommandOutcome.from_errors(
                DataError.runtime_error(symbol="execution_error", message=str(e))
            )

    def __call__(self, **inputs) -> ResultT:
        """Direct call returns result or raises"""
        outcome = self.run(**inputs)
        return outcome.unwrap()


def simple_command(func):
    """Decorator to create SimpleCommand from function"""
    return SimpleCommand(func)


class AsyncSimpleCommand(Generic[ResultT]):
    """
    Simplified async command for async functions (decorator-based).

    Usage:
        @async_simple_command
        async def fetch_user(user_id: int) -> User:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"/users/{user_id}") as resp:
                    return User(**(await resp.json()))

        outcome = await fetch_user.run(user_id=123)
        result = outcome.unwrap()
    """

    def __init__(self, func):
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"async_simple_command requires an async function, "
                f"got {type(func).__name__}. Use @simple_command for sync functions."
            )
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__

        # Extract type hints
        self._hints = get_type_hints(func)
        self._return_type = self._hints.pop("return", Any)

        # Build inputs model dynamically
        sig = inspect.signature(func)
        fields = {}
        for param_name, param in sig.parameters.items():
            param_type = self._hints.get(param_name, Any)
            if param.default is inspect.Parameter.empty:
                fields[param_name] = (param_type, ...)
            else:
                fields[param_name] = (param_type, param.default)

        self._inputs_model = create_model(f"{func.__name__}Inputs", **fields)

    def inputs_schema(self) -> dict:
        """Get JSON Schema for inputs"""
        return self._inputs_model.model_json_schema()

    async def run(self, **inputs) -> CommandOutcome[ResultT]:
        """Run the async command with given inputs"""
        errors = ErrorCollection()

        # Validate inputs
        try:
            validated = self._inputs_model(**inputs)
        except ValidationError as e:
            for error in e.errors():
                path = [str(p) for p in error["loc"]]
                errors.add_error(
                    DataError(
                        category="data", symbol=error["type"], path=path, message=error["msg"]
                    )
                )
            return CommandOutcome.from_errors(*errors.all())

        # Execute async function
        try:
            result = await self.func(**validated.model_dump())
            return CommandOutcome.from_result(result)
        except Exception as e:
            return CommandOutcome.from_errors(
                DataError.runtime_error(symbol="execution_error", message=str(e))
            )

    async def __call__(self, **inputs) -> ResultT:
        """Direct call returns result or raises"""
        outcome = await self.run(**inputs)
        return outcome.unwrap()


def async_simple_command(func):
    """Decorator to create AsyncSimpleCommand from async function"""
    return AsyncSimpleCommand(func)
