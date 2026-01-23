"""
OpenAI API type definitions.

Defines Pydantic models for OpenAI API requests and responses.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# Message types
class ChatMessage(BaseModel):
    """A message in the chat conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List["ToolCall"]] = None
    tool_call_id: Optional[str] = None


class FunctionCall(BaseModel):
    """Function call information."""

    name: str
    arguments: str  # JSON string


class ToolCall(BaseModel):
    """Tool call from assistant."""

    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class ToolDefinition(BaseModel):
    """Tool definition for function calling."""

    type: Literal["function"] = "function"
    function: "FunctionDefinition"


class FunctionDefinition(BaseModel):
    """Function definition for tool use."""

    name: str = Field(description="Name of the function")
    description: str = Field(description="Description of what the function does")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema for function parameters"
    )
    strict: Optional[bool] = None


# Response types
class PromptTokensDetails(BaseModel):
    """Details about prompt tokens."""

    audio_tokens: Optional[int] = 0
    cached_tokens: Optional[int] = 0


class CompletionTokensDetails(BaseModel):
    """Details about completion tokens."""

    accepted_prediction_tokens: Optional[int] = 0
    audio_tokens: Optional[int] = 0
    reasoning_tokens: Optional[int] = 0
    rejected_prediction_tokens: Optional[int] = 0


class Usage(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: Optional[PromptTokensDetails] = None
    completion_tokens_details: Optional[CompletionTokensDetails] = None


class ResponseMessage(BaseModel):
    """Message in a chat completion response."""

    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    refusal: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class Choice(BaseModel):
    """A completion choice."""

    index: int
    message: ResponseMessage
    logprobs: Optional[Any] = None
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = None


class ChatCompletion(BaseModel):
    """Response from chat completion API."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    system_fingerprint: Optional[str] = None
    choices: List[Choice]
    usage: Usage
    service_tier: Optional[Literal["auto", "default"]] = None


# Streaming types
class DeltaContent(BaseModel):
    """Delta content in streaming response."""

    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class StreamChoice(BaseModel):
    """A streaming completion choice."""

    index: int
    delta: DeltaContent
    logprobs: Optional[Any] = None
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = None


class ChatCompletionChunk(BaseModel):
    """Streaming chunk from chat completion API."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    system_fingerprint: Optional[str] = None
    choices: List[StreamChoice]
    usage: Optional[Usage] = None


# Model information
class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str
    name: str = ""
    description: str = ""
    context_window: int = 128000
    max_output_tokens: int = 4096
    input_price_per_mtok: float = 0.0
    output_price_per_mtok: float = 0.0


# Model constants
GPT_4O = "gpt-4o"
GPT_4O_MINI = "gpt-4o-mini"
GPT_4_TURBO = "gpt-4-turbo"
GPT_4 = "gpt-4"
GPT_3_5_TURBO = "gpt-3.5-turbo"
O1 = "o1"
O1_MINI = "o1-mini"
O1_PREVIEW = "o1-preview"

DEFAULT_MODEL = GPT_4O_MINI

# Available models with metadata
AVAILABLE_MODELS = [
    ModelInfo(
        id=GPT_4O,
        name="GPT-4o",
        description="Most capable multimodal model",
        context_window=128000,
        max_output_tokens=16384,
    ),
    ModelInfo(
        id=GPT_4O_MINI,
        name="GPT-4o Mini",
        description="Fast and cost-effective multimodal model",
        context_window=128000,
        max_output_tokens=16384,
    ),
    ModelInfo(
        id=GPT_4_TURBO,
        name="GPT-4 Turbo",
        description="Previous generation powerful model",
        context_window=128000,
        max_output_tokens=4096,
    ),
    ModelInfo(
        id=GPT_4,
        name="GPT-4",
        description="Original GPT-4 model",
        context_window=8192,
        max_output_tokens=4096,
    ),
    ModelInfo(
        id=GPT_3_5_TURBO,
        name="GPT-3.5 Turbo",
        description="Fast and economical model",
        context_window=16385,
        max_output_tokens=4096,
    ),
    ModelInfo(
        id=O1,
        name="o1",
        description="Advanced reasoning model",
        context_window=200000,
        max_output_tokens=100000,
    ),
    ModelInfo(
        id=O1_MINI,
        name="o1-mini",
        description="Fast reasoning model",
        context_window=128000,
        max_output_tokens=65536,
    ),
    ModelInfo(
        id=O1_PREVIEW,
        name="o1-preview",
        description="Preview reasoning model",
        context_window=128000,
        max_output_tokens=32768,
    ),
]


# Update forward references
ChatMessage.model_rebuild()
ToolDefinition.model_rebuild()
