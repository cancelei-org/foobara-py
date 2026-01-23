"""
NotifyUserThatCurrentGoalHasBeenAccomplished - Signals goal completion.

This command allows the agent to signal that it has successfully
accomplished the current goal and provide a result.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from foobara_py.core.command import Command


class NotifyAccomplishedInputs(BaseModel):
    """Inputs for NotifyUserThatCurrentGoalHasBeenAccomplished command."""

    agent: Any = Field(..., description="The agent instance")
    result: Optional[Any] = Field(None, description="The result data to return to the user")
    message_to_user: Optional[str] = Field(
        None, description="Message to the user about what was done"
    )

    class Config:
        arbitrary_types_allowed = True


class NotifyUserThatCurrentGoalHasBeenAccomplished(Command[NotifyAccomplishedInputs, None]):
    """
    Notify the user that the current goal has been accomplished.

    Use this command when you have successfully completed the goal.
    Provide the result data and an optional message explaining what was done.

    The user might issue a new goal after this.
    """

    def execute(self) -> None:
        agent = self.inputs.agent
        result = self.inputs.result
        message = self.inputs.message_to_user

        agent.mark_mission_accomplished(result, message)
        return None
