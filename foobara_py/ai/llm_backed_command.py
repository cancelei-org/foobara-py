"""
LLM-Backed Command Implementation.

Provides a base class for commands whose execution is backed by an LLM.
The LLM generates the result based on the command's inputs and description.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field

from foobara_py.ai.types import AssociationDepth
from foobara_py.core.command import AsyncCommand, Command, CommandOutcome


class LlmMessage(BaseModel):
    """A message in the LLM conversation."""

    role: str = Field(..., description="Role of the message sender (system, user, assistant)")
    content: str = Field(..., description="Content of the message")


class LlmProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        messages: List[LlmMessage],
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            messages: List of messages in the conversation
            temperature: Sampling temperature (0.0 = deterministic)
            model: Optional model name to use

        Returns:
            The LLM's response text
        """
        pass


class AnthropicProvider(LlmProvider):
    """LLM provider using Anthropic's Claude API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.default_model = model

    def generate(
        self,
        messages: List[LlmMessage],
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        from foobara_py.apis.anthropic import CreateMessage, Message

        # Separate system message from other messages
        system_content = None
        chat_messages = []

        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                chat_messages.append(Message(role=msg.role, content=msg.content))

        outcome = CreateMessage.run(
            model=model or self.default_model,
            max_tokens=4096,
            system=system_content,
            messages=chat_messages,
            temperature=temperature,
        )

        if outcome.is_failure():
            raise RuntimeError(f"LLM request failed: {outcome.errors}")

        result = outcome.unwrap()
        return result.content[0].text


class OpenAIProvider(LlmProvider):
    """LLM provider using OpenAI's API."""

    def __init__(self, model: str = "gpt-4o"):
        self.default_model = model

    def generate(
        self,
        messages: List[LlmMessage],
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        from foobara_py.apis.openai import ChatMessage, CreateChatCompletion

        chat_messages = [ChatMessage(role=msg.role, content=msg.content) for msg in messages]

        outcome = CreateChatCompletion.run(
            model=model or self.default_model,
            messages=chat_messages,
            temperature=temperature,
        )

        if outcome.is_failure():
            raise RuntimeError(f"LLM request failed: {outcome.errors}")

        result = outcome.unwrap()
        return result.choices[0].message.content


class OllamaProvider(LlmProvider):
    """LLM provider using Ollama's local API."""

    def __init__(self, model: str = "llama3.2"):
        self.default_model = model

    def generate(
        self,
        messages: List[LlmMessage],
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        from foobara_py.apis.ollama import ChatMessage, GenerateChatCompletion, GenerateOptions

        chat_messages = [ChatMessage(role=msg.role, content=msg.content) for msg in messages]

        options = GenerateOptions(temperature=temperature) if temperature != 0.0 else None

        outcome = GenerateChatCompletion.run(
            model=model or self.default_model,
            messages=chat_messages,
            options=options,
        )

        if outcome.is_failure():
            raise RuntimeError(f"LLM request failed: {outcome.errors}")

        result = outcome.unwrap()
        return result.message.content


# Default provider - can be set globally
_default_provider: Optional[LlmProvider] = None


def set_default_llm_provider(provider: LlmProvider) -> None:
    """Set the default LLM provider."""
    global _default_provider
    _default_provider = provider


def get_default_llm_provider() -> LlmProvider:
    """Get the default LLM provider."""
    global _default_provider
    if _default_provider is None:
        # Default to Anthropic
        _default_provider = AnthropicProvider()
    return _default_provider


InputsT = TypeVar("InputsT", bound=BaseModel)
ResultT = TypeVar("ResultT")


class LlmBackedCommandError(Exception):
    """Error raised when LLM-backed command execution fails."""

    def __init__(
        self, message: str, raw_answer: Optional[str] = None, stripped_answer: Optional[str] = None
    ):
        super().__init__(message)
        self.raw_answer = raw_answer
        self.stripped_answer = stripped_answer


def _type_to_json_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """Convert a Pydantic model to JSON schema."""
    return model.model_json_schema()


def _strip_think_tags(text: str) -> str:
    """Remove <THINK>...</THINK> and similar tags from LLM output."""
    # Remove <THINK>...</THINK> tags (case insensitive)
    text = re.sub(r"<THINK>.*?</THINK>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # Remove standalone </think> or <think> at the start
    text = re.sub(r"^\s*</?think>\s*", "", text, flags=re.IGNORECASE)
    return text


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from text."""
    # Remove ```json or ``` fences
    text = re.sub(r"^\s*```\w*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def _extract_last_json_block(text: str) -> Optional[str]:
    """Try to extract the last JSON block from fenced code."""
    pattern = r"```\w*\s*\n((?:(?!```).)+)\n```(?:(?!```).)*$"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


class LlmBackedCommand(Command[InputsT, ResultT], Generic[InputsT, ResultT]):
    """
    A command whose execution is backed by an LLM.

    The LLM generates a response based on the command's description,
    input schema, and result schema.

    Usage:
        class TranslateTextInputs(BaseModel):
            text: str
            target_language: str

        class TranslateText(LlmBackedCommand[TranslateTextInputs, str]):
            __description__ = "Translate text to the target language"

            def build_messages(self) -> List[LlmMessage]:
                # Optionally override to customize messages
                return super().build_messages()

        outcome = TranslateText.run(text="Hello", target_language="Spanish")
        if outcome.is_success():
            print(outcome.unwrap())  # "Hola"
    """

    # Class-level configuration
    __description__: str = "An LLM-backed command"
    __llm_provider__: Optional[LlmProvider] = None
    __llm_model__: Optional[str] = None
    __temperature__: float = 0.0
    __association_depth__: AssociationDepth = AssociationDepth.ATOM

    # Instance state
    answer: Optional[str] = None
    parsed_answer: Any = None
    final_answer: Any = None
    messages: Optional[List[LlmMessage]] = None

    def execute(self) -> ResultT:
        """Execute the LLM-backed command."""
        self._construct_messages()
        self._generate_answer()
        self._parse_answer()
        self._attempt_to_recover_from_bad_format()
        return self.final_answer

    def _get_provider(self) -> LlmProvider:
        """Get the LLM provider to use."""
        if self.__llm_provider__ is not None:
            return self.__llm_provider__
        return get_default_llm_provider()

    def _construct_messages(self) -> None:
        """Construct the messages to send to the LLM."""
        self.messages = self.build_messages()

    def build_messages(self) -> List[LlmMessage]:
        """Build the messages for the LLM.

        Override this method to customize the messages sent to the LLM.
        """
        instructions = self._build_llm_instructions()

        # Serialize inputs to JSON
        inputs_json = json.dumps(self.inputs.model_dump(exclude_none=True))

        return [
            LlmMessage(role="system", content=instructions),
            LlmMessage(role="user", content=inputs_json),
        ]

    def _build_llm_instructions(self) -> str:
        """Build the system instructions for the LLM."""
        command_name = self.__class__.__name__
        description = self.__description__

        # Get JSON schemas
        inputs_schema = json.dumps(self._get_inputs_json_schema(), indent=2)
        result_schema = json.dumps(self._get_result_json_schema(), indent=2)

        return f"""You are implementing an API for a command named {command_name} which has the following description:

{description}

Here is the inputs JSON schema for the data you will receive:

{inputs_schema}

Here is the result JSON schema:

{result_schema}

You will receive 1 message containing only JSON data according to the inputs JSON schema above
and you will generate a JSON response that is a valid response according to the result JSON schema above.

You will reply with nothing more than the JSON you've generated so that the calling code
can successfully parse your answer."""

    def _get_inputs_json_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the inputs type."""
        inputs_type = self.__class__.__orig_bases__[0].__args__[0]
        return _type_to_json_schema(inputs_type)

    def _get_result_json_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the result type."""
        result_type = self.__class__.__orig_bases__[0].__args__[1]
        if hasattr(result_type, "model_json_schema"):
            return _type_to_json_schema(result_type)
        # For simple types like str, int, etc.
        return {"type": self._python_type_to_json_type(result_type)}

    def _python_type_to_json_type(self, python_type: type) -> str:
        """Convert Python type to JSON schema type."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return type_map.get(python_type, "string")

    def _generate_answer(self) -> None:
        """Generate the answer from the LLM."""
        provider = self._get_provider()
        self.answer = provider.generate(
            messages=self.messages,
            temperature=self.__temperature__,
            model=self.__llm_model__,
        )

    def _parse_answer(self) -> None:
        """Parse the JSON answer from the LLM."""
        # Strip thinking tags
        stripped = _strip_think_tags(self.answer)

        # Strip code fences
        stripped = _strip_code_fences(stripped)

        try:
            self.parsed_answer = json.loads(stripped)
        except json.JSONDecodeError:
            # Try to extract last JSON block
            extracted = _extract_last_json_block(stripped)
            if extracted:
                try:
                    self.parsed_answer = json.loads(extracted)
                    return
                except json.JSONDecodeError:
                    pass

            raise LlmBackedCommandError(
                f"Could not parse result JSON",
                raw_answer=self.answer,
                stripped_answer=stripped,
            )

    def _attempt_to_recover_from_bad_format(self) -> None:
        """Attempt to recover from badly formatted responses.

        Some models wrap the result in {"result": ...} even when not asked to.
        """
        if isinstance(self.parsed_answer, dict) and list(self.parsed_answer.keys()) == ["result"]:
            # Check if the result itself is what we want
            result_value = self.parsed_answer["result"]
            self.final_answer = result_value
        else:
            self.final_answer = self.parsed_answer


class AsyncLlmBackedCommand(AsyncCommand[InputsT, ResultT], Generic[InputsT, ResultT]):
    """
    Async version of LlmBackedCommand.

    Usage:
        class TranslateTextAsync(AsyncLlmBackedCommand[TranslateTextInputs, str]):
            __description__ = "Translate text to the target language"

        outcome = await TranslateTextAsync.run(text="Hello", target_language="Spanish")
    """

    __description__: str = "An LLM-backed command"
    __llm_provider__: Optional[LlmProvider] = None
    __llm_model__: Optional[str] = None
    __temperature__: float = 0.0
    __association_depth__: AssociationDepth = AssociationDepth.ATOM

    answer: Optional[str] = None
    parsed_answer: Any = None
    final_answer: Any = None
    messages: Optional[List[LlmMessage]] = None

    async def execute(self) -> ResultT:
        """Execute the LLM-backed command asynchronously."""
        self._construct_messages()
        await self._generate_answer()
        self._parse_answer()
        self._attempt_to_recover_from_bad_format()
        return self.final_answer

    def _get_provider(self) -> LlmProvider:
        """Get the LLM provider to use."""
        if self.__llm_provider__ is not None:
            return self.__llm_provider__
        return get_default_llm_provider()

    def _construct_messages(self) -> None:
        """Construct the messages to send to the LLM."""
        self.messages = self.build_messages()

    def build_messages(self) -> List[LlmMessage]:
        """Build the messages for the LLM."""
        instructions = self._build_llm_instructions()
        inputs_json = json.dumps(self.inputs.model_dump(exclude_none=True))

        return [
            LlmMessage(role="system", content=instructions),
            LlmMessage(role="user", content=inputs_json),
        ]

    def _build_llm_instructions(self) -> str:
        """Build the system instructions for the LLM."""
        command_name = self.__class__.__name__
        description = self.__description__

        inputs_schema = json.dumps(self._get_inputs_json_schema(), indent=2)
        result_schema = json.dumps(self._get_result_json_schema(), indent=2)

        return f"""You are implementing an API for a command named {command_name} which has the following description:

{description}

Here is the inputs JSON schema for the data you will receive:

{inputs_schema}

Here is the result JSON schema:

{result_schema}

You will receive 1 message containing only JSON data according to the inputs JSON schema above
and you will generate a JSON response that is a valid response according to the result JSON schema above.

You will reply with nothing more than the JSON you've generated so that the calling code
can successfully parse your answer."""

    def _get_inputs_json_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the inputs type."""
        inputs_type = self.__class__.__orig_bases__[0].__args__[0]
        return _type_to_json_schema(inputs_type)

    def _get_result_json_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the result type."""
        result_type = self.__class__.__orig_bases__[0].__args__[1]
        if hasattr(result_type, "model_json_schema"):
            return _type_to_json_schema(result_type)
        return {"type": self._python_type_to_json_type(result_type)}

    def _python_type_to_json_type(self, python_type: type) -> str:
        """Convert Python type to JSON schema type."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return type_map.get(python_type, "string")

    async def _generate_answer(self) -> None:
        """Generate the answer from the LLM asynchronously."""
        # For now, run synchronously in a thread pool
        # In the future, we could add async provider methods
        import asyncio

        provider = self._get_provider()

        loop = asyncio.get_event_loop()
        self.answer = await loop.run_in_executor(
            None,
            lambda: provider.generate(
                messages=self.messages,
                temperature=self.__temperature__,
                model=self.__llm_model__,
            ),
        )

    def _parse_answer(self) -> None:
        """Parse the JSON answer from the LLM."""
        stripped = _strip_think_tags(self.answer)
        stripped = _strip_code_fences(stripped)

        try:
            self.parsed_answer = json.loads(stripped)
        except json.JSONDecodeError:
            extracted = _extract_last_json_block(stripped)
            if extracted:
                try:
                    self.parsed_answer = json.loads(extracted)
                    return
                except json.JSONDecodeError:
                    pass

            raise LlmBackedCommandError(
                f"Could not parse result JSON",
                raw_answer=self.answer,
                stripped_answer=stripped,
            )

    def _attempt_to_recover_from_bad_format(self) -> None:
        """Attempt to recover from badly formatted responses."""
        if isinstance(self.parsed_answer, dict) and list(self.parsed_answer.keys()) == ["result"]:
            result_value = self.parsed_answer["result"]
            self.final_answer = result_value
        else:
            self.final_answer = self.parsed_answer
