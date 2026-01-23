"""Tests for OpenAI API Client"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, AsyncMock
from pydantic import BaseModel

# Create mock openai module before importing our code
mock_openai_module = MagicMock()
sys.modules['openai'] = mock_openai_module

from foobara_py.apis.openai import (
    # Types
    ChatMessage,
    FunctionCall,
    ToolCall,
    ToolDefinition,
    FunctionDefinition,
    ResponseMessage,
    Choice,
    ChatCompletion,
    Usage,
    PromptTokensDetails,
    CompletionTokensDetails,
    ModelInfo,
    # Commands
    CreateChatCompletion,
    CreateChatCompletionAsync,
    CreateChatCompletionInputs,
    CreateChatCompletionResult,
    ListModels,
    # Errors
    OpenAIError,
    AuthenticationError,
    RateLimitError,
    InvalidRequestError,
    # Functions
    chat,
    stream_chat_completion,
    # Constants
    GPT_4O,
    GPT_4O_MINI,
    GPT_3_5_TURBO,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
)


class TestTypes:
    """Test OpenAI type definitions"""

    def test_chat_message_simple(self):
        """Should create simple chat message"""
        msg = ChatMessage(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_chat_message_system(self):
        """Should create system message"""
        msg = ChatMessage(role="system", content="You are helpful.")
        assert msg.role == "system"
        assert msg.content == "You are helpful."

    def test_chat_message_assistant(self):
        """Should create assistant message"""
        msg = ChatMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"

    def test_chat_message_with_tool_calls(self):
        """Should create message with tool calls"""
        tool_call = ToolCall(
            id="call_123",
            type="function",
            function=FunctionCall(
                name="calculator",
                arguments='{"expression": "2 + 2"}'
            )
        )
        msg = ChatMessage(role="assistant", tool_calls=[tool_call])
        assert msg.tool_calls[0].id == "call_123"
        assert msg.tool_calls[0].function.name == "calculator"

    def test_chat_message_tool_response(self):
        """Should create tool response message"""
        msg = ChatMessage(
            role="tool",
            content="4",
            tool_call_id="call_123"
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"

    def test_function_definition(self):
        """Should create function definition"""
        func = FunctionDefinition(
            name="calculator",
            description="Perform arithmetic calculations",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            }
        )
        assert func.name == "calculator"
        assert "expression" in func.parameters["properties"]

    def test_tool_definition(self):
        """Should create tool definition"""
        tool = ToolDefinition(
            type="function",
            function=FunctionDefinition(
                name="calculator",
                description="Calculate math",
                parameters={"type": "object"}
            )
        )
        assert tool.type == "function"
        assert tool.function.name == "calculator"

    def test_usage(self):
        """Should create usage info"""
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_usage_with_details(self):
        """Should create usage with details"""
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            prompt_tokens_details=PromptTokensDetails(
                cached_tokens=20
            ),
            completion_tokens_details=CompletionTokensDetails(
                reasoning_tokens=10
            )
        )
        assert usage.prompt_tokens_details.cached_tokens == 20
        assert usage.completion_tokens_details.reasoning_tokens == 10

    def test_response_message(self):
        """Should create response message"""
        msg = ResponseMessage(
            content="Hello!",
            refusal=None
        )
        assert msg.role == "assistant"
        assert msg.content == "Hello!"

    def test_choice(self):
        """Should create choice"""
        choice = Choice(
            index=0,
            message=ResponseMessage(content="Hello!"),
            finish_reason="stop"
        )
        assert choice.index == 0
        assert choice.finish_reason == "stop"

    def test_model_info(self):
        """Should create model info"""
        model = ModelInfo(
            id="gpt-test",
            name="GPT Test",
            description="Test model",
            context_window=128000,
            max_output_tokens=4096,
        )
        assert model.id == "gpt-test"
        assert model.context_window == 128000

    def test_model_constants(self):
        """Should have correct model constants"""
        assert GPT_4O == "gpt-4o"
        assert GPT_4O_MINI == "gpt-4o-mini"
        assert GPT_3_5_TURBO == "gpt-3.5-turbo"
        assert DEFAULT_MODEL == GPT_4O_MINI

    def test_available_models(self):
        """Should have available models list"""
        assert len(AVAILABLE_MODELS) > 0
        model_ids = [m.id for m in AVAILABLE_MODELS]
        assert GPT_4O in model_ids
        assert GPT_4O_MINI in model_ids


class TestCreateChatCompletionInputs:
    """Test CreateChatCompletionInputs"""

    def test_minimal_inputs(self):
        """Should create with minimal inputs"""
        inputs = CreateChatCompletionInputs(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        assert inputs.model == DEFAULT_MODEL
        assert inputs.n == 1

    def test_full_inputs(self):
        """Should create with all options"""
        inputs = CreateChatCompletionInputs(
            model=GPT_4O,
            messages=[
                ChatMessage(role="system", content="You are helpful"),
                ChatMessage(role="user", content="Hello")
            ],
            max_tokens=2048,
            temperature=0.7,
            top_p=0.9,
            n=2,
            stop=["END"],
            presence_penalty=0.5,
            frequency_penalty=0.5,
            tools=[
                ToolDefinition(
                    type="function",
                    function=FunctionDefinition(
                        name="test",
                        description="Test tool",
                        parameters={"type": "object"}
                    )
                )
            ],
            seed=42,
        )
        assert inputs.model == GPT_4O
        assert inputs.max_tokens == 2048
        assert inputs.temperature == 0.7
        assert len(inputs.tools) == 1


def create_mock_response(
    response_id="chatcmpl-123",
    model=GPT_4O_MINI,
    content="Hello!",
    finish_reason="stop",
    prompt_tokens=10,
    completion_tokens=8,
    tool_calls=None
):
    """Helper to create mock OpenAI response"""
    mock_response = Mock()
    mock_response.id = response_id
    mock_response.model = model
    mock_response.created = 1700000000
    mock_response.system_fingerprint = None

    mock_message = Mock()
    mock_message.role = "assistant"
    mock_message.content = content
    mock_message.refusal = None
    mock_message.tool_calls = tool_calls

    mock_choice = Mock()
    mock_choice.index = 0
    mock_choice.message = mock_message
    mock_choice.logprobs = None
    mock_choice.finish_reason = finish_reason
    mock_response.choices = [mock_choice]

    mock_usage = Mock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = prompt_tokens + completion_tokens
    mock_response.usage = mock_usage

    return mock_response


class TestCreateChatCompletion:
    """Test CreateChatCompletion command"""

    def test_create_chat_completion_success(self):
        """Should create chat completion successfully"""
        mock_response = create_mock_response(
            content="Hello! How can I help you?"
        )

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        outcome = CreateChatCompletion.run(
            messages=[ChatMessage(role="user", content="Hello!")],
            model=GPT_4O_MINI
        )

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.id == "chatcmpl-123"
        assert result.choices[0].message.content == "Hello! How can I help you?"
        assert result.usage.prompt_tokens == 10

    def test_create_chat_completion_with_system(self):
        """Should pass system message"""
        mock_response = create_mock_response(content="Bonjour!")

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        outcome = CreateChatCompletion.run(
            messages=[
                ChatMessage(role="system", content="You are a French assistant."),
                ChatMessage(role="user", content="Hello!")
            ],
        )

        assert outcome.is_success()
        # Verify messages were passed correctly
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"

    def test_create_chat_completion_with_tools(self):
        """Should handle tool calls"""
        mock_tool_call = Mock()
        mock_tool_call.id = "call_abc"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "calculator"
        mock_tool_call.function.arguments = '{"expression": "2 + 2"}'

        mock_response = create_mock_response(
            content=None,
            finish_reason="tool_calls",
            tool_calls=[mock_tool_call]
        )

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        tool = ToolDefinition(
            type="function",
            function=FunctionDefinition(
                name="calculator",
                description="Calculate math",
                parameters={"type": "object", "properties": {"expression": {"type": "string"}}}
            )
        )

        outcome = CreateChatCompletion.run(
            messages=[ChatMessage(role="user", content="What is 2+2?")],
            tools=[tool],
        )

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.choices[0].finish_reason == "tool_calls"
        assert result.choices[0].message.tool_calls[0].function.name == "calculator"

    def test_create_chat_completion_authentication_error(self):
        """Should handle authentication error"""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("Invalid API key")
        mock_openai_module.OpenAI.return_value = mock_client

        outcome = CreateChatCompletion.run(
            messages=[ChatMessage(role="user", content="Hello!")],
        )

        assert outcome.is_failure()


class TestCreateChatCompletionAsync:
    """Test CreateChatCompletionAsync command"""

    @pytest.mark.asyncio
    async def test_create_chat_completion_async(self):
        """Should create chat completion asynchronously"""
        mock_response = create_mock_response(content="Async response!")

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.AsyncOpenAI.return_value = mock_client

        outcome = await CreateChatCompletionAsync.run(
            messages=[ChatMessage(role="user", content="Hello async!")],
        )

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.id == "chatcmpl-123"
        assert result.choices[0].message.content == "Async response!"


class TestListModels:
    """Test ListModels command"""

    def test_list_models(self):
        """Should list available models"""
        outcome = ListModels.run()

        assert outcome.is_success()
        result = outcome.unwrap()
        assert len(result.models) > 0

        model_ids = [m.id for m in result.models]
        assert GPT_4O in model_ids
        assert GPT_4O_MINI in model_ids


class TestChatFunction:
    """Test chat convenience function"""

    def test_chat_simple(self):
        """Should handle simple chat"""
        mock_response = create_mock_response(
            content="The capital of France is Paris."
        )

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        response = chat("What is the capital of France?")

        assert response == "The capital of France is Paris."

    def test_chat_with_system(self):
        """Should pass system prompt in chat"""
        mock_response = create_mock_response(content="Oui, je peux vous aider!")

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        response = chat(
            "Can you help me?",
            system="Always respond in French."
        )

        assert "Oui" in response


class TestStreamChatCompletion:
    """Test stream_chat_completion function"""

    @pytest.mark.asyncio
    async def test_stream_chat_completion(self):
        """Should stream chat completion chunks"""
        # Create mock chunks
        chunks = []
        for text in ["Hello", " ", "world", "!"]:
            chunk = Mock()
            chunk.choices = [Mock()]
            chunk.choices[0].delta = Mock()
            chunk.choices[0].delta.content = text
            chunks.append(chunk)

        # Create async iterator
        async def mock_stream():
            for chunk in chunks:
                yield chunk

        # Create async context manager that returns async iterator
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_stream()
        mock_context.__aexit__.return_value = None

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_context
        mock_openai_module.AsyncOpenAI.return_value = mock_client

        collected_chunks = []
        async for chunk in stream_chat_completion(
            messages=[ChatMessage(role="user", content="Say hello world")],
        ):
            collected_chunks.append(chunk)

        assert "".join(collected_chunks) == "Hello world!"


class TestConversation:
    """Test multi-turn conversation patterns"""

    def test_multi_turn_conversation(self):
        """Should handle multi-turn conversation"""
        mock_response = create_mock_response(content="My name is GPT.")

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        # Multi-turn conversation
        outcome = CreateChatCompletion.run(
            messages=[
                ChatMessage(role="user", content="Hello, what's your name?"),
                ChatMessage(role="assistant", content="Hi! I'm GPT, an AI assistant made by OpenAI."),
                ChatMessage(role="user", content="What did you say your name was?"),
            ],
        )

        assert outcome.is_success()
        result = outcome.unwrap()
        assert "GPT" in result.choices[0].message.content


class TestToolUseConversation:
    """Test tool use conversation flow"""

    def test_tool_use_flow(self):
        """Should handle complete tool use flow"""
        # First response: tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_calc"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "calculator"
        mock_tool_call.function.arguments = '{"expression": "15 * 23"}'

        mock_response1 = create_mock_response(
            response_id="chatcmpl-tool",
            content=None,
            finish_reason="tool_calls",
            tool_calls=[mock_tool_call]
        )

        # Second response: final answer
        mock_response2 = create_mock_response(
            response_id="chatcmpl-final",
            content="15 * 23 = 345"
        )

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai_module.OpenAI.return_value = mock_client

        calculator = ToolDefinition(
            type="function",
            function=FunctionDefinition(
                name="calculator",
                description="Perform arithmetic",
                parameters={
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"]
                }
            )
        )

        # Step 1: Get tool call request
        outcome1 = CreateChatCompletion.run(
            messages=[ChatMessage(role="user", content="What is 15 * 23?")],
            tools=[calculator],
        )

        assert outcome1.is_success()
        result1 = outcome1.unwrap()
        assert result1.choices[0].finish_reason == "tool_calls"

        # Step 2: Send tool result and get final answer
        outcome2 = CreateChatCompletion.run(
            messages=[
                ChatMessage(role="user", content="What is 15 * 23?"),
                ChatMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="call_calc",
                            type="function",
                            function=FunctionCall(
                                name="calculator",
                                arguments='{"expression": "15 * 23"}'
                            )
                        )
                    ]
                ),
                ChatMessage(role="tool", content="345", tool_call_id="call_calc"),
            ],
            tools=[calculator],
        )

        assert outcome2.is_success()
        result2 = outcome2.unwrap()
        assert "345" in result2.choices[0].message.content
