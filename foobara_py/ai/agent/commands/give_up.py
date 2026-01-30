"""
GiveUp - Agent command to abandon the current goal.

This command allows the agent to signal that it cannot accomplish
the current goal and wishes to give up.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from foobara_py.core.command import Command


class GiveUpInputs(BaseModel):
    """Inputs for GiveUp command."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any = Field(..., description="The agent instance")
    message_to_user: Optional[str] = Field(
        None, description="Optional message to the user explaining why you decided to give up"
    )


class GiveUp(Command[GiveUpInputs, None]):
    """
    Give up on the current goal.

    Use this command when you determine that the goal cannot be accomplished
    with the available commands and information.
    """

    def execute(self) -> None:
        agent = self.inputs.agent
        message = self.inputs.message_to_user

        agent.give_up(message)
        return None
