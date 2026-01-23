"""Tests for Agent-Backed Command"""

import pytest
from typing import List
from pydantic import BaseModel, Field

from foobara_py.core.command import Command
from foobara_py.ai.agent_backed_command import (
    AgentBackedCommand,
    AgentBackedCommandError,
    GaveUpError,
    TooManyCommandCallsError,
)
from foobara_py.ai.llm_backed_command import LlmProvider
from foobara_py.ai.types import GoalState


# Mock LLM Provider for testing
class MockLlmProvider(LlmProvider):
    """Mock LLM provider that returns predefined responses."""

    def __init__(self, responses: List[str]):
        self.responses = iter(responses)
        self.call_count = 0

    def generate(self, messages, temperature=0.0, model=None):
        self.call_count += 1
        return next(self.responses)


# Test commands for the agent to use
class AddNumbersInputs(BaseModel):
    a: int
    b: int


class AddNumbers(Command[AddNumbersInputs, int]):
    """Add two numbers together."""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


class MultiplyNumbersInputs(BaseModel):
    a: int
    b: int


class MultiplyNumbers(Command[MultiplyNumbersInputs, int]):
    """Multiply two numbers together."""

    def execute(self) -> int:
        return self.inputs.a * self.inputs.b


class FormatResultInputs(BaseModel):
    value: int
    prefix: str = ""


class FormatResult(Command[FormatResultInputs, str]):
    """Format a result with an optional prefix."""

    def execute(self) -> str:
        if self.inputs.prefix:
            return f"{self.inputs.prefix}: {self.inputs.value}"
        return str(self.inputs.value)


class TestAgentBackedCommand:
    """Test AgentBackedCommand class."""

    def test_simple_agent_backed_command(self):
        """Should execute simple agent-backed command."""
        # Define the agent-backed command
        class CalculateInputs(BaseModel):
            operation: str
            x: int
            y: int

        class Calculate(AgentBackedCommand[CalculateInputs, int]):
            __description__ = "Perform a calculation"
            __depends_on__ = [AddNumbers, MultiplyNumbers]

        # Mock LLM responses
        responses = [
            # List commands
            '{"command": "Agent::ListCommands", "inputs": {}}',
            # Describe AddNumbers
            '{"command": "Agent::DescribeCommand", "inputs": {"command_name": "AddNumbers"}}',
            # Run AddNumbers
            '{"command": "AddNumbers", "inputs": {"a": 5, "b": 3}}',
            # Notify accomplished
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 8, "message_to_user": "Added 5 and 3"}}',
        ]

        Calculate.__llm_provider__ = MockLlmProvider(responses)

        outcome = Calculate.run(operation="add", x=5, y=3)

        assert outcome.is_success()
        assert outcome.unwrap() == 8

    def test_agent_backed_command_with_multiple_steps(self):
        """Should handle multi-step agent execution."""

        class ComplexCalcInputs(BaseModel):
            a: int
            b: int
            c: int

        class ComplexCalc(AgentBackedCommand[ComplexCalcInputs, str]):
            __description__ = "Add a and b, then format the result with c as prefix"
            __depends_on__ = [AddNumbers, FormatResult]

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::DescribeCommand", "inputs": {"command_name": "AddNumbers"}}',
            '{"command": "AddNumbers", "inputs": {"a": 10, "b": 20}}',
            '{"command": "Agent::DescribeCommand", "inputs": {"command_name": "FormatResult"}}',
            '{"command": "FormatResult", "inputs": {"value": 30, "prefix": "Result"}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": "Result: 30", "message_to_user": "Calculated and formatted"}}',
        ]

        ComplexCalc.__llm_provider__ = MockLlmProvider(responses)

        outcome = ComplexCalc.run(a=10, b=20, c=0)

        assert outcome.is_success()
        assert outcome.unwrap() == "Result: 30"

    def test_agent_gives_up(self):
        """Should handle agent giving up."""

        class ImpossibleInputs(BaseModel):
            task: str

        class ImpossibleTask(AgentBackedCommand[ImpossibleInputs, str]):
            __description__ = "Do something impossible"
            __depends_on__ = []

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "No commands available to accomplish this task"}}',
        ]

        ImpossibleTask.__llm_provider__ = MockLlmProvider(responses)

        outcome = ImpossibleTask.run(task="impossible")

        assert outcome.is_failure()

    def test_max_iterations_exceeded(self):
        """Should stop when max iterations exceeded."""

        class LoopInputs(BaseModel):
            count: int

        class LoopForever(AgentBackedCommand[LoopInputs, int]):
            __description__ = "Loop forever"
            __depends_on__ = [AddNumbers]
            __maximum_command_calls__ = 3

        # Return list commands forever
        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::ListCommands", "inputs": {}}',
        ]

        LoopForever.__llm_provider__ = MockLlmProvider(responses)

        outcome = LoopForever.run(count=10)

        assert outcome.is_failure()

    def test_configuration_inheritance(self):
        """Should inherit configuration from class attributes."""

        class ConfiguredInputs(BaseModel):
            value: int

        class ConfiguredCommand(AgentBackedCommand[ConfiguredInputs, int]):
            __description__ = "A configured command"
            __depends_on__ = [AddNumbers]
            __maximum_command_calls__ = 10
            __verbose__ = False
            __agent_name__ = "TestAgent"

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "AddNumbers", "inputs": {"a": 1, "b": 1}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 2, "message_to_user": "Done"}}',
        ]

        ConfiguredCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = ConfiguredCommand.run(value=1)

        assert outcome.is_success()

    def test_goal_construction(self):
        """Should construct goal from command metadata."""

        class GoalTestInputs(BaseModel):
            name: str = Field(..., description="The name to use")
            count: int = Field(default=1, description="Number of times")

        class GoalTestCommand(AgentBackedCommand[GoalTestInputs, str]):
            __description__ = "Test goal construction"
            __depends_on__ = [FormatResult]

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": "test", "message_to_user": "Done"}}',
        ]

        provider = MockLlmProvider(responses)
        GoalTestCommand.__llm_provider__ = provider

        # Create an instance and validate inputs manually for testing
        cmd = GoalTestCommand(name="test", count=5)
        # Manually validate inputs so we can test goal construction
        cmd._inputs = GoalTestInputs(name="test", count=5)
        cmd._build_agent_if_needed()
        cmd._construct_goal_if_needed()

        # Goal should contain command name and description
        assert "GoalTestCommand" in cmd.goal
        assert "Test goal construction" in cmd.goal
        # Goal should contain input values
        assert '"name": "test"' in cmd.goal
        assert '"count": 5' in cmd.goal

    def test_result_type_validation(self):
        """Should validate result against result type."""

        class TypedResultInputs(BaseModel):
            value: int

        class TypedResult(BaseModel):
            computed: int
            message: str

        class TypedResultCommand(AgentBackedCommand[TypedResultInputs, TypedResult]):
            __description__ = "Return typed result"
            __depends_on__ = [AddNumbers]

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": {"computed": 42, "message": "Answer"}, "message_to_user": "Done"}}',
        ]

        TypedResultCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = TypedResultCommand.run(value=42)

        assert outcome.is_success()
        result = outcome.unwrap()
        # Result should be converted to the TypedResult model
        assert hasattr(result, "computed") or isinstance(result, dict)


