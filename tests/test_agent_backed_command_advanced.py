"""Advanced tests for AgentBackedCommand"""

import pytest
from unittest.mock import Mock
from pydantic import BaseModel, Field
from typing import List

from foobara_py.ai.agent_backed_command import (
    AgentBackedCommand,
    AsyncAgentBackedCommand,
    AgentBackedCommandError,
    GaveUpError,
    TooManyCommandCallsError,
)
from foobara_py.ai.llm_backed_command import LlmProvider, LlmMessage
from foobara_py.ai.types import GoalState
from foobara_py.core.command import Command


class MockLlmProvider(LlmProvider):
    """Mock LLM provider"""

    def __init__(self, responses):
        if isinstance(responses, list):
            self.responses = iter(responses)
        else:
            self.responses = iter([responses])

    def generate(self, messages, temperature=0.0, model=None):
        try:
            return next(self.responses)
        except StopIteration:
            return '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "No more responses"}}'


class TestAgentBackedCommandErrorHandling:
    """Test error handling in AgentBackedCommand"""

    def test_agent_backed_command_error(self):
        """Should raise base error"""
        error = AgentBackedCommandError("Test error")
        assert "Test error" in str(error)

    def test_gave_up_error_with_reason(self):
        """Should include reason in gave up error"""
        error = GaveUpError("Cannot proceed")
        assert "Cannot proceed" in str(error)
        assert error.reason == "Cannot proceed"

    def test_gave_up_error_without_reason(self):
        """Should work without reason"""
        error = GaveUpError()
        assert "gave up" in str(error).lower()
        assert error.reason is None

    def test_too_many_command_calls_error(self):
        """Should include max calls in error"""
        error = TooManyCommandCallsError(50)
        assert "50" in str(error)
        assert error.maximum_command_calls == 50


class TestAgentBackedCommandExecution:
    """Test AgentBackedCommand execution"""

    def test_simple_execution(self):
        """Should execute with dependencies"""
        class HelperInputs(BaseModel):
            value: int

        class HelperCommand(Command[HelperInputs, int]):
            """Helper command"""
            def execute(self):
                return self.inputs.value * 2

        class MainInputs(BaseModel):
            number: int

        class MainCommand(AgentBackedCommand[MainInputs, int]):
            __description__ = "Double a number"
            __depends_on__ = [HelperCommand]

        responses = [
            '{"command": "HelperCommand", "inputs": {"value": 5}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 10, "message_to_user": "Doubled"}}',
        ]

        MainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = MainCommand.run(number=5)

        assert outcome.is_success()
        assert outcome.unwrap() == 10

    def test_execution_with_pydantic_result(self):
        """Should validate Pydantic result models"""
        class SubInputs(BaseModel):
            x: int

        class SubCommand(Command[SubInputs, str]):
            def execute(self):
                return f"value:{self.inputs.x}"

        class MainInputs(BaseModel):
            value: int

        class ResultModel(BaseModel):
            output: str
            count: int

        class MainCommand(AgentBackedCommand[MainInputs, ResultModel]):
            __description__ = "Process value"
            __depends_on__ = [SubCommand]

        responses = [
            '{"command": "SubCommand", "inputs": {"x": 42}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": {"output": "value:42", "count": 1}, "message_to_user": "Done"}}',
        ]

        MainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = MainCommand.run(value=42)

        assert outcome.is_success()
        result = outcome.unwrap()
        # Result is properly converted to ResultModel by _agent_result()
        assert result.output == "value:42"
        assert result.count == 1

    def test_execution_without_dependencies(self):
        """Should work with no dependencies"""
        class MainInputs(BaseModel):
            text: str

        class MainCommand(AgentBackedCommand[MainInputs, str]):
            __description__ = "Process without dependencies"
            __depends_on__ = []

        responses = [
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "No commands to use"}}',
        ]

        MainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = MainCommand.run(text="test")

        assert outcome.is_failure()

    def test_execution_with_custom_max_iterations(self):
        """Should respect custom max iterations"""
        class MainInputs(BaseModel):
            x: int

        class MainCommand(AgentBackedCommand[MainInputs, int]):
            __description__ = "Test with custom max"
            __depends_on__ = []
            __maximum_command_calls__ = 5

        assert MainCommand.__maximum_command_calls__ == 5

    def test_execution_with_custom_agent_name(self):
        """Should support custom agent name"""
        class MainInputs(BaseModel):
            x: int

        class MainCommand(AgentBackedCommand[MainInputs, int]):
            __description__ = "Test"
            __agent_name__ = "CustomAgent"

        assert MainCommand.__agent_name__ == "CustomAgent"

    def test_execution_verbose_mode(self):
        """Should support verbose mode"""
        class SubInputs(BaseModel):
            x: int

        class SubCommand(Command[SubInputs, int]):
            def execute(self):
                return 42

        class MainInputs(BaseModel):
            value: int

        class MainCommand(AgentBackedCommand[MainInputs, int]):
            __description__ = "Verbose test"
            __depends_on__ = [SubCommand]
            __verbose__ = True

        responses = [
            '{"command": "SubCommand", "inputs": {"x": 1}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 42, "message_to_user": "Done"}}',
        ]

        MainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = MainCommand.run(value=1)

        assert outcome.is_success()

    def test_execution_with_custom_model(self):
        """Should use custom LLM model"""
        class MainInputs(BaseModel):
            x: int

        class MainCommand(AgentBackedCommand[MainInputs, int]):
            __description__ = "Test"
            __llm_model__ = "custom-model-v1"

        assert MainCommand.__llm_model__ == "custom-model-v1"


