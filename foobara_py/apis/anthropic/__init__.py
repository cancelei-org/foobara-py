"""
Anthropic API Client for foobara-py.

Provides commands to interact with Anthropic's Claude API.

Usage:
    from foobara_py.apis.anthropic import CreateMessage, Message

    # Simple message
    command = CreateMessage(api_key="your-key")
    outcome = await command.run(
        messages=[Message(role="user", content="Hello!")],
        max_tokens=100
    )

    # With system prompt
    outcome = await CreateMessage(api_key="your-key").run(
        messages=[Message(role="user", content="What is 2+2?")],
        system="You are a math tutor.",
        max_tokens=50
    )
"""

from foobara_py.apis.anthropic.commands import (
    CountTokens,
    CountTokensInputs,
    CountTokensResponse,
    CreateMessage,
    CreateMessageInputs,
    Message,
    MessageContent,
    MessageResponse,
    Usage,
    create_message_simple,
    create_message_with_tools,
)

__all__ = [
    "CreateMessage",
    "CreateMessageInputs",
    "MessageResponse",
    "CountTokens",
    "CountTokensInputs",
    "CountTokensResponse",
    "Message",
    "MessageContent",
    "Usage",
    "create_message_simple",
    "create_message_with_tools",
]
