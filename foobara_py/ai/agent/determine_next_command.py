"""
DetermineNextCommandNameAndInputs - LLM-backed command for agent decisions.

This command uses an LLM to determine which command the agent should
run next and with what inputs.
"""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from foobara_py.ai.llm_backed_command import (
    LlmBackedCommand,
    LlmMessage,
)


class DetermineNextCommandInputs(BaseModel):
    """Inputs for DetermineNextCommandNameAndInputs."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any = Field(..., description="The agent instance")


class DetermineNextCommandResult(BaseModel):
    """Result of DetermineNextCommandNameAndInputs."""

    command: str = Field(..., description="Name of the command to run")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Inputs for the command")


class DetermineNextCommandNameAndInputs(
    LlmBackedCommand[DetermineNextCommandInputs, DetermineNextCommandResult]
):
    """
    Determine the next command to run to accomplish the goal.

    This LLM-backed command analyzes the current context (goal, command log)
    and determines what command should be run next.
    """

    __description__ = "Determine the next command to run to accomplish the current goal"

    def build_messages(self) -> List[LlmMessage]:
        """Build messages for the LLM including full context."""
        agent = self.inputs.agent
        context = agent.context

        # Build system prompt with available commands
        system_prompt = self._build_system_prompt(agent)

        # Build user message with current context
        user_message = self._build_context_message(context)

        return [
            LlmMessage(role="system", content=system_prompt),
            LlmMessage(role="user", content=user_message),
        ]

    def _build_system_prompt(self, agent: "Agent") -> str:
        """Build the system prompt with instructions and available commands."""
        # Get list of commands
        user_commands = []
        agent_commands = []

        for name, info in agent.commands.items():
            if info["is_agent_command"]:
                agent_commands.append(name)
            else:
                user_commands.append(name)

        # Get described commands info
        command_descriptions = []
        for name in agent.described_commands:
            if name in agent.commands:
                info = agent.commands[name]
                cmd_class = info["command_class"]
                description = getattr(cmd_class, "__description__", None) or cmd_class.__doc__ or ""

                # Get input schema if available
                input_schema = None
                if hasattr(cmd_class, "__orig_bases__") and cmd_class.__orig_bases__:
                    try:
                        inputs_model = cmd_class.__orig_bases__[0].__args__[0]
                        if hasattr(inputs_model, "model_json_schema"):
                            input_schema = inputs_model.model_json_schema()
                    except (IndexError, AttributeError):
                        pass

                command_descriptions.append(
                    {
                        "name": name,
                        "description": description.strip() if description else None,
                        "inputs_schema": input_schema,
                    }
                )

        return f"""You are an AI agent tasked with accomplishing a goal by running commands.

Available Commands:
- User-provided commands: {json.dumps(user_commands)}
- Agent commands: {json.dumps(agent_commands)}

Agent Commands Explanation:
- Agent::ListCommands - Lists all available commands
- Agent::DescribeCommand - Gets detailed info about a command (inputs, outputs)
- Agent::GiveUp - Give up on the current goal if you cannot accomplish it
- Agent::NotifyUserThatCurrentGoalHasBeenAccomplished - Signal that the goal is complete

Previously Described Commands:
{json.dumps(command_descriptions, indent=2) if command_descriptions else "None yet - use Agent::DescribeCommand to learn about commands"}

Strategy:
1. First, use Agent::ListCommands to see available commands
2. Use Agent::DescribeCommand to understand how commands work
3. Run user-provided commands to accomplish the goal
4. When done, use Agent::NotifyUserThatCurrentGoalHasBeenAccomplished
5. If you cannot accomplish the goal, use Agent::GiveUp

You must respond with a JSON object containing:
- "command": The name of the command to run (string)
- "inputs": The inputs to pass to the command (object)

Example responses:
{{"command": "Agent::ListCommands", "inputs": {{}}}}
{{"command": "Agent::DescribeCommand", "inputs": {{"command_name": "SomeCommand"}}}}
{{"command": "SomeCommand", "inputs": {{"param1": "value1"}}}}
{{"command": "Agent::NotifyUserThatCurrentGoalHasBeenAccomplished", "inputs": {{"result": "...", "message_to_user": "..."}}}}

Respond with ONLY the JSON object, no additional text."""

    def _build_context_message(self, context) -> str:
        """Build the user message with current context."""
        if context is None:
            return json.dumps({"error": "No context available"})

        # Format command log
        log_entries = []
        for entry in context.command_log:
            log_entry = {
                "command": entry.command_name,
                "inputs": entry.inputs,
                "success": entry.outcome.success,
            }
            if entry.outcome.success:
                result = entry.outcome.result
                # Truncate large results
                if isinstance(result, (dict, list)):
                    result_str = json.dumps(result)
                    if len(result_str) > 1000:
                        result = {"_truncated": True, "_preview": result_str[:500] + "..."}
                log_entry["result"] = result
            else:
                log_entry["errors"] = entry.outcome.errors_hash

            log_entries.append(log_entry)

        context_data = {
            "current_goal": context.current_goal.text,
            "command_history": log_entries,
        }

        return json.dumps(context_data, indent=2)

    def _get_inputs_json_schema(self) -> Dict[str, Any]:
        """Override to provide context-based schema."""
        return {
            "type": "object",
            "properties": {
                "current_goal": {"type": "string", "description": "The goal to accomplish"},
                "command_history": {
                    "type": "array",
                    "description": "History of commands run so far",
                    "items": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "inputs": {"type": "object"},
                            "success": {"type": "boolean"},
                            "result": {},
                            "errors": {"type": "object"},
                        },
                    },
                },
            },
        }

    def _get_result_json_schema(self) -> Dict[str, Any]:
        """Override to provide explicit result schema."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Name of the command to run",
                },
                "inputs": {
                    "type": "object",
                    "description": "Inputs to pass to the command",
                },
            },
            "required": ["command"],
        }
