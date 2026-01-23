"""
Agent-Backed Command Implementation.

Provides a command class whose execution is backed by an AI agent.
The agent uses registered commands to accomplish the command's goal.
"""

import json
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field

from foobara_py.ai.agent import Agent, AgentResult
from foobara_py.ai.llm_backed_command import LlmProvider, get_default_llm_provider
from foobara_py.ai.types import Context, GoalState
from foobara_py.core.command import Command

InputsT = TypeVar("InputsT", bound=BaseModel)
ResultT = TypeVar("ResultT")


class AgentBackedCommandError(Exception):
    """Error raised when agent-backed command fails."""

    pass


class GaveUpError(AgentBackedCommandError):
    """Error raised when the agent gives up."""

    def __init__(self, reason: Optional[str] = None):
        super().__init__(f"Agent gave up: {reason}" if reason else "Agent gave up")
        self.reason = reason


class TooManyCommandCallsError(AgentBackedCommandError):
    """Error raised when agent exceeds maximum command calls."""

    def __init__(self, maximum_command_calls: int):
        super().__init__(f"Exceeded maximum command calls: {maximum_command_calls}")
        self.maximum_command_calls = maximum_command_calls


class AgentBackedCommand(Command[InputsT, ResultT], Generic[InputsT, ResultT]):
    """
    A command whose execution is backed by an AI agent.

    The agent uses registered commands to accomplish the command's goal,
    which is automatically constructed from the command name and description.

    Usage:
        class ResearchTopicInputs(BaseModel):
            topic: str
            depth: str = "brief"

        class ResearchTopicResult(BaseModel):
            summary: str
            sources: List[str]
            message_to_user: Optional[str] = None

        class ResearchTopic(AgentBackedCommand[ResearchTopicInputs, ResearchTopicResult]):
            __description__ = "Research a topic and provide a summary"
            __depends_on__ = [SearchWeb, ReadArticle, SummarizeText]

            # Optional configuration
            __llm_model__ = "claude-sonnet-4-20250514"
            __maximum_command_calls__ = 20
            __verbose__ = True

        outcome = ResearchTopic.run(topic="quantum computing", depth="detailed")
        if outcome.is_success():
            result = outcome.unwrap()
            print(result.summary)
    """

    # Class-level configuration
    __description__: str = ""
    __depends_on__: List[Type[Command]] = []
    __llm_provider__: Optional[LlmProvider] = None
    __llm_model__: Optional[str] = None
    __maximum_command_calls__: int = 25
    __verbose__: bool = False
    __agent_name__: Optional[str] = None

    # Instance state
    agent: Optional[Agent] = None
    goal: Optional[str] = None
    agent_outcome: Optional[AgentResult] = None

    def execute(self) -> ResultT:
        """Execute the agent-backed command."""
        self._build_agent_if_needed()
        self._construct_goal_if_needed()
        self._run_agent()
        self._handle_agent_outcome()
        return self._agent_result()

    def _build_agent_if_needed(self) -> None:
        """Build the agent with dependent commands."""
        if self.agent is not None:
            return

        # Get LLM provider
        llm_provider = self.__llm_provider__ or get_default_llm_provider()

        # Create agent
        self.agent = Agent(
            llm_provider=llm_provider,
            llm_model=self.__llm_model__,
            max_iterations=self.__maximum_command_calls__,
            verbose=self.__verbose__,
        )

        # Register dependent commands
        for command_class in self.__depends_on__:
            self.agent.register_command(command_class)

    def _construct_goal_if_needed(self) -> None:
        """Construct the goal from command metadata and inputs."""
        if self.goal is not None:
            return

        command_name = self.__class__.__name__

        # Build goal from command name
        goal_parts = []
        goal_parts.append(f"You are an agent backed command named {command_name}.")

        # Add description if available
        description = self.__description__
        if description:
            goal_parts.append(f"Your goal is: {description}")

        # Add inputs information
        inputs_dict = self.inputs.model_dump(exclude_none=True)
        if inputs_dict:
            # Get JSON schema for inputs
            inputs_schema = self.inputs.model_json_schema()
            goal_parts.append(
                f"\n\nThe inputs to this command have the following type:\n\n{json.dumps(inputs_schema, indent=2)}"
            )

            # Add actual input values
            goal_parts.append(
                f"\n\nYou have been run with the following inputs:\n\n{json.dumps(inputs_dict, indent=2)}"
            )

        self.goal = " ".join(goal_parts)

    def _run_agent(self) -> None:
        """Run the agent with the constructed goal."""
        self.agent_outcome = self.agent.accomplish_goal(self.goal)

    def _handle_agent_outcome(self) -> None:
        """Handle the agent's outcome, raising errors if needed."""
        if self.agent_outcome is None:
            raise AgentBackedCommandError("Agent did not produce an outcome")

        if not self.agent_outcome.success:
            if self.agent_outcome.goal_state == GoalState.GAVE_UP:
                raise GaveUpError(self.agent_outcome.message_to_user)
            elif self.agent_outcome.goal_state == GoalState.FAILED:
                raise TooManyCommandCallsError(self.__maximum_command_calls__)
            else:
                raise AgentBackedCommandError(f"Agent failed: {self.agent_outcome.message_to_user}")

    def _agent_result(self) -> ResultT:
        """Extract and format the result from the agent outcome."""
        if self.agent_outcome is None:
            return None

        result = self.agent_outcome.result

        # Try to get result type and validate
        try:
            result_type = self.__class__.__orig_bases__[0].__args__[1]
            if hasattr(result_type, "model_validate"):
                # It's a Pydantic model
                if isinstance(result, dict):
                    return result_type.model_validate(result)
        except (IndexError, AttributeError):
            pass

        return result


