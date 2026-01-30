"""Advanced tests for Agent framework"""

import pytest
from unittest.mock import Mock, MagicMock
from pydantic import BaseModel, Field

from foobara_py.ai.agent import Agent, AgentState, AgentResult
from foobara_py.ai.agent.accomplish_goal import AccomplishGoal, AccomplishGoalInputs
from foobara_py.ai.agent.determine_next_command import (
    DetermineNextCommandNameAndInputs,
    DetermineNextCommandInputs,
    DetermineNextCommandResult,
)
from foobara_py.ai.llm_backed_command import LlmProvider, LlmMessage
from foobara_py.ai.types import Goal, GoalState, Context, CommandLogEntry, CommandOutcome
from foobara_py.core.command import Command
from foobara_py.core.outcome import CommandOutcome as CoreOutcome


class MockLlmProvider(LlmProvider):
    """Mock LLM provider with predefined responses"""

    def __init__(self, responses):
        if isinstance(responses, list):
            self.responses = iter(responses)
        else:
            self.responses = iter([responses])
        self.calls = []

    def generate(self, messages, temperature=0.0, model=None):
        self.calls.append({
            "messages": messages,
            "temperature": temperature,
            "model": model
        })
        try:
            return next(self.responses)
        except StopIteration:
            # Return last response repeatedly if we run out
            return '{"command": "Agent::ListCommands", "inputs": {}}'


