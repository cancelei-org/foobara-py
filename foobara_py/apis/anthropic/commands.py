"""
Anthropic API Client Commands.

Provides commands for interacting with Anthropic's Claude API.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from foobara_py.apis import HTTPAPICommand, HTTPMethod


class MessageContent(BaseModel):
    """Message content block"""

    type: str
    text: Optional[str] = None
    # For image content
    source: Optional[Dict[str, Any]] = None


class Message(BaseModel):
    """Chat message"""

    role: Literal["user", "assistant"]
    content: str | List[MessageContent]


class Usage(BaseModel):
    """API usage statistics"""

    input_tokens: int
    output_tokens: int


class CreateMessageInputs(BaseModel):
    """Inputs for CreateMessage command"""

    model: str = Field(default="claude-3-5-sonnet-20241022", description="Model to use")
    messages: List[Message] = Field(..., description="List of messages")
    max_tokens: int = Field(default=1024, description="Maximum tokens to generate")
    system: Optional[str] = Field(None, description="System prompt")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="Temperature")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p sampling")
    top_k: Optional[int] = Field(None, ge=0, description="Top-k sampling")
    stop_sequences: Optional[List[str]] = Field(None, description="Stop sequences")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Available tools")
    tool_choice: Optional[Dict[str, Any]] = Field(None, description="Tool choice strategy")


class MessageResponse(BaseModel):
    """Response from Anthropic API"""

    id: str
    type: str
    role: str
    content: List[Dict[str, Any]]
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Usage


class CreateMessage(HTTPAPICommand[CreateMessageInputs, MessageResponse]):
    """
    Create a message using Anthropic's Claude API.

    Supports text generation, tool use, and vision capabilities.

    Usage:
        command = CreateMessage(api_key="your-api-key")
        outcome = await command.run(
            messages=[{"role": "user", "content": "Hello!"}],
            max_tokens=100
        )
        if outcome.is_success():
            response = outcome.unwrap()
            print(response.content[0]["text"])

    Configuration:
        Set api_key as instance attribute or override in subclass.
    """

    base_url = "https://api.anthropic.com"
    api_key: str = ""  # Set this or pass in __init__
    anthropic_version: str = "2023-06-01"

    def __init__(self, api_key: str = None, **inputs):
        """Initialize with optional API key"""
        super().__init__(**inputs)
        if api_key:
            self.api_key = api_key

    def endpoint(self) -> str:
        """API endpoint"""
        return "/v1/messages"

    def method(self) -> HTTPMethod:
        """HTTP method"""
        return HTTPMethod.POST

    def headers(self) -> Dict[str, str]:
        """Request headers"""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }
        return headers

    def request_body(self) -> Dict[str, Any]:
        """Request body"""
        # Convert messages to dict format
        messages = []
        for msg in self.inputs.messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            messages.append(msg_dict)

        body = {
            "model": self.inputs.model,
            "messages": messages,
            "max_tokens": self.inputs.max_tokens,
        }

        # Add optional fields
        if self.inputs.system:
            body["system"] = self.inputs.system
        if self.inputs.temperature is not None:
            body["temperature"] = self.inputs.temperature
        if self.inputs.top_p is not None:
            body["top_p"] = self.inputs.top_p
        if self.inputs.top_k is not None:
            body["top_k"] = self.inputs.top_k
        if self.inputs.stop_sequences:
            body["stop_sequences"] = self.inputs.stop_sequences
        if self.inputs.metadata:
            body["metadata"] = self.inputs.metadata
        if self.inputs.tools:
            body["tools"] = self.inputs.tools
        if self.inputs.tool_choice:
            body["tool_choice"] = self.inputs.tool_choice

        return body

    async def parse_response(self, response) -> MessageResponse:
        """Parse API response"""
        data = response.json()
        return MessageResponse(**data)


class CountTokensInputs(BaseModel):
    """Inputs for CountTokens command"""

    model: str = Field(
        default="claude-3-5-sonnet-20241022", description="Model to use for token counting"
    )
    messages: List[Message] = Field(..., description="Messages to count tokens for")
    system: Optional[str] = Field(None, description="System prompt")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Tools definition")


class CountTokensResponse(BaseModel):
    """Response from token counting"""

    input_tokens: int


class CountTokens(HTTPAPICommand[CountTokensInputs, CountTokensResponse]):
    """
    Count tokens in messages without making an API call.

    Useful for estimating costs and staying within limits.

    Usage:
        command = CountTokens(api_key="your-api-key")
        outcome = await command.run(
            messages=[{"role": "user", "content": "Hello!"}]
        )
        if outcome.is_success():
            count = outcome.unwrap()
            print(f"Token count: {count.input_tokens}")
    """

    base_url = "https://api.anthropic.com"
    api_key: str = ""
    anthropic_version: str = "2023-06-01"

    def __init__(self, api_key: str = None, **inputs):
        super().__init__(**inputs)
        if api_key:
            self.api_key = api_key

    def endpoint(self) -> str:
        return "/v1/messages/count_tokens"

    def method(self) -> HTTPMethod:
        return HTTPMethod.POST

    def headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }

    def request_body(self) -> Dict[str, Any]:
        messages = []
        for msg in self.inputs.messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            messages.append(msg_dict)

        body = {
            "model": self.inputs.model,
            "messages": messages,
        }

        if self.inputs.system:
            body["system"] = self.inputs.system
        if self.inputs.tools:
            body["tools"] = self.inputs.tools

        return body

    async def parse_response(self, response) -> CountTokensResponse:
        data = response.json()
        return CountTokensResponse(**data)


# Helper functions for common use cases


async def create_message_simple(
    api_key: str,
    prompt: str,
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 1024,
    system: Optional[str] = None,
):
    """
    Create and run a simple message with a single user prompt.

    Args:
        api_key: Anthropic API key
        prompt: User prompt text
        model: Model to use
        max_tokens: Maximum tokens to generate
        system: Optional system prompt

    Returns:
        CommandOutcome with MessageResponse

    Usage:
        outcome = await create_message_simple(
            api_key="your-key",
            prompt="What is the capital of France?",
            system="You are a helpful geography assistant."
        )
        if outcome.is_success():
            print(outcome.result.content[0]["text"])
    """
    command = CreateMessage(api_key=api_key)
    return await command.run(
        model=model,
        messages=[Message(role="user", content=prompt)],
        max_tokens=max_tokens,
        system=system,
    )


async def create_message_with_tools(
    api_key: str,
    prompt: str,
    tools: List[Dict[str, Any]],
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 1024,
):
    """
    Create and run a message with tool use enabled.

    Args:
        api_key: Anthropic API key
        prompt: User prompt text
        tools: List of tool definitions
        model: Model to use
        max_tokens: Maximum tokens to generate

    Returns:
        CommandOutcome with MessageResponse

    Example:
        tools = [{
            "name": "get_weather",
            "description": "Get weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }]
        outcome = await create_message_with_tools(
            api_key="your-key",
            prompt="What's the weather in Paris?",
            tools=tools
        )
    """
    command = CreateMessage(api_key=api_key)
    return await command.run(
        model=model,
        messages=[Message(role="user", content=prompt)],
        max_tokens=max_tokens,
        tools=tools,
    )
