"""Tests for Ollama API Client"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from pydantic import BaseModel

from foobara_py.apis.ollama import (
    # Types
    ChatMessage,
    ChatCompletionMessage,
    ChatCompletion,
    LocalModel,
    RunningModel,
    ModelDetails,
    GenerateOptions,
    ModelInfo,
    # Commands
    GenerateChatCompletion,
    GenerateChatCompletionAsync,
    GenerateChatCompletionInputs,
    GenerateChatCompletionResult,
    ListLocalModels,
    ListRunningModels,
    # Errors
    OllamaError,
    ConnectionError,
    ModelNotFoundError,
    # Functions
    chat,
    stream_chat_completion,
    get_base_url,
    # Constants
    LLAMA3_2,
    LLAMA3,
    MISTRAL,
    DEFAULT_MODEL,
    COMMON_MODELS,
)


class TestTypes:
    """Test Ollama type definitions"""

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

    def test_chat_message_with_images(self):
        """Should create message with images"""
        msg = ChatMessage(
            role="user",
            content="What's in this image?",
            images=["base64encodedimage=="]
        )
        assert msg.images == ["base64encodedimage=="]

    def test_chat_completion_message(self):
        """Should create chat completion message"""
        msg = ChatCompletionMessage(content="Hello!")
        assert msg.role == "assistant"
        assert msg.content == "Hello!"

    def test_local_model(self):
        """Should create local model"""
        model = LocalModel(
            name="llama3.2:latest",
            size=2000000000,
            digest="abc123"
        )
        assert model.name == "llama3.2:latest"
        assert model.size == 2000000000

    def test_local_model_with_details(self):
        """Should create local model with details"""
        details = ModelDetails(
            family="llama",
            parameter_size="3B",
            quantization_level="q4_0"
        )
        model = LocalModel(
            name="llama3.2:latest",
            details=details
        )
        assert model.details.family == "llama"
        assert model.details.parameter_size == "3B"

    def test_running_model(self):
        """Should create running model"""
        model = RunningModel(
            name="llama3.2:latest",
            size=2000000000,
            size_vram=1500000000
        )
        assert model.name == "llama3.2:latest"
        assert model.size_vram == 1500000000

    def test_generate_options(self):
        """Should create generate options"""
        options = GenerateOptions(
            temperature=0.7,
            top_p=0.9,
            num_predict=100,
            stop=["END"]
        )
        assert options.temperature == 0.7
        assert options.top_p == 0.9
        assert options.num_predict == 100
        assert options.stop == ["END"]

    def test_model_info(self):
        """Should create model info"""
        info = ModelInfo(
            id="llama3.2",
            name="Llama 3.2",
            description="Meta's latest model",
            parameter_size="3B"
        )
        assert info.id == "llama3.2"
        assert info.parameter_size == "3B"

    def test_model_constants(self):
        """Should have correct model constants"""
        assert LLAMA3_2 == "llama3.2"
        assert LLAMA3 == "llama3"
        assert MISTRAL == "mistral"
        assert DEFAULT_MODEL == LLAMA3_2

    def test_common_models(self):
        """Should have common models list"""
        assert len(COMMON_MODELS) > 0
        model_ids = [m.id for m in COMMON_MODELS]
        assert LLAMA3_2 in model_ids
        assert MISTRAL in model_ids


class TestGenerateChatCompletionInputs:
    """Test GenerateChatCompletionInputs"""

    def test_minimal_inputs(self):
        """Should create with minimal inputs"""
        inputs = GenerateChatCompletionInputs(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        assert inputs.model == DEFAULT_MODEL

    def test_full_inputs(self):
        """Should create with all options"""
        inputs = GenerateChatCompletionInputs(
            model=LLAMA3_2,
            messages=[
                ChatMessage(role="system", content="You are helpful"),
                ChatMessage(role="user", content="Hello")
            ],
            options=GenerateOptions(temperature=0.7),
            format="json",
            keep_alive="5m"
        )
        assert inputs.model == LLAMA3_2
        assert inputs.options.temperature == 0.7
        assert inputs.format == "json"


class TestGetBaseUrl:
    """Test get_base_url function"""

    def test_default_url(self):
        """Should return default URL"""
        with patch.dict("os.environ", {}, clear=True):
            # Remove OLLAMA_API_URL if present
            import os
            old_val = os.environ.pop("OLLAMA_API_URL", None)
            try:
                url = get_base_url()
                assert url == "http://localhost:11434"
            finally:
                if old_val:
                    os.environ["OLLAMA_API_URL"] = old_val

    def test_custom_url(self):
        """Should return custom URL from environment"""
        with patch.dict("os.environ", {"OLLAMA_API_URL": "http://myserver:8080"}):
            url = get_base_url()
            assert url == "http://myserver:8080"


class TestGenerateChatCompletion:
    """Test GenerateChatCompletion command"""

    @patch("httpx.Client")
    def test_generate_chat_completion_success(self, mock_client_class):
        """Should generate chat completion successfully"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Hello! How can I help you?"},
            "done": True,
            "total_duration": 1000000000,
            "prompt_eval_count": 10,
            "eval_count": 8,
            "done_reason": "stop"
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        outcome = GenerateChatCompletion.run(
            model="llama3.2",
            messages=[ChatMessage(role="user", content="Hello!")]
        )

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result.model == "llama3.2"
        assert result.message.content == "Hello! How can I help you?"
        assert result.done is True

    @patch("httpx.Client")
    def test_generate_chat_completion_with_options(self, mock_client_class):
        """Should pass generation options"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Response with options"},
            "done": True,
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        outcome = GenerateChatCompletion.run(
            model="llama3.2",
            messages=[ChatMessage(role="user", content="Hello!")],
            options=GenerateOptions(temperature=0.5, top_p=0.9)
        )

        assert outcome.is_success()
        # Verify options were passed in request
        call_kwargs = mock_client.post.call_args.kwargs
        assert "options" in call_kwargs["json"]
        assert call_kwargs["json"]["options"]["temperature"] == 0.5

    @patch("httpx.Client")
    def test_generate_chat_completion_connection_error(self, mock_client_class):
        """Should handle connection error"""
        import httpx
        mock_client = Mock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        outcome = GenerateChatCompletion.run(
            model="llama3.2",
            messages=[ChatMessage(role="user", content="Hello!")]
        )

        assert outcome.is_failure()


class TestGenerateChatCompletionAsync:
    """Test GenerateChatCompletionAsync command"""

    @pytest.mark.asyncio
    async def test_generate_chat_completion_async(self):
        """Should generate chat completion asynchronously"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Async response!"},
            "done": True,
        }
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            outcome = await GenerateChatCompletionAsync.run(
                model="llama3.2",
                messages=[ChatMessage(role="user", content="Hello async!")]
            )

            assert outcome.is_success()
            result = outcome.unwrap()
            assert result.message.content == "Async response!"


