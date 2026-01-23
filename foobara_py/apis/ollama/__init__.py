"""
Ollama API integration for Foobara Python.

Provides commands for interacting with local Ollama instances,
including chat completions, streaming, and model management.

Usage:
    from foobara_py.apis.ollama import (
        GenerateChatCompletion,
        ChatMessage,
        chat,
        stream_chat_completion,
    )

    # Simple chat
    response = chat("Hello, Llama!", model="llama3.2")
    print(response)

    # Using command pattern
    outcome = GenerateChatCompletion.run(
        model="llama3.2",
        messages=[ChatMessage(role="user", content="Hello!")]
    )
    if outcome.is_success():
        result = outcome.unwrap()
        print(result.message.content)

    # Streaming
    async for chunk in stream_chat_completion(
        messages=[ChatMessage(role="user", content="Tell me a story")],
        model="llama3.2"
    ):
        print(chunk, end="")

    # List local models
    from foobara_py.apis.ollama import ListLocalModels

    outcome = ListLocalModels.run()
    for model in outcome.unwrap().models:
        print(f"{model.name}: {model.size} bytes")

Configuration:
    Set OLLAMA_API_URL environment variable to change the Ollama server URL.
    Default: http://localhost:11434

    Set OLLAMA_API_KEY if authentication is required.
"""

from foobara_py.apis.ollama.commands import (
    ConnectionError,
    # Commands
    GenerateChatCompletion,
    GenerateChatCompletionAsync,
    GenerateChatCompletionInputs,
    GenerateChatCompletionResult,
    InvalidRequestError,
    ListLocalModels,
    ListLocalModelsInputs,
    ListLocalModelsResult,
    ListRunningModels,
    ListRunningModelsInputs,
    ListRunningModelsResult,
    ModelNotFoundError,
    # Errors
    OllamaError,
    # Convenience functions
    chat,
    chat_async,
    # Utilities
    get_base_url,
    # Streaming
    stream_chat_completion,
)
from foobara_py.apis.ollama.types import (
    CODELLAMA,
    COMMON_MODELS,
    DEEPSEEK_CODER,
    DEFAULT_MODEL,
    GEMMA2,
    LLAMA2,
    LLAMA3,
    LLAMA3_1,
    # Model constants
    LLAMA3_2,
    MISTRAL,
    MIXTRAL,
    PHI3,
    QWEN2,
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
    # Message types
    ChatMessage,
    # Options
    GenerateOptions,
    # Model types
    LocalModel,
    ModelDetails,
    ModelInfo,
    RunningModel,
)

__all__ = [
    # Message types
    "ChatMessage",
    "ChatCompletionMessage",
    "ChatCompletion",
    "ChatCompletionChunk",
    # Model types
    "LocalModel",
    "RunningModel",
    "ModelDetails",
    "ModelInfo",
    # Options
    "GenerateOptions",
    # Model constants
    "LLAMA3_2",
    "LLAMA3_1",
    "LLAMA3",
    "LLAMA2",
    "MISTRAL",
    "MIXTRAL",
    "CODELLAMA",
    "DEEPSEEK_CODER",
    "PHI3",
    "QWEN2",
    "GEMMA2",
    "DEFAULT_MODEL",
    "COMMON_MODELS",
    # Errors
    "OllamaError",
    "ConnectionError",
    "ModelNotFoundError",
    "InvalidRequestError",
    # Commands
    "GenerateChatCompletion",
    "GenerateChatCompletionAsync",
    "GenerateChatCompletionInputs",
    "GenerateChatCompletionResult",
    "ListLocalModels",
    "ListLocalModelsInputs",
    "ListLocalModelsResult",
    "ListRunningModels",
    "ListRunningModelsInputs",
    "ListRunningModelsResult",
    # Streaming
    "stream_chat_completion",
    # Convenience functions
    "chat",
    "chat_async",
    # Utilities
    "get_base_url",
]
