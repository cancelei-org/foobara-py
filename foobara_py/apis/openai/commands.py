"""
OpenAI API commands.

Commands for interacting with the OpenAI API.
"""

from typing import Any, AsyncIterator, Dict, List, Optional

from pydantic import BaseModel, Field

from foobara_py.apis.openai.types import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    ChatCompletion,
    ChatMessage,
    Choice,
    ModelInfo,
    ResponseMessage,
    ToolDefinition,
    Usage,
)
from foobara_py.core.command import AsyncCommand, Command


class OpenAIError(Exception):
    """Base error for OpenAI API operations."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(OpenAIError):
    """Invalid or missing API key."""

    pass


class RateLimitError(OpenAIError):
    """Rate limit exceeded."""

    pass


class InvalidRequestError(OpenAIError):
    """Invalid request parameters."""

    pass


# ==================== Create Chat Completion Command ====================


class CreateChatCompletionInputs(BaseModel):
    """Inputs for CreateChatCompletion command."""

    model: str = Field(default=DEFAULT_MODEL, description="Model to use for the completion")
    messages: List[ChatMessage] = Field(description="Conversation messages")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens in response")
    max_completion_tokens: Optional[int] = Field(
        default=None, description="Maximum completion tokens (for o1 models)"
    )
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature"
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling parameter"
    )
    n: int = Field(default=1, ge=1, description="Number of completions to generate")
    stop: Optional[List[str]] = Field(default=None, description="Sequences that stop generation")
    presence_penalty: Optional[float] = Field(
        default=None, ge=-2.0, le=2.0, description="Presence penalty"
    )
    frequency_penalty: Optional[float] = Field(
        default=None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    tools: Optional[List[ToolDefinition]] = Field(
        default=None, description="Available tools for function calling"
    )
    tool_choice: Optional[Any] = Field(default=None, description="Control tool usage behavior")
    response_format: Optional[Dict[str, Any]] = Field(
        default=None, description="Response format specification"
    )
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    user: Optional[str] = Field(default=None, description="User identifier")


class CreateChatCompletionResult(BaseModel):
    """Result of CreateChatCompletion command."""

    id: str
    choices: List[Choice]
    model: str
    created: int
    usage: Usage
    system_fingerprint: Optional[str] = None


class CreateChatCompletion(Command[CreateChatCompletionInputs, CreateChatCompletionResult]):
    """
    Send a chat completion request to OpenAI and get a response.

    Usage:
        outcome = CreateChatCompletion.run(
            messages=[
                ChatMessage(role="user", content="Hello!")
            ],
            model="gpt-4o-mini"
        )
        if outcome.is_success():
            response = outcome.unwrap()
            print(response.choices[0].message.content)
    """

    def execute(self) -> CreateChatCompletionResult:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required. Install it with: pip install foobara-py[agent]"
            )

        client = OpenAI()  # Uses OPENAI_API_KEY env var

        # Build request params
        params: Dict[str, Any] = {
            "model": self.inputs.model,
            "messages": [self._convert_message(m) for m in self.inputs.messages],
        }

        if self.inputs.max_tokens is not None:
            params["max_tokens"] = self.inputs.max_tokens
        if self.inputs.max_completion_tokens is not None:
            params["max_completion_tokens"] = self.inputs.max_completion_tokens
        if self.inputs.temperature is not None:
            params["temperature"] = self.inputs.temperature
        if self.inputs.top_p is not None:
            params["top_p"] = self.inputs.top_p
        if self.inputs.n != 1:
            params["n"] = self.inputs.n
        if self.inputs.stop:
            params["stop"] = self.inputs.stop
        if self.inputs.presence_penalty is not None:
            params["presence_penalty"] = self.inputs.presence_penalty
        if self.inputs.frequency_penalty is not None:
            params["frequency_penalty"] = self.inputs.frequency_penalty
        if self.inputs.tools:
            params["tools"] = [t.model_dump() for t in self.inputs.tools]
        if self.inputs.tool_choice is not None:
            params["tool_choice"] = self.inputs.tool_choice
        if self.inputs.response_format:
            params["response_format"] = self.inputs.response_format
        if self.inputs.seed is not None:
            params["seed"] = self.inputs.seed
        if self.inputs.user:
            params["user"] = self.inputs.user

        try:
            response = client.chat.completions.create(**params)
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise AuthenticationError(error_msg)
            elif "rate limit" in error_msg.lower():
                raise RateLimitError(error_msg)
            elif "invalid" in error_msg.lower():
                raise InvalidRequestError(error_msg)
            raise OpenAIError(error_msg)

        return CreateChatCompletionResult(
            id=response.id,
            choices=self._parse_choices(response.choices),
            model=response.model,
            created=response.created,
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            system_fingerprint=response.system_fingerprint,
        )

    def _convert_message(self, message: ChatMessage) -> Dict[str, Any]:
        """Convert ChatMessage to API format."""
        result: Dict[str, Any] = {"role": message.role}
        if message.content is not None:
            result["content"] = message.content
        if message.name:
            result["name"] = message.name
        if message.tool_calls:
            result["tool_calls"] = [tc.model_dump() for tc in message.tool_calls]
        if message.tool_call_id:
            result["tool_call_id"] = message.tool_call_id
        return result

    def _parse_choices(self, choices: List[Any]) -> List[Choice]:
        """Parse response choices."""
        result = []
        for choice in choices:
            tool_calls = None
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                from foobara_py.apis.openai.types import FunctionCall, ToolCall

                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type=tc.type,
                        function=FunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in choice.message.tool_calls
                ]

            result.append(
                Choice(
                    index=choice.index,
                    message=ResponseMessage(
                        role="assistant",
                        content=choice.message.content,
                        refusal=getattr(choice.message, "refusal", None),
                        tool_calls=tool_calls,
                    ),
                    logprobs=choice.logprobs,
                    finish_reason=choice.finish_reason,
                )
            )
        return result


# ==================== Async Create Chat Completion Command ====================


class CreateChatCompletionAsync(
    AsyncCommand[CreateChatCompletionInputs, CreateChatCompletionResult]
):
    """
    Async version of CreateChatCompletion command.

    Usage:
        outcome = await CreateChatCompletionAsync.run(
            messages=[ChatMessage(role="user", content="Hello!")],
            model="gpt-4o-mini"
        )
    """

    async def execute(self) -> CreateChatCompletionResult:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package is required. Install it with: pip install foobara-py[agent]"
            )

        client = AsyncOpenAI()

        params: Dict[str, Any] = {
            "model": self.inputs.model,
            "messages": [self._convert_message(m) for m in self.inputs.messages],
        }

        if self.inputs.max_tokens is not None:
            params["max_tokens"] = self.inputs.max_tokens
        if self.inputs.max_completion_tokens is not None:
            params["max_completion_tokens"] = self.inputs.max_completion_tokens
        if self.inputs.temperature is not None:
            params["temperature"] = self.inputs.temperature
        if self.inputs.top_p is not None:
            params["top_p"] = self.inputs.top_p
        if self.inputs.n != 1:
            params["n"] = self.inputs.n
        if self.inputs.stop:
            params["stop"] = self.inputs.stop
        if self.inputs.presence_penalty is not None:
            params["presence_penalty"] = self.inputs.presence_penalty
        if self.inputs.frequency_penalty is not None:
            params["frequency_penalty"] = self.inputs.frequency_penalty
        if self.inputs.tools:
            params["tools"] = [t.model_dump() for t in self.inputs.tools]
        if self.inputs.tool_choice is not None:
            params["tool_choice"] = self.inputs.tool_choice
        if self.inputs.response_format:
            params["response_format"] = self.inputs.response_format
        if self.inputs.seed is not None:
            params["seed"] = self.inputs.seed

        try:
            response = await client.chat.completions.create(**params)
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower():
                raise AuthenticationError(error_msg)
            elif "rate limit" in error_msg.lower():
                raise RateLimitError(error_msg)
            raise OpenAIError(error_msg)

        return CreateChatCompletionResult(
            id=response.id,
            choices=self._parse_choices(response.choices),
            model=response.model,
            created=response.created,
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            system_fingerprint=response.system_fingerprint,
        )

    def _convert_message(self, message: ChatMessage) -> Dict[str, Any]:
        result: Dict[str, Any] = {"role": message.role}
        if message.content is not None:
            result["content"] = message.content
        if message.name:
            result["name"] = message.name
        if message.tool_calls:
            result["tool_calls"] = [tc.model_dump() for tc in message.tool_calls]
        if message.tool_call_id:
            result["tool_call_id"] = message.tool_call_id
        return result

    def _parse_choices(self, choices: List[Any]) -> List[Choice]:
        result = []
        for choice in choices:
            tool_calls = None
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                from foobara_py.apis.openai.types import FunctionCall, ToolCall

                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type=tc.type,
                        function=FunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in choice.message.tool_calls
                ]

            result.append(
                Choice(
                    index=choice.index,
                    message=ResponseMessage(
                        role="assistant",
                        content=choice.message.content,
                        refusal=getattr(choice.message, "refusal", None),
                        tool_calls=tool_calls,
                    ),
                    logprobs=choice.logprobs,
                    finish_reason=choice.finish_reason,
                )
            )
        return result


# ==================== Streaming Support ====================


class StreamChatCompletionInputs(CreateChatCompletionInputs):
    """Inputs for streaming chat completion (same as CreateChatCompletion)."""

    pass


async def stream_chat_completion(
    messages: List[ChatMessage],
    model: str = DEFAULT_MODEL,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    tools: Optional[List[ToolDefinition]] = None,
) -> AsyncIterator[str]:
    """
    Stream a chat completion response from OpenAI.

    Yields text chunks as they are generated.

    Usage:
        async for chunk in stream_chat_completion(
            messages=[ChatMessage(role="user", content="Tell me a story")],
            max_tokens=2048
        ):
            print(chunk, end="", flush=True)
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ImportError(
            "openai package is required. Install it with: pip install foobara-py[agent]"
        )

    client = AsyncOpenAI()

    params: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": True,
    }

    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    if temperature is not None:
        params["temperature"] = temperature
    if tools:
        params["tools"] = [t.model_dump() for t in tools]

    async with await client.chat.completions.create(**params) as stream:
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ==================== List Models Command ====================


