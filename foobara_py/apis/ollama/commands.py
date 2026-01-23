"""
Ollama API commands.

Commands for interacting with the Ollama API.
"""

import os
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from foobara_py.apis.ollama.types import (
    DEFAULT_MODEL,
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatMessage,
    GenerateOptions,
    LocalModel,
    RunningModel,
)
from foobara_py.core.command import AsyncCommand, Command


def get_base_url() -> str:
    """Get Ollama API base URL from environment or default."""
    return os.environ.get("OLLAMA_API_URL", "http://localhost:11434")


class OllamaError(Exception):
    """Base error for Ollama API operations."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ConnectionError(OllamaError):
    """Cannot connect to Ollama server."""

    pass


class ModelNotFoundError(OllamaError):
    """Model not found locally."""

    pass


class InvalidRequestError(OllamaError):
    """Invalid request parameters."""

    pass


# ==================== Generate Chat Completion Command ====================


class GenerateChatCompletionInputs(BaseModel):
    """Inputs for GenerateChatCompletion command."""

    model: str = Field(default=DEFAULT_MODEL, description="Model to use for the completion")
    messages: List[ChatMessage] = Field(description="Conversation messages")
    options: Optional[GenerateOptions] = Field(default=None, description="Generation options")
    format: Optional[str] = Field(default=None, description="Response format (e.g., 'json')")
    keep_alive: Optional[str] = Field(
        default=None, description="How long to keep model loaded (e.g., '5m')"
    )


class GenerateChatCompletionResult(BaseModel):
    """Result of GenerateChatCompletion command."""

    model: str
    message: ChatCompletionMessage
    done: bool
    total_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    done_reason: Optional[str] = None


class GenerateChatCompletion(Command[GenerateChatCompletionInputs, GenerateChatCompletionResult]):
    """
    Send a chat completion request to Ollama and get a response.

    Usage:
        outcome = GenerateChatCompletion.run(
            model="llama3.2",
            messages=[
                ChatMessage(role="user", content="Hello!")
            ]
        )
        if outcome.is_success():
            response = outcome.unwrap()
            print(response.message.content)
    """

    def execute(self) -> GenerateChatCompletionResult:
        base_url = get_base_url()
        url = f"{base_url}/api/chat"

        # Build request body
        body: Dict[str, Any] = {
            "model": self.inputs.model,
            "messages": [m.model_dump(exclude_none=True) for m in self.inputs.messages],
            "stream": False,
        }

        if self.inputs.options:
            body["options"] = self.inputs.options.model_dump(exclude_none=True)
        if self.inputs.format:
            body["format"] = self.inputs.format
        if self.inputs.keep_alive:
            body["keep_alive"] = self.inputs.keep_alive

        # Build headers
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("OLLAMA_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key

        try:
            with httpx.Client(timeout=600.0) as client:
                response = client.post(url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as e:
            raise ConnectionError(f"Cannot connect to Ollama server at {base_url}: {e}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFoundError(
                    f"Model '{self.inputs.model}' not found. Pull it with: ollama pull {self.inputs.model}"
                )
            raise OllamaError(f"HTTP error: {e}", status_code=e.response.status_code)
        except Exception as e:
            raise OllamaError(str(e))

        return GenerateChatCompletionResult(
            model=data["model"],
            message=ChatCompletionMessage(
                role="assistant",
                content=data["message"]["content"],
            ),
            done=data.get("done", True),
            total_duration=data.get("total_duration"),
            prompt_eval_count=data.get("prompt_eval_count"),
            eval_count=data.get("eval_count"),
            done_reason=data.get("done_reason"),
        )


# ==================== Async Generate Chat Completion Command ====================


class GenerateChatCompletionAsync(
    AsyncCommand[GenerateChatCompletionInputs, GenerateChatCompletionResult]
):
    """
    Async version of GenerateChatCompletion command.

    Usage:
        outcome = await GenerateChatCompletionAsync.run(
            model="llama3.2",
            messages=[ChatMessage(role="user", content="Hello!")]
        )
    """

    async def execute(self) -> GenerateChatCompletionResult:
        base_url = get_base_url()
        url = f"{base_url}/api/chat"

        body: Dict[str, Any] = {
            "model": self.inputs.model,
            "messages": [m.model_dump(exclude_none=True) for m in self.inputs.messages],
            "stream": False,
        }

        if self.inputs.options:
            body["options"] = self.inputs.options.model_dump(exclude_none=True)
        if self.inputs.format:
            body["format"] = self.inputs.format
        if self.inputs.keep_alive:
            body["keep_alive"] = self.inputs.keep_alive

        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("OLLAMA_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as e:
            raise ConnectionError(f"Cannot connect to Ollama server: {e}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFoundError(f"Model '{self.inputs.model}' not found")
            raise OllamaError(f"HTTP error: {e}", status_code=e.response.status_code)
        except Exception as e:
            raise OllamaError(str(e))

        return GenerateChatCompletionResult(
            model=data["model"],
            message=ChatCompletionMessage(
                role="assistant",
                content=data["message"]["content"],
            ),
            done=data.get("done", True),
            total_duration=data.get("total_duration"),
            prompt_eval_count=data.get("prompt_eval_count"),
            eval_count=data.get("eval_count"),
            done_reason=data.get("done_reason"),
        )


# ==================== Streaming Support ====================


async def stream_chat_completion(
    messages: List[ChatMessage],
    model: str = DEFAULT_MODEL,
    options: Optional[GenerateOptions] = None,
) -> AsyncIterator[str]:
    """
    Stream a chat completion response from Ollama.

    Yields text chunks as they are generated.

    Usage:
        async for chunk in stream_chat_completion(
            messages=[ChatMessage(role="user", content="Tell me a story")],
            model="llama3.2"
        ):
            print(chunk, end="", flush=True)
    """
    base_url = get_base_url()
    url = f"{base_url}/api/chat"

    body: Dict[str, Any] = {
        "model": model,
        "messages": [m.model_dump(exclude_none=True) for m in messages],
        "stream": True,
    }

    if options:
        body["options"] = options.model_dump(exclude_none=True)

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("OLLAMA_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    async with httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream("POST", url, json=body, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    import json

                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]


# ==================== List Local Models Command ====================


class ListLocalModelsInputs(BaseModel):
    """Inputs for ListLocalModels command."""

    pass


class ListLocalModelsResult(BaseModel):
    """Result of ListLocalModels command."""

    models: List[LocalModel]


class ListLocalModels(Command[ListLocalModelsInputs, ListLocalModelsResult]):
    """
    List locally available models.

    Usage:
        outcome = ListLocalModels.run()
        for model in outcome.unwrap().models:
            print(f"{model.name}: {model.size} bytes")
    """

    def execute(self) -> ListLocalModelsResult:
        base_url = get_base_url()
        url = f"{base_url}/api/tags"

        headers = {}
        api_key = os.environ.get("OLLAMA_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as e:
            raise ConnectionError(f"Cannot connect to Ollama server: {e}")
        except Exception as e:
            raise OllamaError(str(e))

        models = []
        for m in data.get("models", []):
            models.append(
                LocalModel(
                    name=m.get("name", ""),
                    model=m.get("model"),
                    modified_at=m.get("modified_at"),
                    size=m.get("size"),
                    digest=m.get("digest"),
                )
            )

        return ListLocalModelsResult(models=models)


# ==================== List Running Models Command ====================


class ListRunningModelsInputs(BaseModel):
    """Inputs for ListRunningModels command."""

    pass


class ListRunningModelsResult(BaseModel):
    """Result of ListRunningModels command."""

    models: List[RunningModel]


class ListRunningModels(Command[ListRunningModelsInputs, ListRunningModelsResult]):
    """
    List currently running models.

    Usage:
        outcome = ListRunningModels.run()
        for model in outcome.unwrap().models:
            print(f"{model.name}: expires at {model.expires_at}")
    """

    def execute(self) -> ListRunningModelsResult:
        base_url = get_base_url()
        url = f"{base_url}/api/ps"

        headers = {}
        api_key = os.environ.get("OLLAMA_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as e:
            raise ConnectionError(f"Cannot connect to Ollama server: {e}")
        except Exception as e:
            raise OllamaError(str(e))

        models = []
        for m in data.get("models", []):
            models.append(
                RunningModel(
                    name=m.get("name", ""),
                    model=m.get("model"),
                    size=m.get("size"),
                    digest=m.get("digest"),
                    expires_at=m.get("expires_at"),
                    size_vram=m.get("size_vram"),
                )
            )

        return ListRunningModelsResult(models=models)


# ==================== Simple Chat Function ====================


def chat(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    Simple chat function for quick interactions.

    Args:
        prompt: User message
        model: Ollama model to use
        system: Optional system prompt
        temperature: Sampling temperature

    Returns:
        Assistant's response text

    Usage:
        response = chat("What is the capital of France?", model="llama3.2")
        print(response)
    """
    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    options = None
    if temperature is not None:
        options = GenerateOptions(temperature=temperature)

    outcome = GenerateChatCompletion.run(
        model=model,
        messages=messages,
        options=options,
    )

    if outcome.is_failure():
        raise OllamaError(f"Chat failed: {outcome.errors}")

    result = outcome.unwrap()
    return result.message.content


async def chat_async(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    Async version of chat function.

    Usage:
        response = await chat_async("What is 2+2?", model="llama3.2")
        print(response)
    """
    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    options = None
    if temperature is not None:
        options = GenerateOptions(temperature=temperature)

    outcome = await GenerateChatCompletionAsync.run(
        model=model,
        messages=messages,
        options=options,
    )

    if outcome.is_failure():
        raise OllamaError(f"Chat failed: {outcome.errors}")

    result = outcome.unwrap()
    return result.message.content
