"""
DescribeCommand - Describes a command's interface.

This command allows the agent to get detailed information about
a specific command's inputs and outputs.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from foobara_py.core.command import Command


class DescribeCommandInputs(BaseModel):
    """Inputs for DescribeCommand command."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any = Field(..., description="The agent instance")
    command_name: str = Field(..., description="Name of the command to describe")


class DescribeCommandResult(BaseModel):
    """Result of DescribeCommand command."""

    full_command_name: str = Field(..., description="Full name of the command")
    description: Optional[str] = Field(None, description="Description of what the command does")
    inputs_type: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for command inputs"
    )
    result_type: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for command result"
    )


class DescribeCommand(Command[DescribeCommandInputs, DescribeCommandResult]):
    """
    Describe a command's interface.

    Returns the command's name, description, and JSON schemas for
    its inputs and result types.
    """

    def execute(self) -> DescribeCommandResult:
        agent = self.inputs.agent
        command_name = self.inputs.command_name

        command_info = agent.commands.get(command_name)
        if not command_info:
            raise ValueError(f"Command '{command_name}' not found")

        command_class = command_info["command_class"]

        # Get description
        description = getattr(command_class, "__description__", None)
        if description is None:
            description = command_class.__doc__

        # Get input schema
        inputs_type = None
        if hasattr(command_class, "__orig_bases__") and command_class.__orig_bases__:
            try:
                inputs_model = command_class.__orig_bases__[0].__args__[0]
                if hasattr(inputs_model, "model_json_schema"):
                    inputs_type = inputs_model.model_json_schema()
            except (IndexError, AttributeError):
                pass

        # Get result schema
        result_type = None
        if hasattr(command_class, "__orig_bases__") and command_class.__orig_bases__:
            try:
                result_model = command_class.__orig_bases__[0].__args__[1]
                if hasattr(result_model, "model_json_schema"):
                    result_type = result_model.model_json_schema()
                else:
                    # Simple types
                    result_type = {"type": self._python_type_to_json_type(result_model)}
            except (IndexError, AttributeError):
                pass

        # Mark command as described
        agent.described_commands.add(command_name)

        return DescribeCommandResult(
            full_command_name=command_name,
            description=description,
            inputs_type=inputs_type,
            result_type=result_type,
        )

    def _python_type_to_json_type(self, python_type: type) -> str:
        """Convert Python type to JSON schema type."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return type_map.get(python_type, "string")