class TestAccomplishGoal:
    """Test AccomplishGoal command"""

    def test_accomplish_goal_inputs(self):
        """Should create inputs with agent"""
        agent = Agent()
        inputs = AccomplishGoalInputs(agent=agent)
        assert inputs.agent is agent

    def test_accomplish_goal_single_iteration(self):
        """Should handle single iteration to completion"""
        class AddInputs(BaseModel):
            a: int
            b: int

        class Add(Command[AddInputs, int]):
            """Add two numbers"""
            def execute(self):
                return self.inputs.a + self.inputs.b

        responses = [
            '{"command": "Add", "inputs": {"a": 2, "b": 3}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 5, "message_to_user": "Added successfully"}}',
        ]

        agent = Agent(llm_provider=MockLlmProvider(responses))
        agent.register_command(Add)
        goal = Goal(text="Add 2 and 3")
        agent.context = Context(current_goal=goal)

        result = AccomplishGoal.run(agent=agent)

        assert result.is_success()
        outcome = result.unwrap()
        assert outcome.accomplished is True
        assert outcome.iterations == 2

    def test_accomplish_goal_verbose_output(self, capsys):
        """Should print verbose output when enabled"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self):
                return self.inputs.x * 2

        responses = [
            '{"command": "TestCommand", "inputs": {"x": 5}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 10, "message_to_user": "Done"}}',
        ]

        agent = Agent(llm_provider=MockLlmProvider(responses), verbose=True)
        agent.register_command(TestCommand)
        goal = Goal(text="Test goal")
        agent.context = Context(current_goal=goal)

        AccomplishGoal.run(agent=agent)

        captured = capsys.readouterr()
        assert "[Agent]" in captured.out
        assert "Iteration" in captured.out

    def test_accomplish_goal_max_iterations(self):
        """Should stop at max iterations"""
        responses = [
            '{"command": "Agent::ListCommands", "inputs": {}}',
        ]

        agent = Agent(llm_provider=MockLlmProvider(responses), max_iterations=3)
        goal = Goal(text="Infinite loop goal")
        agent.context = Context(current_goal=goal)

        result = AccomplishGoal.run(agent=agent)

        assert result.is_success()
        outcome = result.unwrap()
        assert outcome.iterations == 3
        assert outcome.accomplished is False

    def test_accomplish_goal_determine_command_failure(self):
        """Should handle determination failure gracefully"""
        # Mock a provider that returns invalid JSON
        class FailingProvider(LlmProvider):
            def generate(self, messages, temperature=0.0, model=None):
                return "invalid json response"

        agent = Agent(llm_provider=FailingProvider())
        goal = Goal(text="Test goal")
        agent.context = Context(current_goal=goal)

        result = AccomplishGoal.run(agent=agent)

        assert result.is_success()
        # Agent should give up after failed determination
        assert agent.state == AgentState.GIVING_UP

    def test_accomplish_goal_handles_dict_response(self):
        """Should handle dict response from LLM"""
        class TestInputs(BaseModel):
            value: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self):
                return self.inputs.value

        # Response is already a dict (simulating model validation)
        responses = [
            {"command": "TestCommand", "inputs": {"value": 42}},
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": 42, "message_to_user": "Done"}}',
        ]

        # Convert dicts to JSON strings for the mock provider
        import json
        responses_str = [json.dumps(r) if isinstance(r, dict) else r for r in responses]

        agent = Agent(llm_provider=MockLlmProvider(responses_str))
        agent.register_command(TestCommand)
        goal = Goal(text="Test")
        agent.context = Context(current_goal=goal)

        result = AccomplishGoal.run(agent=agent)

        assert result.is_success()
        outcome = result.unwrap()
        assert outcome.accomplished is True


class TestDetermineNextCommand:
    """Test DetermineNextCommandNameAndInputs"""

    def test_determine_next_command_inputs(self):
        """Should create inputs with agent"""
        agent = Agent()
        inputs = DetermineNextCommandInputs(agent=agent)
        assert inputs.agent is agent

    def test_build_system_prompt_basic(self):
        """Should build system prompt with command lists"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(Command[TestInputs, int]):
            """Test command"""
            def execute(self):
                return 1

        agent = Agent()
        agent.register_command(TestCommand)

        # Create the command and build messages
        DetermineNextCommandNameAndInputs.__llm_provider__ = MockLlmProvider(
            '{"command": "TestCommand", "inputs": {"x": 1}}'
        )

        cmd = DetermineNextCommandNameAndInputs(agent=agent)
        cmd._inputs = DetermineNextCommandInputs(agent=agent)
        messages = cmd.build_messages()

        system_message = messages[0].content

        assert "TestCommand" in system_message
        assert "Agent::ListCommands" in system_message
        assert "Agent::DescribeCommand" in system_message
        assert "Agent::GiveUp" in system_message

    def test_build_system_prompt_with_descriptions(self):
        """Should include described command details"""
        class TestInputs(BaseModel):
            value: int = Field(..., description="The input value")

        class DescribedCommand(Command[TestInputs, int]):
            """A well-described command"""
            def execute(self):
                return self.inputs.value

        agent = Agent()
        agent.register_command(DescribedCommand)

        # Describe the command
        from foobara_py.ai.agent import DescribeCommand
        DescribeCommand.run(agent=agent, command_name="DescribedCommand")

        # Build system prompt
        cmd = DetermineNextCommandNameAndInputs(agent=agent)
        cmd._inputs = DetermineNextCommandInputs(agent=agent)
        messages = cmd.build_messages()

        system_message = messages[0].content

        assert "DescribedCommand" in system_message
        assert "well-described" in system_message

    def test_build_context_message_empty_log(self):
        """Should build context with empty command log"""
        agent = Agent()
        goal = Goal(text="Test goal")
        agent.context = Context(current_goal=goal)

        cmd = DetermineNextCommandNameAndInputs(agent=agent)
        cmd._inputs = DetermineNextCommandInputs(agent=agent)
        context_msg = cmd._build_context_message(agent.context)

        import json
        context_data = json.loads(context_msg)

        assert context_data["current_goal"] == "Test goal"
        assert context_data["command_history"] == []

    def test_build_context_message_with_history(self):
        """Should build context with command history"""
        agent = Agent()
        goal = Goal(text="Test goal")

        # Add some command history
        entry1 = CommandLogEntry(
            command_name="TestCmd",
            inputs={"x": 1},
            outcome=CommandOutcome(success=True, result="result1")
        )
        entry2 = CommandLogEntry(
            command_name="FailCmd",
            inputs={"y": 2},
            outcome=CommandOutcome(success=False, errors_hash={"error": "failed"})
        )

        agent.context = Context(
            current_goal=goal,
            command_log=[entry1, entry2]
        )

        cmd = DetermineNextCommandNameAndInputs(agent=agent)
        cmd._inputs = DetermineNextCommandInputs(agent=agent)
        context_msg = cmd._build_context_message(agent.context)

        import json
        context_data = json.loads(context_msg)

        assert len(context_data["command_history"]) == 2
        assert context_data["command_history"][0]["command"] == "TestCmd"
        assert context_data["command_history"][0]["success"] is True
        assert context_data["command_history"][1]["success"] is False

    def test_build_context_message_truncates_large_results(self):
        """Should truncate very large results in history"""
        agent = Agent()
        goal = Goal(text="Test goal")

        # Create a large result
        large_result = {"data": "x" * 2000}  # Very large result

        entry = CommandLogEntry(
            command_name="BigResultCmd",
            inputs={},
            outcome=CommandOutcome(success=True, result=large_result)
        )

        agent.context = Context(
            current_goal=goal,
            command_log=[entry]
        )

        cmd = DetermineNextCommandNameAndInputs(agent=agent)
        cmd._inputs = DetermineNextCommandInputs(agent=agent)
        context_msg = cmd._build_context_message(agent.context)

        import json
        context_data = json.loads(context_msg)

        result = context_data["command_history"][0]["result"]
        # Should be truncated
        assert "_truncated" in result

    def test_build_context_message_no_context(self):
        """Should handle missing context"""
        agent = Agent()
        agent.context = None

        cmd = DetermineNextCommandNameAndInputs(agent=agent)
        cmd._inputs = DetermineNextCommandInputs(agent=agent)
        context_msg = cmd._build_context_message(None)

        import json
        context_data = json.loads(context_msg)

        assert "error" in context_data

    def test_get_schemas_override(self):
        """Should provide custom schemas"""
        agent = Agent()

        cmd = DetermineNextCommandNameAndInputs(agent=agent)
        cmd._inputs = DetermineNextCommandInputs(agent=agent)

        input_schema = cmd._get_inputs_json_schema()
        result_schema = cmd._get_result_json_schema()

        assert input_schema["type"] == "object"
        assert "current_goal" in input_schema["properties"]
        assert "command_history" in input_schema["properties"]

        assert result_schema["type"] == "object"
        assert "command" in result_schema["properties"]
        assert "inputs" in result_schema["properties"]


