"""
AI Agent Implementation.

The Agent class provides an AI-powered command execution system
that can accomplish goals using a set of registered commands.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar

from pydantic import BaseModel

from foobara_py.ai.llm_backed_command import LlmProvider, get_default_llm_provider
from foobara_py.ai.types import (
    CommandLogEntry,
    Context,
    Goal,
    GoalState,
)
from foobara_py.ai.types import (
    CommandOutcome as CommandOutcomeType,
)
from foobara_py.core.command import Command, CommandOutcome


class AgentState(str, Enum):
    """State machine states for the agent."""

    INITIALIZED = "initialized"
    IDLE = "idle"
    ACCOMPLISHING_GOAL = "accomplishing_goal"
    WAITING_FOR_NEXT_GOAL = "waiting_for_next_goal"
    GIVING_UP = "giving_up"
    MISSION_ACCOMPLISHED = "mission_accomplished"


class Agent:
    """
    An AI Agent that can accomplish goals using registered commands.

    The agent uses an LLM to determine which commands to run and with
    what inputs in order to accomplish the given goal.

    Usage:
        # Create an agent
        agent = Agent(llm_model="claude-sonnet-4-20250514")

        # Register commands the agent can use
        agent.register_command(MyCommand)
        agent.register_command(AnotherCommand)

        # Accomplish a goal
        result = agent.accomplish_goal("Do something useful")
        print(result.message_to_user)
        print(result.result)

    The agent has a built-in state machine:
    - initialized: Agent is created but not started
    - idle: Agent is waiting for a goal
    - accomplishing_goal: Agent is working on a goal
    - waiting_for_next_goal: Agent completed a goal and is waiting for another
    - giving_up: Agent decided to give up on the current goal
    - mission_accomplished: Agent successfully completed the goal
    """

    def __init__(
        self,
        llm_provider: Optional[LlmProvider] = None,
        llm_model: Optional[str] = None,
        max_iterations: int = 100,
        verbose: bool = False,
    ):
        """
        Initialize the agent.

        Args:
            llm_provider: The LLM provider to use (default: global default)
            llm_model: Specific model to use (overrides provider default)
            max_iterations: Maximum command iterations per goal
            verbose: Whether to print debug information
        """
        self.llm_provider = llm_provider or get_default_llm_provider()
        self.llm_model = llm_model
        self.max_iterations = max_iterations
        self.verbose = verbose

        # Command registry: name -> {command_class, is_agent_command}
        self.commands: Dict[str, Dict[str, Any]] = {}

        # State
        self.state = AgentState.INITIALIZED
        self.context: Optional[Context] = None
        self.described_commands: Set[str] = set()

        # Results
        self.final_result: Any = None
        self.final_message: Optional[str] = None

        # Register built-in agent commands
        self._register_builtin_commands()

    def _register_builtin_commands(self) -> None:
        """Register the built-in agent commands."""
        from foobara_py.ai.agent.commands import (
            DescribeCommand,
            GiveUp,
            ListCommands,
            NotifyUserThatCurrentGoalHasBeenAccomplished,
        )

        self._register_command_internal(
            "Agent::ListCommands",
            ListCommands,
            is_agent_command=True,
        )
        self._register_command_internal(
            "Agent::DescribeCommand",
            DescribeCommand,
            is_agent_command=True,
        )
        self._register_command_internal(
            "Agent::GiveUp",
            GiveUp,
            is_agent_command=True,
        )
        self._register_command_internal(
            "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished",
            NotifyUserThatCurrentGoalHasBeenAccomplished,
            is_agent_command=True,
        )

    def _register_command_internal(
        self,
        name: str,
        command_class: Type[Command],
        is_agent_command: bool = False,
    ) -> None:
        """Internal method to register a command."""
        self.commands[name] = {
            "command_class": command_class,
            "is_agent_command": is_agent_command,
        }

    def register_command(
        self,
        command_class: Type[Command],
        name: Optional[str] = None,
    ) -> "Agent":
        """
        Register a command that the agent can use.

        Args:
            command_class: The command class to register
            name: Optional custom name (defaults to class name)

        Returns:
            self for chaining
        """
        if name is None:
            name = command_class.__name__

        self._register_command_internal(name, command_class, is_agent_command=False)
        return self

    def register_commands(self, *command_classes: Type[Command]) -> "Agent":
        """
        Register multiple commands at once.

        Args:
            command_classes: Command classes to register

        Returns:
            self for chaining
        """
        for command_class in command_classes:
            self.register_command(command_class)
        return self

    def accomplish_goal(self, goal_text: str) -> "AgentResult":
        """
        Accomplish a goal using the registered commands.

        Args:
            goal_text: Description of the goal to accomplish

        Returns:
            AgentResult containing the outcome
        """
        from foobara_py.ai.agent.accomplish_goal import AccomplishGoal

        # Initialize context
        goal = Goal(text=goal_text)
        self.context = Context(
            current_goal=goal,
            previous_goals=[],
            command_log=[],
        )

        # Reset state
        self.state = AgentState.ACCOMPLISHING_GOAL
        self.described_commands = set()
        self.final_result = None
        self.final_message = None

        if self.verbose:
            print(f"[Agent] Starting goal: {goal_text}")

        # Run the accomplish goal loop
        outcome = AccomplishGoal.run(agent=self)

        if outcome.is_failure():
            return AgentResult(
                success=False,
                result=None,
                message_to_user=f"Agent failed: {outcome.errors}",
                goal_state=GoalState.ERROR,
            )

        # Return based on final state
        if self.state == AgentState.MISSION_ACCOMPLISHED:
            return AgentResult(
                success=True,
                result=self.final_result,
                message_to_user=self.final_message,
                goal_state=GoalState.ACCOMPLISHED,
            )
        elif self.state == AgentState.GIVING_UP:
            return AgentResult(
                success=False,
                result=None,
                message_to_user=self.final_message or "Agent gave up",
                goal_state=GoalState.GAVE_UP,
            )
        else:
            return AgentResult(
                success=False,
                result=None,
                message_to_user="Agent reached maximum iterations",
                goal_state=GoalState.FAILED,
            )

    def run_command(self, command_name: str, inputs: Dict[str, Any]) -> CommandOutcome:
        """
        Run a command by name with given inputs.

        Args:
            command_name: Name of the command to run
            inputs: Inputs to pass to the command

        Returns:
            CommandOutcome from the command execution
        """
        if command_name not in self.commands:
            # Return a failure outcome
            from foobara_py.core.errors import DataError

            return CommandOutcome.from_errors(
                DataError.runtime_error(
                    symbol="command_not_found",
                    message=f"Command '{command_name}' not found",
                )
            )

        command_info = self.commands[command_name]
        command_class = command_info["command_class"]

        # Inject agent for built-in commands
        if command_info["is_agent_command"]:
            inputs = {"agent": self, **inputs}

        return command_class.run(**inputs)

    def log_command(
        self,
        command_name: str,
        inputs: Dict[str, Any],
        outcome: CommandOutcome,
    ) -> None:
        """Log a command execution to the context."""
        if self.context is None:
            return

        # Convert outcome to loggable format
        result = None
        errors_hash = None

        if outcome.is_success():
            result = outcome.result
            # Try to serialize if it's a model
            if hasattr(result, "model_dump"):
                result = result.model_dump()
        else:
            errors_hash = {
                "errors": [
                    {"symbol": e.symbol, "message": str(e.message)} for e in (outcome.errors or [])
                ]
            }

        entry = CommandLogEntry(
            command_name=command_name,
            inputs=inputs,
            outcome=CommandOutcomeType(
                success=outcome.is_success(),
                result=result,
                errors_hash=errors_hash,
            ),
        )

        self.context.command_log.append(entry)

        if self.verbose:
            status = "SUCCESS" if outcome.is_success() else "FAILED"
            print(f"[Agent] {command_name} -> {status}")

    def give_up(self, message: Optional[str] = None) -> None:
        """Mark the agent as giving up on the current goal."""
        self.state = AgentState.GIVING_UP
        self.final_message = message

        if self.context:
            self.context.current_goal.state = GoalState.GAVE_UP

        if self.verbose:
            print(f"[Agent] Giving up: {message}")

    def mark_mission_accomplished(
        self,
        result: Any = None,
        message: Optional[str] = None,
    ) -> None:
        """Mark the current goal as accomplished."""
        self.state = AgentState.MISSION_ACCOMPLISHED
        self.final_result = result
        self.final_message = message

        if self.context:
            self.context.current_goal.state = GoalState.ACCOMPLISHED

        if self.verbose:
            print(f"[Agent] Mission accomplished: {message}")

    @property
    def is_done(self) -> bool:
        """Check if the agent is done (accomplished or gave up)."""
        return self.state in (
            AgentState.MISSION_ACCOMPLISHED,
            AgentState.GIVING_UP,
        )


class AgentResult(BaseModel):
    """Result of an agent goal execution."""

    success: bool
    result: Any = None
    message_to_user: Optional[str] = None
    goal_state: GoalState

    class Config:
        arbitrary_types_allowed = True
