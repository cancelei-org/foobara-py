"""
ListCommands - Lists available commands for the agent.

This command allows the agent to discover what commands are available
to accomplish its goal.
"""

from typing import Any, List

from pydantic import BaseModel, Field

from foobara_py.core.command import Command


class ListCommandsInputs(BaseModel):
    """Inputs for ListCommands command."""

    agent: Any = Field(..., description="The agent instance")

    class Config:
        arbitrary_types_allowed = True


class ListCommandsResult(BaseModel):
    """Result of ListCommands command."""

    user_provided_commands: List[str] = Field(
        ...,
        description="List of commands the user would like you to choose from to accomplish the goal",
    )
    agent_specific_commands: List[str] = Field(
        ..., description="Commands available to all agents to introspect or end the session"
    )


class ListCommands(Command[ListCommandsInputs, ListCommandsResult]):
    """
    List available commands for the agent.

    Returns two lists:
    - user_provided_commands: Commands registered by the user for the agent to use
    - agent_specific_commands: Built-in agent commands for introspection and control
    """

    def execute(self) -> ListCommandsResult:
        agent = self.inputs.agent

        user_provided = []
        agent_specific = []

        for name, cmd in agent.commands.items():
            if cmd.get("is_agent_command", False):
                agent_specific.append(name)
            else:
                user_provided.append(name)

        return ListCommandsResult(
            user_provided_commands=user_provided,
            agent_specific_commands=agent_specific,
        )
