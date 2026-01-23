"""
AI Agent Framework.

Provides an AI-powered agent that can accomplish goals using
registered commands and LLM-backed decision making.

Usage:
    from foobara_py.ai.agent import Agent

    # Create agent
    agent = Agent()

    # Register commands
    agent.register_command(MyCommand)
    agent.register_command(AnotherCommand)

    # Accomplish a goal
    result = agent.accomplish_goal("Do something useful")

    if result.success:
        print(f"Result: {result.result}")
        print(f"Message: {result.message_to_user}")
    else:
        print(f"Failed: {result.message_to_user}")
"""

from foobara_py.ai.agent.accomplish_goal import (
    AccomplishGoal,
    AccomplishGoalInputs,
    AccomplishGoalResult,
)
from foobara_py.ai.agent.agent import Agent, AgentResult, AgentState
from foobara_py.ai.agent.commands import (
    DescribeCommand,
    DescribeCommandInputs,
    DescribeCommandResult,
    GiveUp,
    GiveUpInputs,
    ListCommands,
    ListCommandsInputs,
    ListCommandsResult,
    NotifyAccomplishedInputs,
    NotifyUserThatCurrentGoalHasBeenAccomplished,
)
from foobara_py.ai.agent.determine_next_command import (
    DetermineNextCommandInputs,
    DetermineNextCommandNameAndInputs,
    DetermineNextCommandResult,
)

__all__ = [
    # Main classes
    "Agent",
    "AgentState",
    "AgentResult",
    # AccomplishGoal
    "AccomplishGoal",
    "AccomplishGoalInputs",
    "AccomplishGoalResult",
    # DetermineNextCommand
    "DetermineNextCommandNameAndInputs",
    "DetermineNextCommandInputs",
    "DetermineNextCommandResult",
    # Built-in commands
    "ListCommands",
    "ListCommandsInputs",
    "ListCommandsResult",
    "DescribeCommand",
    "DescribeCommandInputs",
    "DescribeCommandResult",
    "GiveUp",
    "GiveUpInputs",
    "NotifyUserThatCurrentGoalHasBeenAccomplished",
    "NotifyAccomplishedInputs",
]
