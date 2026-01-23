"""
Ollama API type definitions.

Defines Pydantic models for Ollama API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Message types
class ChatMessage(BaseModel):
    """A message in the chat conversation."""

    role: Literal["system", "user", "assistant"]
    content: str
    images: Optional[List[str]] = None  # Base64 encoded images for multimodal models


# Model information
class ModelDetails(BaseModel):
    """Details about a model."""

    parent_model: Optional[str] = None
    format: Optional[str] = None
    family: Optional[str] = None
    families: Optional[List[str]] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None


class LocalModel(BaseModel):
    """A locally available model."""

    name: str
    model: Optional[str] = None
    modified_at: Optional[datetime] = None
    size: Optional[int] = None
    digest: Optional[str] = None
    details: Optional[ModelDetails] = None


class RunningModel(BaseModel):
    """A currently running model."""

    name: str
    model: Optional[str] = None
    size: Optional[int] = None
    digest: Optional[str] = None
    details: Optional[ModelDetails] = None
    expires_at: Optional[datetime] = None
    size_vram: Optional[int] = None


# Chat completion response
class ChatCompletionMessage(BaseModel):
    """Message in chat completion response."""

    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletion(BaseModel):
    """Response from chat completion API."""

    model: str
    created_at: datetime
    message: ChatCompletionMessage
    done: bool
    total_duration: Optional[int] = None  # nanoseconds
    load_duration: Optional[int] = None  # nanoseconds
    prompt_eval_count: Optional[int] = None  # number of tokens in prompt
    prompt_eval_duration: Optional[int] = None  # nanoseconds
    eval_count: Optional[int] = None  # number of tokens generated
    eval_duration: Optional[int] = None  # nanoseconds
    done_reason: Optional[Literal["stop", "length", "load"]] = None


# Streaming response
class ChatCompletionChunk(BaseModel):
    """Streaming chunk from chat completion API."""

    model: str
    created_at: datetime
    message: ChatCompletionMessage
    done: bool
    # Final chunk includes these stats
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None
    done_reason: Optional[str] = None


# Generation options
class GenerateOptions(BaseModel):
    """Options for generation."""

    seed: Optional[int] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_k: Optional[int] = None
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    num_predict: Optional[int] = None  # max tokens to generate
    num_ctx: Optional[int] = None  # context window size
    repeat_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stop: Optional[List[str]] = None


# Model info for listing
class ModelInfo(BaseModel):
    """Information about a model for listing purposes."""

    id: str
    name: str = ""
    description: str = ""
    parameter_size: str = ""
    quantization: str = ""


# Common models
LLAMA3_2 = "llama3.2"
LLAMA3_1 = "llama3.1"
LLAMA3 = "llama3"
LLAMA2 = "llama2"
MISTRAL = "mistral"
MIXTRAL = "mixtral"
CODELLAMA = "codellama"
DEEPSEEK_CODER = "deepseek-coder"
PHI3 = "phi3"
QWEN2 = "qwen2"
GEMMA2 = "gemma2"

DEFAULT_MODEL = LLAMA3_2

# Common model list (actual models depend on what's pulled locally)
COMMON_MODELS = [
    ModelInfo(
        id=LLAMA3_2,
        name="Llama 3.2",
        description="Meta's latest small language model",
        parameter_size="1B-3B",
    ),
    ModelInfo(
        id=LLAMA3_1,
        name="Llama 3.1",
        description="Meta's Llama 3.1 model",
        parameter_size="8B-405B",
    ),
    ModelInfo(
        id=LLAMA3,
        name="Llama 3",
        description="Meta's Llama 3 model",
        parameter_size="8B-70B",
    ),
    ModelInfo(
        id=MISTRAL,
        name="Mistral",
        description="Mistral AI's base model",
        parameter_size="7B",
    ),
    ModelInfo(
        id=MIXTRAL,
        name="Mixtral",
        description="Mistral AI's mixture of experts model",
        parameter_size="8x7B",
    ),
    ModelInfo(
        id=CODELLAMA,
        name="Code Llama",
        description="Meta's code-specialized model",
        parameter_size="7B-34B",
    ),
    ModelInfo(
        id=PHI3,
        name="Phi-3",
        description="Microsoft's small language model",
        parameter_size="3.8B-14B",
    ),
    ModelInfo(
        id=QWEN2,
        name="Qwen 2",
        description="Alibaba's Qwen 2 model",
        parameter_size="0.5B-72B",
    ),
    ModelInfo(
        id=GEMMA2,
        name="Gemma 2",
        description="Google's Gemma 2 model",
        parameter_size="2B-27B",
    ),
]