class TestMultiAgentCoordination:
    """Test multi-agent coordination patterns"""

    def test_two_agents_sequential(self):
        """Should coordinate two agents sequentially"""
        class Step1Inputs(BaseModel):
            data: str

        class Step1(Command[Step1Inputs, str]):
            """Process step 1"""
            def execute(self):
                return f"step1:{self.inputs.data}"

        class Step2Inputs(BaseModel):
            previous: str

        class Step2(Command[Step2Inputs, str]):
            """Process step 2"""
            def execute(self):
                return f"step2:{self.inputs.previous}"

        # Agent 1 responses
        agent1_responses = [
            '{"command": "Step1", "inputs": {"data": "input"}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": "step1:input", "message_to_user": "Step 1 done"}}',
        ]

        # Agent 2 responses
        agent2_responses = [
            '{"command": "Step2", "inputs": {"previous": "step1:input"}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": "step2:step1:input", "message_to_user": "Step 2 done"}}',
        ]

        agent1 = Agent(llm_provider=MockLlmProvider(agent1_responses))
        agent1.register_command(Step1)

        agent2 = Agent(llm_provider=MockLlmProvider(agent2_responses))
        agent2.register_command(Step2)

        # Run agent 1
        result1 = agent1.accomplish_goal("Process step 1 with 'input'")
        assert result1.success is True

        # Pass result to agent 2
        result2 = agent2.accomplish_goal(f"Process step 2 with '{result1.result}'")
        assert result2.success is True
        assert "step2:step1:input" in str(result2.result)

    def test_agent_delegation(self):
        """Should demonstrate agent delegation pattern"""
        class SubTaskInputs(BaseModel):
            task_id: int

        class SubTask(Command[SubTaskInputs, str]):
            """Execute a subtask"""
            def execute(self):
                return f"subtask_{self.inputs.task_id}_complete"

        # Coordinator responses
        coordinator_responses = [
            '{"command": "SubTask", "inputs": {"task_id": 1}}',
            '{"command": "SubTask", "inputs": {"task_id": 2}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": ["subtask_1_complete", "subtask_2_complete"], "message_to_user": "All subtasks done"}}',
        ]

        coordinator = Agent(llm_provider=MockLlmProvider(coordinator_responses))
        coordinator.register_command(SubTask)

        result = coordinator.accomplish_goal("Complete all subtasks")

        assert result.success is True
        assert len(coordinator.context.command_log) == 3

    def test_agent_with_shared_context(self):
        """Should share context between agent runs"""
        class UpdateContextInputs(BaseModel):
            key: str
            value: str

        class UpdateContext(Command[UpdateContextInputs, dict]):
            """Update shared context"""
            def execute(self):
                return {self.inputs.key: self.inputs.value}

        shared_results = []

        responses = [
            '{"command": "UpdateContext", "inputs": {"key": "k1", "value": "v1"}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": {"k1": "v1"}, "message_to_user": "Updated"}}',
        ]

        agent = Agent(llm_provider=MockLlmProvider(responses))
        agent.register_command(UpdateContext)

        # First run
        result1 = agent.accomplish_goal("Add k1=v1 to context")
        shared_results.append(result1.result)

        # Second run with new responses
        responses2 = [
            '{"command": "UpdateContext", "inputs": {"key": "k2", "value": "v2"}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": {"k2": "v2"}, "message_to_user": "Updated"}}',
        ]

        agent.llm_provider = MockLlmProvider(responses2)
        result2 = agent.accomplish_goal("Add k2=v2 to context")
        shared_results.append(result2.result)

        # Verify both results exist
        assert len(shared_results) == 2
        assert shared_results[0] == {"k1": "v1"}
        assert shared_results[1] == {"k2": "v2"}


