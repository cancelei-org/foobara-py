"""
AccomplishGoal Command - Main agent execution loop.

This command runs the agent loop, repeatedly calling the LLM
to determine the next command until the goal is accomplished
or the agent gives up.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from foobara_py.ai.agent.determine_next_command import DetermineNextCommandNameAndInputs
from foobara_py.core.command import Command


class AccomplishGoalInputs(BaseModel):
    """Inputs for AccomplishGoal command."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any = Field(..., description="The agent instance")


class AccomplishGoalResult(BaseModel):
    """Result of AccomplishGoal command."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    accomplished: bool = Field(..., description="Whether the goal was accomplished")
    iterations: int = Field(..., description="Number of iterations run")
    final_result: Any = Field(None, description="Final result if accomplished")
    message: Optional[str] = Field(None, description="Final message from agent")


class AccomplishGoal(Command[AccomplishGoalInputs, AccomplishGoalResult]):
    """
    Main agent execution loop.

    This command repeatedly:
    1. Asks the LLM what command to run next
    2. Runs that command
    3. Logs the result
    4. Repeats until mission accomplished or agent gives up

    The loop also has a maximum iteration limit to prevent infinite loops.
    """

    def execute(self) -> AccomplishGoalResult:
        agent = self.inputs.agent
        iterations = 0

        while not agent.is_done and iterations < agent.max_iterations:
            iterations += 1

            if agent.verbose:
                print(f"\n[Agent] Iteration {iterations}")

            # Determine next command using LLM
            next_command_outcome = self._determine_next_command(agent)

            if next_command_outcome.is_failure():
                if agent.verbose:
                    print(
                        f"[Agent] Failed to determine next command: {next_command_outcome.errors}"
                    )

                # Try to recover by giving up
                agent.give_up(f"Failed to determine next command: {next_command_outcome.errors}")
                break

            next_command = next_command_outcome.unwrap()

            # Handle both dict and model responses from LLM
            if isinstance(next_command, dict):
                command_name = next_command.get("command", "")
                inputs = next_command.get("inputs", {}) or {}
            else:
                command_name = next_command.command
                inputs = next_command.inputs or {}

            if agent.verbose:
                print(f"[Agent] Running: {command_name}")
                print(f"[Agent] Inputs: {inputs}")

            # Run the command
            outcome = agent.run_command(command_name, inputs)

            # Log the command execution
            agent.log_command(command_name, inputs, outcome)

            if agent.verbose:
                if outcome.is_success():
                    print(f"[Agent] Result: {outcome.result}")
                else:
                    print(f"[Agent] Errors: {outcome.errors}")

        return AccomplishGoalResult(
            accomplished=agent.state.value == "mission_accomplished",
            iterations=iterations,
            final_result=agent.final_result,
            message=agent.final_message,
        )

    def _determine_next_command(self, agent: "Agent"):
        """Use LLM to determine the next command to run."""
        # Configure the determine command with agent's LLM settings
        DetermineNextCommandNameAndInputs.__llm_provider__ = agent.llm_provider
        DetermineNextCommandNameAndInputs.__llm_model__ = agent.llm_model

        return DetermineNextCommandNameAndInputs.run(agent=agent)