class TestListLocalModels:
    """Test ListLocalModels command"""

    @patch("httpx.Client")
    def test_list_local_models(self, mock_client_class):
        """Should list local models"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "llama3.2:latest",
                    "size": 2000000000,
                    "digest": "abc123"
                },
                {
                    "name": "mistral:latest",
                    "size": 4000000000,
                    "digest": "def456"
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        outcome = ListLocalModels.run()

        assert outcome.is_success()
        result = outcome.unwrap()
        assert len(result.models) == 2
        assert result.models[0].name == "llama3.2:latest"
        assert result.models[1].name == "mistral:latest"


class TestListRunningModels:
    """Test ListRunningModels command"""

    @patch("httpx.Client")
    def test_list_running_models(self, mock_client_class):
        """Should list running models"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "llama3.2:latest",
                    "size": 2000000000,
                    "size_vram": 1500000000
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        outcome = ListRunningModels.run()

        assert outcome.is_success()
        result = outcome.unwrap()
        assert len(result.models) == 1
        assert result.models[0].name == "llama3.2:latest"


class TestChatFunction:
    """Test chat convenience function"""

    @patch("httpx.Client")
    def test_chat_simple(self, mock_client_class):
        """Should handle simple chat"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "The capital of France is Paris."},
            "done": True,
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        response = chat("What is the capital of France?", model="llama3.2")

        assert response == "The capital of France is Paris."

    @patch("httpx.Client")
    def test_chat_with_system(self, mock_client_class):
        """Should pass system prompt in chat"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Oui, je peux vous aider!"},
            "done": True,
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        response = chat(
            "Can you help me?",
            model="llama3.2",
            system="Always respond in French."
        )

        assert "Oui" in response

        # Verify system message was passed
        call_kwargs = mock_client.post.call_args.kwargs
        messages = call_kwargs["json"]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"


class TestStreamChatCompletion:
    """Test stream_chat_completion function"""

    @pytest.mark.asyncio
    async def test_stream_chat_completion(self):
        """Should stream chat completion chunks"""
        # Create mock lines (NDJSON format)
        lines = [
            '{"message": {"content": "Hello"}, "done": false}',
            '{"message": {"content": " "}, "done": false}',
            '{"message": {"content": "world"}, "done": false}',
            '{"message": {"content": "!"}, "done": true}',
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        # Create a proper async context manager for the stream response
        class MockStreamResponse:
            def __init__(self):
                self.aiter_lines = mock_aiter_lines

            def raise_for_status(self):
                pass

        class MockStreamContextManager:
            async def __aenter__(self):
                return MockStreamResponse()

            async def __aexit__(self, *args):
                pass

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def stream(self, method, url, **kwargs):
                return MockStreamContextManager()

        with patch("foobara_py.apis.ollama.commands.httpx.AsyncClient", MockAsyncClient):
            collected_chunks = []
            async for chunk in stream_chat_completion(
                messages=[ChatMessage(role="user", content="Say hello world")],
                model="llama3.2"
            ):
                collected_chunks.append(chunk)

            assert "".join(collected_chunks) == "Hello world!"


class TestConversation:
    """Test multi-turn conversation patterns"""

    @patch("httpx.Client")
    def test_multi_turn_conversation(self, mock_client_class):
        """Should handle multi-turn conversation"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "My name is Llama."},
            "done": True,
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        # Multi-turn conversation
        outcome = GenerateChatCompletion.run(
            model="llama3.2",
            messages=[
                ChatMessage(role="user", content="Hello, what's your name?"),
                ChatMessage(role="assistant", content="Hi! I'm Llama, an AI assistant."),
                ChatMessage(role="user", content="What did you say your name was?"),
            ],
        )

        assert outcome.is_success()
        result = outcome.unwrap()
        assert "Llama" in result.message.content
