"""
Agent Built-in Commands.

These commands are available to all agents for introspection
and control flow.
"""

from foobara_py.ai.agent.commands.describe_command import (
    DescribeCommand,
    DescribeCommandInputs,
    DescribeCommandResult,
)
from foobara_py.ai.agent.commands.give_up import (
    GiveUp,
    GiveUpInputs,
)
from foobara_py.ai.agent.commands.list_commands import (
    ListCommands,
    ListCommandsInputs,
    ListCommandsResult,
)
from foobara_py.ai.agent.commands.notify_accomplished import (
    NotifyAccomplishedInputs,
    NotifyUserThatCurrentGoalHasBeenAccomplished,
)

__all__ = [
    # ListCommands
    "ListCommands",
    "ListCommandsInputs",
    "ListCommandsResult",
    # DescribeCommand
    "DescribeCommand",
    "DescribeCommandInputs",
    "DescribeCommandResult",
    # GiveUp
    "GiveUp",
    "GiveUpInputs",
    # NotifyUserThatCurrentGoalHasBeenAccomplished
    "NotifyUserThatCurrentGoalHasBeenAccomplished",
    "NotifyAccomplishedInputs",
]