class TestAgentBackedCommandGoalConstruction:
    """Test goal construction in AgentBackedCommand"""

    def test_goal_includes_command_name(self):
        """Should include command name in goal"""
        class TestInputs(BaseModel):
            x: int

        class TestAgentCommand(AgentBackedCommand[TestInputs, int]):
            __description__ = "Test goal construction"
            __depends_on__ = []

        responses = [
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "Done"}}',
        ]

        TestAgentCommand.__llm_provider__ = MockLlmProvider(responses)

        cmd = TestAgentCommand(x=1)
        cmd._inputs = TestInputs(x=1)
        cmd._build_agent_if_needed()
        cmd._construct_goal_if_needed()

        assert "TestAgentCommand" in cmd.goal
        assert "Test goal construction" in cmd.goal

    def test_goal_includes_inputs(self):
        """Should include input values in goal"""
        class TestInputs(BaseModel):
            name: str = Field(..., description="The name")
            count: int = Field(default=1, description="The count")

        class TestAgentCommand(AgentBackedCommand[TestInputs, str]):
            __description__ = "Process inputs"
            __depends_on__ = []

        responses = [
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "Done"}}',
        ]

        TestAgentCommand.__llm_provider__ = MockLlmProvider(responses)

        cmd = TestAgentCommand(name="test", count=5)
        cmd._inputs = TestInputs(name="test", count=5)
        cmd._build_agent_if_needed()
        cmd._construct_goal_if_needed()

        assert '"name": "test"' in cmd.goal
        assert '"count": 5' in cmd.goal

    def test_goal_construction_caching(self):
        """Should not reconstruct goal if already built"""
        class TestInputs(BaseModel):
            x: int

        class TestAgentCommand(AgentBackedCommand[TestInputs, int]):
            __description__ = "Test"
            __depends_on__ = []

        cmd = TestAgentCommand(x=1)
        cmd._inputs = TestInputs(x=1)
        cmd._build_agent_if_needed()

        cmd.goal = "PresetGoal"
        cmd._construct_goal_if_needed()

        # Should not override preset goal
        assert cmd.goal == "PresetGoal"