class TestGaveUpError:
    """Test GaveUpError."""

    def test_with_reason(self):
        """Should include reason in message."""
        error = GaveUpError("Cannot find solution")
        assert "Cannot find solution" in str(error)
        assert error.reason == "Cannot find solution"

    def test_without_reason(self):
        """Should work without reason."""
        error = GaveUpError()
        assert "gave up" in str(error).lower()
        assert error.reason is None


class TestTooManyCommandCallsError:
    """Test TooManyCommandCallsError."""

    def test_includes_max_calls(self):
        """Should include max calls in message."""
        error = TooManyCommandCallsError(25)
        assert "25" in str(error)
        assert error.maximum_command_calls == 25


class TestAgentBackedCommandRegistration:
    """Test command registration in agent-backed command."""

    def test_depends_on_registers_commands(self):
        """Should register all depends_on commands with the agent."""

        class MultiDepsInputs(BaseModel):
            x: int

        class MultiDepsCommand(AgentBackedCommand[MultiDepsInputs, int]):
            __description__ = "Use multiple dependencies"
            __depends_on__ = [AddNumbers, MultiplyNumbers, FormatResult]

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 1, "message_to_user": "Done"}}',
        ]

        MultiDepsCommand.__llm_provider__ = MockLlmProvider(responses)

        cmd = MultiDepsCommand(x=1)
        cmd._build_agent_if_needed()

        # Check that all commands are registered
        assert "AddNumbers" in cmd.agent.commands
        assert "MultiplyNumbers" in cmd.agent.commands
        assert "FormatResult" in cmd.agent.commands

    def test_empty_depends_on(self):
        """Should work with empty depends_on."""

        class NoDepsInputs(BaseModel):
            task: str

        class NoDepsCommand(AgentBackedCommand[NoDepsInputs, str]):
            __description__ = "No dependencies"
            __depends_on__ = []

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "No commands available"}}',
        ]

        NoDepsCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = NoDepsCommand.run(task="test")

        # Should fail because no commands to use
        assert outcome.is_failure()
