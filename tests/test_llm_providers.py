"""Tests for LLM Provider implementations"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import BaseModel

from foobara_py.ai.llm_backed_command import (
    LlmProvider,
    LlmMessage,
    AnthropicProvider,
    OpenAIProvider,
    OllamaProvider,
    set_default_llm_provider,
    get_default_llm_provider,
)


class TestLlmProvider:
    """Test LlmProvider abstract base class"""

    def test_is_abstract(self):
        """Should not be able to instantiate abstract provider"""
        with pytest.raises(TypeError):
            LlmProvider()


class TestAnthropicProvider:
    """Test AnthropicProvider"""

    def test_initialization(self):
        """Should initialize with default model"""
        provider = AnthropicProvider()
        assert provider.default_model == "claude-sonnet-4-20250514"

    def test_initialization_custom_model(self):
        """Should initialize with custom model"""
        provider = AnthropicProvider(model="claude-opus-4-20241022")
        assert provider.default_model == "claude-opus-4-20241022"

    def test_generate_simple(self):
        """Should generate response from simple messages"""
        with patch('foobara_py.apis.anthropic.CreateMessage') as mock_create_message:
            # Mock the CreateMessage.run outcome
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_result.content = [Mock(text="Hello there!")]
            mock_outcome.unwrap.return_value = mock_result
            mock_create_message.run.return_value = mock_outcome

            provider = AnthropicProvider()
            messages = [
                LlmMessage(role="user", content="Hi!")
            ]

            result = provider.generate(messages)

            assert result == "Hello there!"
            mock_create_message.run.assert_called_once()

    def test_generate_with_system_message(self):
        """Should handle system messages separately"""
        with patch('foobara_py.apis.anthropic.CreateMessage') as mock_create_message:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_result.content = [Mock(text="Response")]
            mock_outcome.unwrap.return_value = mock_result
            mock_create_message.run.return_value = mock_outcome

            provider = AnthropicProvider()
            messages = [
                LlmMessage(role="system", content="You are helpful."),
                LlmMessage(role="user", content="Hello"),
            ]

            result = provider.generate(messages)

            # Verify system was passed separately
            call_kwargs = mock_create_message.run.call_args.kwargs
            assert call_kwargs["system"] == "You are helpful."
            assert len(call_kwargs["messages"]) == 1
            assert result == "Response"

    def test_generate_with_temperature(self):
        """Should pass temperature to API"""
        with patch('foobara_py.apis.anthropic.CreateMessage') as mock_create_message:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_result.content = [Mock(text="Response")]
            mock_outcome.unwrap.return_value = mock_result
            mock_create_message.run.return_value = mock_outcome

            provider = AnthropicProvider()
            messages = [LlmMessage(role="user", content="Hi")]

            provider.generate(messages, temperature=0.7)

            call_kwargs = mock_create_message.run.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7

    def test_generate_with_custom_model(self):
        """Should use custom model when provided"""
        with patch('foobara_py.apis.anthropic.CreateMessage') as mock_create_message:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_result.content = [Mock(text="Response")]
            mock_outcome.unwrap.return_value = mock_result
            mock_create_message.run.return_value = mock_outcome

            provider = AnthropicProvider(model="claude-sonnet-4-20250514")
            messages = [LlmMessage(role="user", content="Hi")]

            provider.generate(messages, model="claude-opus-4-20241022")

            call_kwargs = mock_create_message.run.call_args.kwargs
            assert call_kwargs["model"] == "claude-opus-4-20241022"

    def test_generate_failure(self):
        """Should raise error on API failure"""
        with patch('foobara_py.apis.anthropic.CreateMessage') as mock_create_message:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = True
            mock_outcome.errors = ["API error"]
            mock_create_message.run.return_value = mock_outcome

            provider = AnthropicProvider()
            messages = [LlmMessage(role="user", content="Hi")]

            with pytest.raises(RuntimeError, match="LLM request failed"):
                provider.generate(messages)


class TestOpenAIProvider:
    """Test OpenAIProvider"""

    def test_initialization(self):
        """Should initialize with default model"""
        provider = OpenAIProvider()
        assert provider.default_model == "gpt-4o"

    def test_initialization_custom_model(self):
        """Should initialize with custom model"""
        provider = OpenAIProvider(model="gpt-4o-mini")
        assert provider.default_model == "gpt-4o-mini"

    def test_generate_simple(self):
        """Should generate response"""
        with patch('foobara_py.apis.openai.CreateChatCompletion') as mock_create_chat:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.content = "Hello there!"
            mock_choice.message = mock_message
            mock_result.choices = [mock_choice]
            mock_outcome.unwrap.return_value = mock_result
            mock_create_chat.run.return_value = mock_outcome

            provider = OpenAIProvider()
            messages = [LlmMessage(role="user", content="Hi!")]

            result = provider.generate(messages)

            assert result == "Hello there!"
            mock_create_chat.run.assert_called_once()

    def test_generate_with_system_message(self):
        """Should include system messages"""
        with patch('foobara_py.apis.openai.CreateChatCompletion') as mock_create_chat:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.content = "Response"
            mock_choice.message = mock_message
            mock_result.choices = [mock_choice]
            mock_outcome.unwrap.return_value = mock_result
            mock_create_chat.run.return_value = mock_outcome

            provider = OpenAIProvider()
            messages = [
                LlmMessage(role="system", content="Be helpful"),
                LlmMessage(role="user", content="Hi"),
            ]

            result = provider.generate(messages)

            call_kwargs = mock_create_chat.run.call_args.kwargs
            assert len(call_kwargs["messages"]) == 2
            assert result == "Response"

    def test_generate_with_temperature(self):
        """Should pass temperature"""
        with patch('foobara_py.apis.openai.CreateChatCompletion') as mock_create_chat:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.content = "Response"
            mock_choice.message = mock_message
            mock_result.choices = [mock_choice]
            mock_outcome.unwrap.return_value = mock_result
            mock_create_chat.run.return_value = mock_outcome

            provider = OpenAIProvider()
            messages = [LlmMessage(role="user", content="Hi")]

            provider.generate(messages, temperature=0.9)

            call_kwargs = mock_create_chat.run.call_args.kwargs
            assert call_kwargs["temperature"] == 0.9

    def test_generate_failure(self):
        """Should raise error on failure"""
        with patch('foobara_py.apis.openai.CreateChatCompletion') as mock_create_chat:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = True
            mock_outcome.errors = ["API error"]
            mock_create_chat.run.return_value = mock_outcome

            provider = OpenAIProvider()
            messages = [LlmMessage(role="user", content="Hi")]

            with pytest.raises(RuntimeError, match="LLM request failed"):
                provider.generate(messages)


class TestOllamaProvider:
    """Test OllamaProvider"""

    def test_initialization(self):
        """Should initialize with default model"""
        provider = OllamaProvider()
        assert provider.default_model == "llama3.2"

    def test_initialization_custom_model(self):
        """Should initialize with custom model"""
        provider = OllamaProvider(model="mistral")
        assert provider.default_model == "mistral"

    def test_generate_simple(self):
        """Should generate response"""
        with patch('foobara_py.apis.ollama.GenerateChatCompletion') as mock_generate:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_message = Mock()
            mock_message.content = "Hello there!"
            mock_result.message = mock_message
            mock_outcome.unwrap.return_value = mock_result
            mock_generate.run.return_value = mock_outcome

            provider = OllamaProvider()
            messages = [LlmMessage(role="user", content="Hi!")]

            result = provider.generate(messages)

            assert result == "Hello there!"
            mock_generate.run.assert_called_once()

    def test_generate_with_temperature_zero(self):
        """Should not pass options when temperature is 0"""
        with patch('foobara_py.apis.ollama.GenerateChatCompletion') as mock_generate:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_message = Mock()
            mock_message.content = "Response"
            mock_result.message = mock_message
            mock_outcome.unwrap.return_value = mock_result
            mock_generate.run.return_value = mock_outcome

            provider = OllamaProvider()
            messages = [LlmMessage(role="user", content="Hi")]

            provider.generate(messages, temperature=0.0)

            call_kwargs = mock_generate.run.call_args.kwargs
            assert call_kwargs.get("options") is None

    def test_generate_with_temperature_nonzero(self):
        """Should pass options when temperature is not 0"""
        with patch('foobara_py.apis.ollama.GenerateChatCompletion') as mock_generate:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = False
            mock_result = Mock()
            mock_message = Mock()
            mock_message.content = "Response"
            mock_result.message = mock_message
            mock_outcome.unwrap.return_value = mock_result
            mock_generate.run.return_value = mock_outcome

            provider = OllamaProvider()
            messages = [LlmMessage(role="user", content="Hi")]

            provider.generate(messages, temperature=0.7)

            call_kwargs = mock_generate.run.call_args.kwargs
            assert call_kwargs["options"] is not None
            assert call_kwargs["options"].temperature == 0.7

    def test_generate_failure(self):
        """Should raise error on failure"""
        with patch('foobara_py.apis.ollama.GenerateChatCompletion') as mock_generate:
            mock_outcome = Mock()
            mock_outcome.is_failure.return_value = True
            mock_outcome.errors = ["Connection error"]
            mock_generate.run.return_value = mock_outcome

            provider = OllamaProvider()
            messages = [LlmMessage(role="user", content="Hi")]

            with pytest.raises(RuntimeError, match="LLM request failed"):
                provider.generate(messages)


class TestDefaultProvider:
    """Test default provider management"""

    def test_get_default_provider_initial(self):
        """Should return Anthropic provider by default"""
        # Reset global state
        import foobara_py.ai.llm_backed_command as llm_module
        llm_module._default_provider = None

        provider = get_default_llm_provider()
        assert isinstance(provider, AnthropicProvider)

    def test_set_default_provider(self):
        """Should set and get custom default provider"""
        custom_provider = OpenAIProvider(model="gpt-4o-mini")
        set_default_llm_provider(custom_provider)

        provider = get_default_llm_provider()
        assert provider is custom_provider
        assert isinstance(provider, OpenAIProvider)

    def test_set_default_provider_ollama(self):
        """Should work with Ollama provider"""
        custom_provider = OllamaProvider(model="mistral")
        set_default_llm_provider(custom_provider)

        provider = get_default_llm_provider()
        assert provider is custom_provider
        assert isinstance(provider, OllamaProvider)
        assert provider.default_model == "mistral"
