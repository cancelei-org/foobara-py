"""
Anthropic API type definitions.

Defines Pydantic models for Anthropic Claude API requests and responses.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# Content types
class TextContent(BaseModel):
    """Text content block."""

    type: Literal["text"] = "text"
    text: str


class ImageSource(BaseModel):
    """Image source for image content."""

    type: Literal["base64", "url"] = "base64"
    media_type: str = "image/png"
    data: str


class ImageContent(BaseModel):
    """Image content block."""

    type: Literal["image"] = "image"
    source: ImageSource


class ToolUseContent(BaseModel):
    """Tool use content block (from assistant)."""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class ToolResultContent(BaseModel):
    """Tool result content block (from user)."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


# Union of all content types
ContentBlock = Union[TextContent, ImageContent, ToolUseContent, ToolResultContent]


class Message(BaseModel):
    """A message in the conversation."""

    role: Literal["user", "assistant"]
    content: Union[str, List[ContentBlock]]


class ToolDefinition(BaseModel):
    """Tool definition for function calling."""

    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    input_schema: Dict[str, Any] = Field(description="JSON Schema for tool inputs")


class Usage(BaseModel):
    """Token usage information."""

    input_tokens: int
    output_tokens: int


class MessageResponse(BaseModel):
    """Response from create message API."""

    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: List[ContentBlock]
    model: str
    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]] = None
    stop_sequence: Optional[str] = None
    usage: Usage


class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str
    name: str = ""
    description: str = ""
    context_window: int = 200000
    max_output_tokens: int = 4096
    input_price_per_mtok: float = 0.0
    output_price_per_mtok: float = 0.0


# Streaming types
class StreamStartEvent(BaseModel):
    """Stream start event."""

    type: Literal["message_start"] = "message_start"
    message: MessageResponse


class ContentBlockStartEvent(BaseModel):
    """Content block start event."""

    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: ContentBlock


class ContentBlockDeltaEvent(BaseModel):
    """Content block delta event."""

    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: Dict[str, Any]


class ContentBlockStopEvent(BaseModel):
    """Content block stop event."""

    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class MessageDeltaEvent(BaseModel):
    """Message delta event."""

    type: Literal["message_delta"] = "message_delta"
    delta: Dict[str, Any]
    usage: Optional[Usage] = None


class MessageStopEvent(BaseModel):
    """Message stop event."""

    type: Literal["message_stop"] = "message_stop"


StreamEvent = Union[
    StreamStartEvent,
    ContentBlockStartEvent,
    ContentBlockDeltaEvent,
    ContentBlockStopEvent,
    MessageDeltaEvent,
    MessageStopEvent,
]


# Default models
CLAUDE_OPUS_4 = "claude-opus-4-20250514"
CLAUDE_SONNET_4 = "claude-sonnet-4-20250514"
CLAUDE_HAIKU_3_5 = "claude-3-5-haiku-20241022"
CLAUDE_SONNET_3_5 = "claude-3-5-sonnet-20241022"
CLAUDE_OPUS_3 = "claude-3-opus-20240229"

DEFAULT_MODEL = CLAUDE_SONNET_4

# Available models with metadata
AVAILABLE_MODELS = [
    ModelInfo(
        id=CLAUDE_OPUS_4,
        name="Claude Opus 4",
        description="Most capable model for complex tasks",
        context_window=200000,
        max_output_tokens=32000,
    ),
    ModelInfo(
        id=CLAUDE_SONNET_4,
        name="Claude Sonnet 4",
        description="Balanced performance and speed",
        context_window=200000,
        max_output_tokens=16000,
    ),
    ModelInfo(
        id=CLAUDE_HAIKU_3_5,
        name="Claude 3.5 Haiku",
        description="Fastest model for simple tasks",
        context_window=200000,
        max_output_tokens=8192,
    ),
    ModelInfo(
        id=CLAUDE_SONNET_3_5,
        name="Claude 3.5 Sonnet",
        description="Previous generation balanced model",
        context_window=200000,
        max_output_tokens=8192,
    ),
    ModelInfo(
        id=CLAUDE_OPUS_3,
        name="Claude 3 Opus",
        description="Previous generation most capable model",
        context_window=200000,
        max_output_tokens=4096,
    ),
]