class TestAgentBackedCommandAgentBuilding:
    """Test agent building in AgentBackedCommand"""

    def test_agent_building_caching(self):
        """Should not rebuild agent if already built"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(AgentBackedCommand[TestInputs, int]):
            __description__ = "Test"
            __depends_on__ = []

        cmd = TestCommand(x=1)
        cmd._inputs = TestInputs(x=1)

        # Build agent once
        cmd._build_agent_if_needed()
        first_agent = cmd.agent

        # Try to build again
        cmd._build_agent_if_needed()
        second_agent = cmd.agent

        # Should be same instance
        assert first_agent is second_agent

    def test_agent_registers_dependencies(self):
        """Should register all dependencies"""
        class Dep1Inputs(BaseModel):
            x: int

        class Dep1(Command[Dep1Inputs, int]):
            def execute(self):
                return 1

        class Dep2Inputs(BaseModel):
            y: int

        class Dep2(Command[Dep2Inputs, int]):
            def execute(self):
                return 2

        class TestInputs(BaseModel):
            value: int

        class TestCommand(AgentBackedCommand[TestInputs, int]):
            __description__ = "Test"
            __depends_on__ = [Dep1, Dep2]

        cmd = TestCommand(value=1)
        cmd._inputs = TestInputs(value=1)
        cmd._build_agent_if_needed()

        assert "Dep1" in cmd.agent.commands
        assert "Dep2" in cmd.agent.commands


class TestAsyncAgentBackedCommand:
    """Test AsyncAgentBackedCommand"""

    @pytest.mark.asyncio
    async def test_async_execution(self):
        """Should execute asynchronously"""
        class SubInputs(BaseModel):
            x: int

        class SubCommand(Command[SubInputs, int]):
            """Helper command"""
            def execute(self):
                return self.inputs.x * 3

        class MainInputs(BaseModel):
            number: int

        class AsyncMainCommand(AsyncAgentBackedCommand[MainInputs, int]):
            __description__ = "Triple a number"
            __depends_on__ = [SubCommand]

        responses = [
            '{"command": "SubCommand", "inputs": {"x": 7}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 21, "message_to_user": "Tripled"}}',
        ]

        AsyncMainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = await AsyncMainCommand.run(number=7)

        assert outcome.is_success()
        assert outcome.unwrap() == 21

    @pytest.mark.asyncio
    async def test_async_gave_up(self):
        """Should handle giving up in async"""
        class MainInputs(BaseModel):
            task: str

        class AsyncMainCommand(AsyncAgentBackedCommand[MainInputs, str]):
            __description__ = "Impossible task"
            __depends_on__ = []

        responses = [
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "Cannot do it"}}',
        ]

        AsyncMainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = await AsyncMainCommand.run(task="impossible")

        assert outcome.is_failure()

    @pytest.mark.asyncio
    async def test_async_max_iterations(self):
        """Should respect max iterations in async"""
        class MainInputs(BaseModel):
            x: int

        class AsyncMainCommand(AsyncAgentBackedCommand[MainInputs, int]):
            __description__ = "Loop forever"
            __depends_on__ = []
            __maximum_command_calls__ = 3

        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::ListCommands", "inputs": {}}',
        ]

        AsyncMainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = await AsyncMainCommand.run(x=1)

        assert outcome.is_failure()

    @pytest.mark.asyncio
    async def test_async_with_complex_result(self):
        """Should handle complex results in async"""
        class SubInputs(BaseModel):
            values: List[int]

        class SubCommand(Command[SubInputs, List[int]]):
            def execute(self):
                return [v * 2 for v in self.inputs.values]

        class MainInputs(BaseModel):
            numbers: List[int]

        class ResultModel(BaseModel):
            doubled: List[int]
            count: int

        class AsyncMainCommand(AsyncAgentBackedCommand[MainInputs, ResultModel]):
            __description__ = "Double all numbers"
            __depends_on__ = [SubCommand]

        import json
        responses = [
            '{"command": "SubCommand", "inputs": {"values": [1, 2, 3]}}',
            json.dumps({
                "command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished",
                "inputs": {
                    "result": {"doubled": [2, 4, 6], "count": 3},
                    "message_to_user": "Doubled all"
                }
            }),
        ]

        AsyncMainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = await AsyncMainCommand.run(numbers=[1, 2, 3])

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.doubled == [2, 4, 6]
        assert result.count == 3

    @pytest.mark.asyncio
    async def test_async_uses_executor(self):
        """Should run in executor"""
        class MainInputs(BaseModel):
            x: int

        class SubInputs(BaseModel):
            value: int

        class SubCommand(Command[SubInputs, int]):
            def execute(self):
                return 100

        class AsyncMainCommand(AsyncAgentBackedCommand[MainInputs, int]):
            __description__ = "Test executor"
            __depends_on__ = [SubCommand]

        responses = [
            '{"command": "SubCommand", "inputs": {"value": 1}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 100, "message_to_user": "Done"}}',
        ]

        AsyncMainCommand.__llm_provider__ = MockLlmProvider(responses)

        # This should use run_in_executor
        outcome = await AsyncMainCommand.run(x=1)

        assert outcome.is_success()
        assert outcome.unwrap() == 100


class TestAgentBackedCommandResultExtraction:
    """Test result extraction and formatting"""

    def test_result_extraction_simple_type(self):
        """Should extract simple type results"""
        class SubInputs(BaseModel):
            x: int

        class SubCommand(Command[SubInputs, str]):
            def execute(self):
                return "simple"

        class MainInputs(BaseModel):
            value: int

        class MainCommand(AgentBackedCommand[MainInputs, str]):
            __description__ = "Get simple result"
            __depends_on__ = [SubCommand]

        responses = [
            '{"command": "SubCommand", "inputs": {"x": 1}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": "simple", "message_to_user": "Done"}}',
        ]

        MainCommand.__llm_provider__ = MockLlmProvider(responses)

        outcome = MainCommand.run(value=1)

        assert outcome.is_success()
        assert outcome.unwrap() == "simple"

    def test_result_extraction_with_none(self):
        """Should handle None agent outcome"""
        class MainInputs(BaseModel):
            x: int

        class MainCommand(AgentBackedCommand[MainInputs, int]):
            __description__ = "Test"
            __depends_on__ = []

        cmd = MainCommand(x=1)
        cmd._inputs = MainInputs(x=1)
        cmd.agent_outcome = None

        # Should return None when no outcome
        result = cmd._agent_result()
        assert result is None