class ListModelsInputs(BaseModel):
    """Inputs for ListModels command."""

    pass


class ListModelsResult(BaseModel):
    """Result of ListModels command."""

    models: List[ModelInfo]


class ListModels(Command[ListModelsInputs, ListModelsResult]):
    """
    List available OpenAI models.

    Usage:
        outcome = ListModels.run()
        for model in outcome.unwrap().models:
            print(f"{model.id}: {model.description}")
    """

    def execute(self) -> ListModelsResult:
        # Return static list of known models
        return ListModelsResult(models=AVAILABLE_MODELS)


# ==================== Simple Chat Function ====================


def chat(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    Simple chat function for quick interactions.

    Args:
        prompt: User message
        model: OpenAI model to use
        system: Optional system prompt
        max_tokens: Maximum response length
        temperature: Sampling temperature

    Returns:
        Assistant's response text

    Usage:
        response = chat("What is the capital of France?")
        print(response)  # "The capital of France is Paris."
    """
    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    outcome = CreateChatCompletion.run(
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    if outcome.is_failure():
        raise OpenAIError(f"Chat failed: {outcome.errors}")

    result = outcome.unwrap()
    if result.choices and result.choices[0].message.content:
        return result.choices[0].message.content
    return ""


async def chat_async(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    Async version of chat function.

    Usage:
        response = await chat_async("What is 2+2?")
        print(response)
    """
    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    outcome = await CreateChatCompletionAsync.run(
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    if outcome.is_failure():
        raise OpenAIError(f"Chat failed: {outcome.errors}")

    result = outcome.unwrap()
    if result.choices and result.choices[0].message.content:
        return result.choices[0].message.content
    return ""