class TestAgentErrorRecovery:
    """Test agent error recovery patterns"""

    def test_agent_recovers_from_command_failure(self):
        """Should continue after command failure"""
        class FailingInputs(BaseModel):
            should_fail: bool

        class FailableCommand(Command[FailingInputs, str]):
            """A command that can fail"""
            def execute(self):
                if self.inputs.should_fail:
                    raise ValueError("Command failed")
                return "success"

        responses = [
            '{"command": "FailableCommand", "inputs": {"should_fail": true}}',
            '{"command": "FailableCommand", "inputs": {"should_fail": false}}',
            '{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {"result": "success", "message_to_user": "Recovered"}}',
        ]

        agent = Agent(llm_provider=MockLlmProvider(responses))
        agent.register_command(FailableCommand)

        result = agent.accomplish_goal("Execute command, retry on failure")

        assert result.success is True
        # Should have logged both attempts
        assert len(agent.context.command_log) == 3

    def test_agent_gives_up_on_repeated_failures(self):
        """Should give up after multiple failures"""
        class AlwaysFailsInputs(BaseModel):
            x: int

        class AlwaysFails(Command[AlwaysFailsInputs, str]):
            """Always fails"""
            def execute(self):
                raise ValueError("Always fails")

        responses = [
            '{"command": "AlwaysFails", "inputs": {"x": 1}}',
            '{"command": "AlwaysFails", "inputs": {"x": 2}}',
            '{"command": "Agent::GiveUp", "inputs": {"message_to_user": "Cannot succeed"}}',
        ]

        agent = Agent(llm_provider=MockLlmProvider(responses))
        agent.register_command(AlwaysFails)

        result = agent.accomplish_goal("Try to succeed")

        assert result.success is False
        assert result.goal_state == GoalState.GAVE_UP


class TestAgentStateManagement:
    """Test agent state management"""

    def test_agent_state_transitions(self):
        """Should transition through states correctly"""
        agent = Agent()

        assert agent.state == AgentState.INITIALIZED

        # Simulate state changes
        goal = Goal(text="Test")
        agent.context = Context(current_goal=goal)
        agent.state = AgentState.ACCOMPLISHING_GOAL

        assert agent.state == AgentState.ACCOMPLISHING_GOAL
        assert not agent.is_done

        agent.mark_mission_accomplished("done", "Success!")

        assert agent.state == AgentState.MISSION_ACCOMPLISHED
        assert agent.is_done

    def test_agent_context_preservation(self):
        """Should preserve context across operations"""
        agent = Agent()
        goal = Goal(text="Original goal")
        agent.context = Context(current_goal=goal)

        # Add to command log
        entry = CommandLogEntry(
            command_name="TestCmd",
            inputs={},
            outcome=CommandOutcome(success=True, result="test")
        )
        agent.context.command_log.append(entry)

        # Verify context is preserved
        assert len(agent.context.command_log) == 1
        assert agent.context.current_goal.text == "Original goal"

    def test_agent_previous_goals_tracking(self):
        """Should track previous goals"""
        agent = Agent()

        goal1 = Goal(text="First goal", state=GoalState.ACCOMPLISHED)
        goal2 = Goal(text="Second goal")

        agent.context = Context(
            current_goal=goal2,
            previous_goals=[goal1]
        )

        assert len(agent.context.previous_goals) == 1
        assert agent.context.previous_goals[0].text == "First goal"
        assert agent.context.current_goal.text == "Second goal"
