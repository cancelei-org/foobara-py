"""
AI Framework Type Definitions.

Defines types used by LLM-backed commands and AI agents.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GoalState(str, Enum):
    """Possible states for a goal."""

    ACCOMPLISHED = "accomplished"
    KILLED = "killed"
    FAILED = "failed"
    ERROR = "error"
    GAVE_UP = "gave_up"


class Goal(BaseModel):
    """A goal for the agent to accomplish."""

    text: str = Field(..., description="The goal text describing what should be accomplished")
    state: Optional[GoalState] = Field(default=None, description="Current state of the goal")


class CommandOutcome(BaseModel):
    """Outcome of a command execution."""

    success: bool = Field(..., description="Whether the command succeeded or not")
    result: Optional[Any] = Field(default=None, description="Result of the command")
    errors_hash: Optional[Dict[str, Any]] = Field(
        default=None, description="Errors that occurred during the command"
    )


class CommandLogEntry(BaseModel):
    """A log entry for a command that was run by the agent."""

    command_name: str = Field(..., description="Name of the command that was run")
    inputs: Optional[Dict[str, Any]] = Field(default=None, description="Inputs to the command")
    outcome: CommandOutcome = Field(..., description="Outcome of the command")

    def is_success(self) -> bool:
        """Check if the command succeeded."""
        return self.outcome.success


class Context(BaseModel):
    """Context for agent execution containing goals and command history."""

    current_goal: Goal = Field(..., description="The current goal being worked on")
    previous_goals: List[Goal] = Field(
        default_factory=list, description="Previously completed goals"
    )
    command_log: List[CommandLogEntry] = Field(
        default_factory=list, description="Log of commands executed during this goal"
    )


class AssociationDepth(str, Enum):
    """Depth of association serialization."""

    ATOM = "atom"
    AGGREGATE = "aggregate"
    PRIMARY_KEY_ONLY = "primary_key_only"