class AsyncAgentBackedCommand(Command[InputsT, ResultT], Generic[InputsT, ResultT]):
    """
    Async version of AgentBackedCommand.

    Note: Currently runs synchronously internally as the Agent
    doesn't have full async support yet.
    """

    __description__: str = ""
    __depends_on__: List[Type[Command]] = []
    __llm_provider__: Optional[LlmProvider] = None
    __llm_model__: Optional[str] = None
    __maximum_command_calls__: int = 25
    __verbose__: bool = False
    __agent_name__: Optional[str] = None

    agent: Optional[Agent] = None
    goal: Optional[str] = None
    agent_outcome: Optional[AgentResult] = None

    async def execute(self) -> ResultT:
        """Execute the agent-backed command asynchronously."""
        # Currently runs synchronously - future improvement
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute_sync)

    def _execute_sync(self) -> ResultT:
        """Synchronous execution helper."""
        self._build_agent_if_needed()
        self._construct_goal_if_needed()
        self._run_agent()
        self._handle_agent_outcome()
        return self._agent_result()

    def _build_agent_if_needed(self) -> None:
        """Build the agent with dependent commands."""
        if self.agent is not None:
            return

        llm_provider = self.__llm_provider__ or get_default_llm_provider()

        self.agent = Agent(
            llm_provider=llm_provider,
            llm_model=self.__llm_model__,
            max_iterations=self.__maximum_command_calls__,
            verbose=self.__verbose__,
        )

        for command_class in self.__depends_on__:
            self.agent.register_command(command_class)

    def _construct_goal_if_needed(self) -> None:
        """Construct the goal from command metadata and inputs."""
        if self.goal is not None:
            return

        command_name = self.__class__.__name__
        goal_parts = [f"You are an agent backed command named {command_name}."]

        description = self.__description__
        if description:
            goal_parts.append(f"Your goal is: {description}")

        inputs_dict = self.inputs.model_dump(exclude_none=True)
        if inputs_dict:
            inputs_schema = self.inputs.model_json_schema()
            goal_parts.append(
                f"\n\nThe inputs to this command have the following type:\n\n{json.dumps(inputs_schema, indent=2)}"
            )
            goal_parts.append(
                f"\n\nYou have been run with the following inputs:\n\n{json.dumps(inputs_dict, indent=2)}"
            )

        self.goal = " ".join(goal_parts)

    def _run_agent(self) -> None:
        """Run the agent with the constructed goal."""
        self.agent_outcome = self.agent.accomplish_goal(self.goal)

    def _handle_agent_outcome(self) -> None:
        """Handle the agent's outcome, raising errors if needed."""
        if self.agent_outcome is None:
            raise AgentBackedCommandError("Agent did not produce an outcome")

        if not self.agent_outcome.success:
            if self.agent_outcome.goal_state == GoalState.GAVE_UP:
                raise GaveUpError(self.agent_outcome.message_to_user)
            elif self.agent_outcome.goal_state == GoalState.FAILED:
                raise TooManyCommandCallsError(self.__maximum_command_calls__)
            else:
                raise AgentBackedCommandError(f"Agent failed: {self.agent_outcome.message_to_user}")

    def _agent_result(self) -> ResultT:
        """Extract and format the result from the agent outcome."""
        if self.agent_outcome is None:
            return None

        result = self.agent_outcome.result

        try:
            result_type = self.__class__.__orig_bases__[0].__args__[1]
            if hasattr(result_type, "model_validate"):
                if isinstance(result, dict):
                    return result_type.model_validate(result)
        except (IndexError, AttributeError):
            pass

        return result
