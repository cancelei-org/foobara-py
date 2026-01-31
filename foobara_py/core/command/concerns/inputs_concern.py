"""
InputsConcern - Input handling and validation for commands.

Handles:
- Raw input storage
- Pydantic validation
- Validated input access
- Error collection from validation

Pattern: Ruby Foobara's Inputs concern
"""

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from foobara_py.core.errors import FoobaraError
from foobara_py.core.utils import validate_with_model

InputT = TypeVar("InputT", bound=BaseModel)


class InputsConcern(Generic[InputT]):
    """Mixin for input handling and validation."""

    # Instance attributes (defined in __slots__ in Command)
    _raw_inputs: Dict[str, Any]
    _inputs: Optional[InputT]

    @property
    def inputs(self) -> InputT:
        """
        Get validated inputs.

        Returns:
            Validated and typed inputs object

        Raises:
            ValueError: If inputs not yet validated
        """
        if self._inputs is None:
            raise ValueError("Inputs not yet validated")
        return self._inputs

    def cast_and_validate_inputs(self) -> None:
        """
        Cast and validate raw inputs using Pydantic model.

        Converts raw input dictionary to a strongly-typed Pydantic model instance,
        performing type coercion and validation. Validation errors are collected
        and added to the command's error list rather than raising exceptions.

        Raises:
            Halt: If validation errors occur (via add_error)

        Note:
            Runs automatically during command execution before execute().
            Override inputs_type() to customize the validation model.
        """
        try:
            self._inputs = validate_with_model(self.inputs_type(), self._raw_inputs)
        except ValidationError as e:
            for error in e.errors():
                path = tuple(str(p) for p in error["loc"])
                self.add_error(
                    FoobaraError(
                        category="data",
                        symbol=error["type"],
                        path=path,
                        message=error["msg"],
                        context={"input": error.get("input")},
                    )
                )
