"""
Foobara AI Framework.

Provides AI-powered features including:
- LLM-backed commands that use AI to generate results
- AI agents that can accomplish goals using commands

Usage:
    # LLM-backed command
    from foobara_py.ai import LlmBackedCommand
    from pydantic import BaseModel

    class TranslateInputs(BaseModel):
        text: str
        language: str

    class Translate(LlmBackedCommand[TranslateInputs, str]):
        __description__ = "Translate text to target language"

    result = Translate.run(text="Hello", language="Spanish")

    # AI Agent
    from foobara_py.ai import Agent

    agent = Agent()
    agent.register_command(MyCommand)
    result = agent.accomplish_goal("Do something")
"""

from foobara_py.ai.agent import (
    Agent,
    AgentResult,
    AgentState,
)
from foobara_py.ai.agent_backed_command import (
    AgentBackedCommand,
    AgentBackedCommandError,
    AsyncAgentBackedCommand,
    GaveUpError,
    TooManyCommandCallsError,
)
from foobara_py.ai.llm_backed_command import (
    AnthropicProvider,
    AsyncLlmBackedCommand,
    LlmBackedCommand,
    LlmBackedCommandError,
    LlmMessage,
    LlmProvider,
    OllamaProvider,
    OpenAIProvider,
    get_default_llm_provider,
    set_default_llm_provider,
)
from foobara_py.ai.types import (
    AssociationDepth,
    CommandLogEntry,
    CommandOutcome,
    Context,
    Goal,
    GoalState,
)

__all__ = [
    # Types
    "Goal",
    "GoalState",
    "Context",
    "CommandLogEntry",
    "CommandOutcome",
    "AssociationDepth",
    # LLM-backed commands
    "LlmBackedCommand",
    "AsyncLlmBackedCommand",
    "LlmBackedCommandError",
    "LlmMessage",
    # Providers
    "LlmProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "set_default_llm_provider",
    "get_default_llm_provider",
    # Agent
    "Agent",
    "AgentState",
    "AgentResult",
    # Agent-Backed Command
    "AgentBackedCommand",
    "AsyncAgentBackedCommand",
    "AgentBackedCommandError",
    "GaveUpError",
    "TooManyCommandCallsError",
]
