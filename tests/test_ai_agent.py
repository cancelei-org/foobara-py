"""Tests for AI Agent Framework"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pydantic import BaseModel, Field

from foobara_py.ai.types import (
    Goal,
    GoalState,
    Context,
    CommandLogEntry,
    CommandOutcome,
    AssociationDepth,
)
from foobara_py.ai.llm_backed_command import (
    LlmBackedCommand,
    LlmBackedCommandError,
    LlmMessage,
    LlmProvider,
    AnthropicProvider,
    OpenAIProvider,
    OllamaProvider,
    set_default_llm_provider,
    get_default_llm_provider,
    _strip_think_tags,
    _strip_code_fences,
    _extract_last_json_block,
)
from foobara_py.ai.agent import (
    Agent,
    AgentState,
    AgentResult,
    ListCommands,
    DescribeCommand,
    GiveUp,
    NotifyUserThatCurrentGoalHasBeenAccomplished,
)
from foobara_py.core.command import Command


class TestTypes:
    """Test AI type definitions"""

    def test_goal_state_enum(self):
        """Should have correct goal states"""
        assert GoalState.ACCOMPLISHED == "accomplished"
        assert GoalState.KILLED == "killed"
        assert GoalState.FAILED == "failed"
        assert GoalState.ERROR == "error"
        assert GoalState.GAVE_UP == "gave_up"

    def test_goal_creation(self):
        """Should create goal with text"""
        goal = Goal(text="Test goal")
        assert goal.text == "Test goal"
        assert goal.state is None

    def test_goal_with_state(self):
        """Should create goal with state"""
        goal = Goal(text="Test goal", state=GoalState.ACCOMPLISHED)
        assert goal.state == GoalState.ACCOMPLISHED

    def test_command_outcome(self):
        """Should create command outcome"""
        outcome = CommandOutcome(success=True, result="test result")
        assert outcome.success is True
        assert outcome.result == "test result"
        assert outcome.errors_hash is None

    def test_command_outcome_failure(self):
        """Should create failed command outcome"""
        outcome = CommandOutcome(
            success=False,
            errors_hash={"error": "test error"}
        )
        assert outcome.success is False
        assert outcome.errors_hash == {"error": "test error"}

    def test_command_log_entry(self):
        """Should create command log entry"""
        entry = CommandLogEntry(
            command_name="TestCommand",
            inputs={"param": "value"},
            outcome=CommandOutcome(success=True, result="result"),
        )
        assert entry.command_name == "TestCommand"
        assert entry.inputs == {"param": "value"}
        assert entry.is_success() is True

    def test_context_creation(self):
        """Should create context with goal"""
        goal = Goal(text="Test goal")
        context = Context(current_goal=goal)
        assert context.current_goal.text == "Test goal"
        assert context.previous_goals == []
        assert context.command_log == []

    def test_context_with_history(self):
        """Should create context with command history"""
        goal = Goal(text="Test goal")
        entry = CommandLogEntry(
            command_name="TestCommand",
            inputs={},
            outcome=CommandOutcome(success=True),
        )
        context = Context(
            current_goal=goal,
            command_log=[entry],
        )
        assert len(context.command_log) == 1

    def test_association_depth_enum(self):
        """Should have correct association depths"""
        assert AssociationDepth.ATOM == "atom"
        assert AssociationDepth.AGGREGATE == "aggregate"
        assert AssociationDepth.PRIMARY_KEY_ONLY == "primary_key_only"


class TestLlmHelpers:
    """Test LLM helper functions"""

    def test_strip_think_tags(self):
        """Should remove THINK tags"""
        text = "<THINK>thinking...</THINK>actual content"
        result = _strip_think_tags(text)
        assert result == "actual content"

    def test_strip_think_tags_multiline(self):
        """Should remove multiline THINK tags"""
        text = "<THINK>\nthinking\nmultiline\n</THINK>\nactual content"
        result = _strip_think_tags(text)
        assert "actual content" in result
        assert "thinking" not in result

    def test_strip_think_tags_case_insensitive(self):
        """Should handle case variations"""
        text = "<think>thinking</think>content"
        result = _strip_think_tags(text)
        assert "content" in result

    def test_strip_code_fences(self):
        """Should remove code fences"""
        text = '```json\n{"key": "value"}\n```'
        result = _strip_code_fences(text)
        assert result == '{"key": "value"}'

    def test_strip_code_fences_no_language(self):
        """Should handle fences without language"""
        text = '```\n{"key": "value"}\n```'
        result = _strip_code_fences(text)
        assert result == '{"key": "value"}'

    def test_extract_last_json_block(self):
        """Should extract last JSON block from fenced code"""
        text = 'Some text\n```json\n{"first": 1}\n```\nMore text\n```json\n{"last": 2}\n```\nend'
        result = _extract_last_json_block(text)
        assert result == '{"last": 2}'


class TestLlmMessage:
    """Test LlmMessage model"""

    def test_message_creation(self):
        """Should create message"""
        msg = LlmMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_system_message(self):
        """Should create system message"""
        msg = LlmMessage(role="system", content="You are helpful")
        assert msg.role == "system"


class TestMockProvider(LlmProvider):
    """Mock LLM provider for testing"""

    def __init__(self, response: str = '{"result": "test"}'):
        self.response = response
        self.last_messages = None
        self.last_temperature = None
        self.last_model = None

    def generate(self, messages, temperature=0.0, model=None):
        self.last_messages = messages
        self.last_temperature = temperature
        self.last_model = model
        return self.response


class TestLlmBackedCommand:
    """Test LlmBackedCommand"""

    def test_simple_llm_command(self):
        """Should execute LLM-backed command"""
        class TestInputs(BaseModel):
            text: str

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test command"

        # Set up mock provider
        mock_provider = TestMockProvider(response='"translated text"')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(text="hello")

        assert outcome.is_success()
        assert outcome.unwrap() == "translated text"
        assert mock_provider.last_messages is not None

    def test_llm_command_with_dict_result(self):
        """Should handle dict result"""
        class TestInputs(BaseModel):
            query: str

        class ResultModel(BaseModel):
            answer: str
            confidence: float

        class TestCommand(LlmBackedCommand[TestInputs, ResultModel]):
            __description__ = "Test command"

        mock_provider = TestMockProvider(
            response='{"answer": "42", "confidence": 0.95}'
        )
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(query="meaning of life")

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["answer"] == "42"
        assert result["confidence"] == 0.95

    def test_llm_command_handles_code_fences(self):
        """Should handle response with code fences"""
        class TestInputs(BaseModel):
            text: str

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test command"

        mock_provider = TestMockProvider(
            response='```json\n"result value"\n```'
        )
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(text="test")

        assert outcome.is_success()
        assert outcome.unwrap() == "result value"

    def test_llm_command_handles_think_tags(self):
        """Should handle response with think tags"""
        class TestInputs(BaseModel):
            text: str

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test command"

        mock_provider = TestMockProvider(
            response='<THINK>let me think...</THINK>"final answer"'
        )
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(text="test")

        assert outcome.is_success()
        assert outcome.unwrap() == "final answer"

    def test_llm_command_recovers_from_result_wrapper(self):
        """Should recover when LLM wraps result in {result: ...}"""
        class TestInputs(BaseModel):
            text: str

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test command"

        mock_provider = TestMockProvider(
            response='{"result": "actual value"}'
        )
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(text="test")

        assert outcome.is_success()
        assert outcome.unwrap() == "actual value"


class TestAgent:
    """Test Agent class"""

    def test_agent_creation(self):
        """Should create agent with default settings"""
        agent = Agent()
        assert agent.state == AgentState.INITIALIZED
        assert agent.max_iterations == 100
        assert len(agent.commands) == 4  # Built-in commands

    def test_agent_with_custom_settings(self):
        """Should create agent with custom settings"""
        mock_provider = TestMockProvider()
        agent = Agent(
            llm_provider=mock_provider,
            max_iterations=50,
            verbose=True,
        )
        assert agent.llm_provider == mock_provider
        assert agent.max_iterations == 50
        assert agent.verbose is True

    def test_register_command(self):
        """Should register custom command"""
        class TestInputs(BaseModel):
            value: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self):
                return self.inputs.value * 2

        agent = Agent()
        agent.register_command(TestCommand)

        assert "TestCommand" in agent.commands
        assert agent.commands["TestCommand"]["is_agent_command"] is False

    def test_register_command_with_custom_name(self):
        """Should register command with custom name"""
        class TestInputs(BaseModel):
            value: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self):
                return self.inputs.value * 2

        agent = Agent()
        agent.register_command(TestCommand, name="CustomName")

        assert "CustomName" in agent.commands
        assert "TestCommand" not in agent.commands

    def test_register_multiple_commands(self):
        """Should register multiple commands"""
        class Inputs1(BaseModel):
            value: int

        class Command1(Command[Inputs1, int]):
            def execute(self):
                return 1

        class Inputs2(BaseModel):
            value: str

        class Command2(Command[Inputs2, str]):
            def execute(self):
                return "2"

        agent = Agent()
        agent.register_commands(Command1, Command2)

        assert "Command1" in agent.commands
        assert "Command2" in agent.commands

    def test_builtin_commands_registered(self):
        """Should have built-in commands registered"""
        agent = Agent()

        assert "Agent::ListCommands" in agent.commands
        assert "Agent::DescribeCommand" in agent.commands
        assert "Agent::GiveUp" in agent.commands
        assert "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished" in agent.commands

    def test_run_command(self):
        """Should run registered command"""
        class TestInputs(BaseModel):
            value: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self):
                return self.inputs.value * 2

        agent = Agent()
        agent.register_command(TestCommand)

        outcome = agent.run_command("TestCommand", {"value": 5})

        assert outcome.is_success()
        assert outcome.result == 10

    def test_run_unknown_command(self):
        """Should fail for unknown command"""
        agent = Agent()
        outcome = agent.run_command("UnknownCommand", {})

        assert outcome.is_failure()

    def test_give_up(self):
        """Should mark agent as giving up"""
        agent = Agent()
        agent.context = Context(current_goal=Goal(text="test"))

        agent.give_up("Cannot do it")

        assert agent.state == AgentState.GIVING_UP
        assert agent.final_message == "Cannot do it"
        assert agent.context.current_goal.state == GoalState.GAVE_UP

    def test_mark_mission_accomplished(self):
        """Should mark mission as accomplished"""
        agent = Agent()
        agent.context = Context(current_goal=Goal(text="test"))

        agent.mark_mission_accomplished(result="done", message="All done!")

        assert agent.state == AgentState.MISSION_ACCOMPLISHED
        assert agent.final_result == "done"
        assert agent.final_message == "All done!"
        assert agent.context.current_goal.state == GoalState.ACCOMPLISHED

    def test_is_done(self):
        """Should check if agent is done"""
        agent = Agent()
        assert agent.is_done is False

        agent.state = AgentState.MISSION_ACCOMPLISHED
        assert agent.is_done is True

        agent.state = AgentState.GIVING_UP
        assert agent.is_done is True

    def test_log_command(self):
        """Should log command execution"""
        from foobara_py.core.outcome import CommandOutcome as CmdOutcome

        agent = Agent()
        agent.context = Context(current_goal=Goal(text="test"))

        outcome = CmdOutcome.from_result("test result")
        agent.log_command("TestCommand", {"param": "value"}, outcome)

        assert len(agent.context.command_log) == 1
        entry = agent.context.command_log[0]
        assert entry.command_name == "TestCommand"
        assert entry.inputs == {"param": "value"}
        assert entry.is_success() is True


class TestListCommands:
    """Test ListCommands built-in command"""

    def test_list_commands(self):
        """Should list available commands"""
        class TestInputs(BaseModel):
            value: int

        class UserCommand(Command[TestInputs, int]):
            def execute(self):
                return 1

        agent = Agent()
        agent.register_command(UserCommand)

        outcome = ListCommands.run(agent=agent)

        assert outcome.is_success()
        result = outcome.unwrap()
        assert "UserCommand" in result.user_provided_commands
        assert "Agent::ListCommands" in result.agent_specific_commands


class TestDescribeCommand:
    """Test DescribeCommand built-in command"""

    def test_describe_command(self):
        """Should describe a command"""
        class TestInputs(BaseModel):
            value: int = Field(..., description="Input value")

        class TestCommand(Command[TestInputs, int]):
            """A test command that doubles the value."""
            def execute(self):
                return self.inputs.value * 2

        agent = Agent()
        agent.register_command(TestCommand)

        outcome = DescribeCommand.run(agent=agent, command_name="TestCommand")

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.full_command_name == "TestCommand"
        assert "TestCommand" in agent.described_commands

    def test_describe_unknown_command(self):
        """Should fail for unknown command"""
        agent = Agent()

        outcome = DescribeCommand.run(agent=agent, command_name="UnknownCommand")

        assert outcome.is_failure()


class TestGiveUp:
    """Test GiveUp built-in command"""

    def test_give_up(self):
        """Should make agent give up"""
        agent = Agent()
        agent.context = Context(current_goal=Goal(text="test"))

        outcome = GiveUp.run(agent=agent, message_to_user="Cannot proceed")

        assert outcome.is_success()
        assert agent.state == AgentState.GIVING_UP
        assert agent.final_message == "Cannot proceed"


class TestNotifyAccomplished:
    """Test NotifyUserThatCurrentGoalHasBeenAccomplished"""

    def test_notify_accomplished(self):
        """Should mark goal as accomplished"""
        agent = Agent()
        agent.context = Context(current_goal=Goal(text="test"))

        outcome = NotifyUserThatCurrentGoalHasBeenAccomplished.run(
            agent=agent,
            result="done",
            message_to_user="Successfully completed!"
        )

        assert outcome.is_success()
        assert agent.state == AgentState.MISSION_ACCOMPLISHED
        assert agent.final_result == "done"
        assert agent.final_message == "Successfully completed!"


class TestAgentIntegration:
    """Integration tests for Agent"""

    def test_accomplish_goal_simple(self):
        """Should accomplish a simple goal"""
        class AddInputs(BaseModel):
            a: int
            b: int

        class Add(Command[AddInputs, int]):
            """Add two numbers together."""
            def execute(self):
                return self.inputs.a + self.inputs.b

        # Create mock responses for the LLM
        responses = iter([
            # First call: List commands
            '{"command": "Agent::ListCommands", "inputs": {}}',
            # Second call: Describe Add command
            '{"command": "Agent::DescribeCommand", "inputs": {"command_name": "Add"}}',
            # Third call: Run Add
            '{"command": "Add", "inputs": {"a": 2, "b": 3}}',
            # Fourth call: Notify accomplished
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 5, "message_to_user": "Added 2 and 3 to get 5"}}',
        ])

        class SequentialMockProvider(LlmProvider):
            def generate(self, messages, temperature=0.0, model=None):
                return next(responses)

        agent = Agent(llm_provider=SequentialMockProvider())
        agent.register_command(Add)

        result = agent.accomplish_goal("Add 2 and 3")

        assert result.success is True
        assert result.goal_state == GoalState.ACCOMPLISHED
        assert result.result == 5
        assert "5" in result.message_to_user

    def test_accomplish_goal_gives_up(self):
        """Should handle agent giving up"""
        responses = iter([
            '{"command": "Agent::ListCommands", "inputs": {}}',
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "No suitable commands available"}}',
        ])

        class SequentialMockProvider(LlmProvider):
            def generate(self, messages, temperature=0.0, model=None):
                return next(responses)

        agent = Agent(llm_provider=SequentialMockProvider())

        result = agent.accomplish_goal("Do something impossible")

        assert result.success is False
        assert result.goal_state == GoalState.GAVE_UP
        assert "No suitable commands" in result.message_to_user

    def test_accomplish_goal_max_iterations(self):
        """Should stop at max iterations"""
        class MockProvider(LlmProvider):
            def generate(self, messages, temperature=0.0, model=None):
                return '{"command": "Agent::ListCommands", "inputs": {}}'

        agent = Agent(llm_provider=MockProvider(), max_iterations=3)

        result = agent.accomplish_goal("Infinite loop goal")

        assert result.success is False
        assert result.goal_state == GoalState.FAILED
        assert result.message_to_user == "Agent reached maximum iterations"


class TestAgentState:
    """Test AgentState enum"""

    def test_state_values(self):
        """Should have correct state values"""
        assert AgentState.INITIALIZED == "initialized"
        assert AgentState.IDLE == "idle"
        assert AgentState.ACCOMPLISHING_GOAL == "accomplishing_goal"
        assert AgentState.WAITING_FOR_NEXT_GOAL == "waiting_for_next_goal"
        assert AgentState.GIVING_UP == "giving_up"
        assert AgentState.MISSION_ACCOMPLISHED == "mission_accomplished"


class TestAgentResult:
    """Test AgentResult model"""

    def test_success_result(self):
        """Should create success result"""
        result = AgentResult(
            success=True,
            result="test result",
            message_to_user="Done!",
            goal_state=GoalState.ACCOMPLISHED,
        )
        assert result.success is True
        assert result.result == "test result"

    def test_failure_result(self):
        """Should create failure result"""
        result = AgentResult(
            success=False,
            message_to_user="Failed!",
            goal_state=GoalState.GAVE_UP,
        )
        assert result.success is False
        assert result.result is None
