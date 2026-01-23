"""
OpenAI API integration for Foobara Python.

Provides commands for interacting with the OpenAI API,
including chat completions, streaming, and tool use.

Usage:
    from foobara_py.apis.openai import (
        CreateChatCompletion,
        ChatMessage,
        chat,
        stream_chat_completion,
    )

    # Simple chat
    response = chat("Hello, GPT!")
    print(response)

    # Using command pattern
    outcome = CreateChatCompletion.run(
        messages=[ChatMessage(role="user", content="Hello!")],
        model="gpt-4o-mini"
    )
    if outcome.is_success():
        result = outcome.unwrap()
        print(result.choices[0].message.content)

    # Streaming
    async for chunk in stream_chat_completion(
        messages=[ChatMessage(role="user", content="Tell me a story")],
    ):
        print(chunk, end="")

    # With tools
    from foobara_py.apis.openai import ToolDefinition, FunctionDefinition

    calculator_tool = ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="calculator",
            description="Perform arithmetic",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            }
        )
    )

    outcome = CreateChatCompletion.run(
        messages=[ChatMessage(role="user", content="What is 15 * 23?")],
        tools=[calculator_tool],
    )
"""

from foobara_py.apis.openai.commands import (
    AuthenticationError,
    # Commands
    CreateChatCompletion,
    CreateChatCompletionAsync,
    CreateChatCompletionInputs,
    CreateChatCompletionResult,
    InvalidRequestError,
    ListModels,
    ListModelsInputs,
    ListModelsResult,
    # Errors
    OpenAIError,
    RateLimitError,
    StreamChatCompletionInputs,
    # Convenience functions
    chat,
    chat_async,
    # Streaming
    stream_chat_completion,
)
from foobara_py.apis.openai.types import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    GPT_3_5_TURBO,
    GPT_4,
    GPT_4_TURBO,
    # Model constants
    GPT_4O,
    GPT_4O_MINI,
    O1,
    O1_MINI,
    O1_PREVIEW,
    ChatCompletion,
    ChatCompletionChunk,
    # Message types
    ChatMessage,
    Choice,
    CompletionTokensDetails,
    # Streaming types
    DeltaContent,
    FunctionCall,
    FunctionDefinition,
    # Model info
    ModelInfo,
    PromptTokensDetails,
    # Response types
    ResponseMessage,
    StreamChoice,
    ToolCall,
    ToolDefinition,
    Usage,
)

__all__ = [
    # Message types
    "ChatMessage",
    "FunctionCall",
    "ToolCall",
    "ToolDefinition",
    "FunctionDefinition",
    # Response types
    "ResponseMessage",
    "Choice",
    "ChatCompletion",
    "Usage",
    "PromptTokensDetails",
    "CompletionTokensDetails",
    # Streaming types
    "DeltaContent",
    "StreamChoice",
    "ChatCompletionChunk",
    # Model info
    "ModelInfo",
    # Model constants
    "GPT_4O",
    "GPT_4O_MINI",
    "GPT_4_TURBO",
    "GPT_4",
    "GPT_3_5_TURBO",
    "O1",
    "O1_MINI",
    "O1_PREVIEW",
    "DEFAULT_MODEL",
    "AVAILABLE_MODELS",
    # Errors
    "OpenAIError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidRequestError",
    # Commands
    "CreateChatCompletion",
    "CreateChatCompletionAsync",
    "CreateChatCompletionInputs",
    "CreateChatCompletionResult",
    "ListModels",
    "ListModelsInputs",
    "ListModelsResult",
    # Streaming
    "stream_chat_completion",
    "StreamChatCompletionInputs",
    # Convenience functions
    "chat",
    "chat_async",
]
