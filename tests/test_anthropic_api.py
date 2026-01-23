"""Tests for Anthropic API Client"""

import pytest
import asyncio

try:
    import httpx
    from foobara_py.apis.anthropic import (
        CreateMessage,
        CountTokens,
        Message,
        MessageResponse,
        CountTokensResponse,
        create_message_simple,
        create_message_with_tools,
    )
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@pytest.fixture
def anthropic_mock(monkeypatch):
    """Fixture to mock Anthropic API"""
    if not HTTPX_AVAILABLE:
        pytest.skip("httpx not installed")

    import httpx
    from unittest.mock import MagicMock

    responses = []
    response_index = [0]

    async def mock_request(method, url, **kwargs):
        """Mock httpx request"""
        if response_index[0] < len(responses):
            resp_config = responses[response_index[0]]
            response_index[0] += 1
        elif responses:
            resp_config = responses[-1]
        else:
            raise httpx.ConnectError("No mock response configured")

        mock_response = MagicMock()
        mock_response.status_code = resp_config.get("status_code", 200)
        mock_response.json.return_value = resp_config.get("json", {})
        mock_response.text = str(resp_config.get("json", ""))

        return mock_response

    class MockAsyncClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, method, url, **kwargs):
            return await mock_request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    class AnthropicMock:
        def add_response(self, json=None, status_code=200):
            responses.append({"json": json, "status_code": status_code})

    return AnthropicMock()


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestCreateMessage:
    """Test CreateMessage command"""

    def test_simple_message(self, anthropic_mock):
        """Should create a simple message"""
        anthropic_mock.add_response(json={
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! How can I help you?"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 15}
        })

        command = CreateMessage(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="Hello!")],
            max_tokens=100
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert isinstance(response, MessageResponse)
        assert response.id == "msg_123"
        assert response.role == "assistant"
        assert len(response.content) == 1
        assert response.content[0]["text"] == "Hello! How can I help you?"
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 15

    def test_message_with_system_prompt(self, anthropic_mock):
        """Should send message with system prompt"""
        anthropic_mock.add_response(json={
            "id": "msg_456",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "4"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 20, "output_tokens": 5}
        })

        command = CreateMessage(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="What is 2+2?")],
            system="You are a helpful math tutor.",
            max_tokens=50
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.content[0]["text"] == "4"

    def test_message_with_temperature(self, anthropic_mock):
        """Should send message with temperature"""
        anthropic_mock.add_response(json={
            "id": "msg_789",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Creative response!"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 15, "output_tokens": 10}
        })

        command = CreateMessage(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="Tell me a story")],
            temperature=0.9,
            max_tokens=100
        ))

        assert outcome.is_success()

    def test_message_with_tools(self, anthropic_mock):
        """Should send message with tools"""
        anthropic_mock.add_response(json={
            "id": "msg_tool",
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "tool_use",
                "id": "tool_123",
                "name": "get_weather",
                "input": {"location": "Paris"}
            }],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 50, "output_tokens": 20}
        })

        tools = [{
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        }]

        command = CreateMessage(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="What's the weather in Paris?")],
            tools=tools,
            max_tokens=200
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.stop_reason == "tool_use"
        assert response.content[0]["type"] == "tool_use"
        assert response.content[0]["name"] == "get_weather"

    def test_message_with_stop_sequences(self, anthropic_mock):
        """Should send message with stop sequences"""
        anthropic_mock.add_response(json={
            "id": "msg_stop",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Here is my response"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "stop_sequence",
            "stop_sequence": "\n\n",
            "usage": {"input_tokens": 10, "output_tokens": 10}
        })

        command = CreateMessage(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="Tell me something")],
            stop_sequences=["\n\n", "###"],
            max_tokens=100
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.stop_sequence == "\n\n"

    def test_message_401_error(self, anthropic_mock):
        """Should handle authentication error"""
        anthropic_mock.add_response(
            status_code=401,
            json={"error": {"type": "authentication_error", "message": "Invalid API key"}}
        )

        command = CreateMessage(api_key="invalid-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="Hello")],
            max_tokens=50
        ))

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("authentication_failed" in error.symbol for error in errors)

    def test_message_429_rate_limit(self, anthropic_mock):
        """Should handle rate limit error"""
        anthropic_mock.add_response(
            status_code=429,
            json={"error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}}
        )

        command = CreateMessage(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="Hello")],
            max_tokens=50
        ))

        assert outcome.is_failure()
        errors = outcome.errors
        assert any("rate_limit_exceeded" in error.symbol for error in errors)

    def test_multi_turn_conversation(self, anthropic_mock):
        """Should support multi-turn conversations"""
        anthropic_mock.add_response(json={
            "id": "msg_multi",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "That's a great follow-up question!"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 30, "output_tokens": 15}
        })

        command = CreateMessage(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[
                Message(role="user", content="What is Python?"),
                Message(role="assistant", content="Python is a programming language."),
                Message(role="user", content="What can I use it for?")
            ],
            max_tokens=100
        ))

        assert outcome.is_success()


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestCountTokens:
    """Test CountTokens command"""

    def test_count_tokens_simple(self, anthropic_mock):
        """Should count tokens in a simple message"""
        anthropic_mock.add_response(json={
            "input_tokens": 10
        })

        command = CountTokens(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="Hello!")]
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert isinstance(response, CountTokensResponse)
        assert response.input_tokens == 10

    def test_count_tokens_with_system(self, anthropic_mock):
        """Should count tokens including system prompt"""
        anthropic_mock.add_response(json={
            "input_tokens": 25
        })

        command = CountTokens(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="What is 2+2?")],
            system="You are a helpful assistant."
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.input_tokens == 25

    def test_count_tokens_with_tools(self, anthropic_mock):
        """Should count tokens including tools"""
        anthropic_mock.add_response(json={
            "input_tokens": 50
        })

        tools = [{
            "name": "calculator",
            "description": "Perform calculations",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                }
            }
        }]

        command = CountTokens(api_key="test-key")
        outcome = asyncio.run(command.run(
            messages=[Message(role="user", content="Calculate 2+2")],
            tools=tools
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.input_tokens == 50


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestHelperFunctions:
    """Test helper functions"""

    def test_create_message_simple(self, anthropic_mock):
        """Should create simple message command"""
        anthropic_mock.add_response(json={
            "id": "msg_simple",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Paris"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 15, "output_tokens": 5}
        })

        outcome = asyncio.run(create_message_simple(
            api_key="test-key",
            prompt="What is the capital of France?",
            system="You are a geography expert."
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.content[0]["text"] == "Paris"

    def test_create_message_with_tools_helper(self, anthropic_mock):
        """Should create message with tools using helper"""
        anthropic_mock.add_response(json={
            "id": "msg_tools",
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "tool_use",
                "id": "tool_456",
                "name": "get_weather",
                "input": {"location": "London"}
            }],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 40, "output_tokens": 25}
        })

        tools = [{
            "name": "get_weather",
            "description": "Get weather",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }]

        outcome = asyncio.run(create_message_with_tools(
            api_key="test-key",
            prompt="What's the weather in London?",
            tools=tools
        ))

        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.stop_reason == "tool_use"


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestMessageModels:
    """Test message models"""

    def test_message_with_string_content(self):
        """Should create message with string content"""
        msg = Message(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_message_with_list_content(self):
        """Should create message with list content (multimodal)"""
        from foobara_py.apis.anthropic import MessageContent

        content = [
            MessageContent(type="text", text="What is in this image?"),
            MessageContent(type="image", source={"type": "base64", "data": "..."})
        ]
        msg = Message(role="user", content=content)
        assert msg.role == "user"
        assert len(msg.content) == 2
        assert msg.content[0].type == "text"
        assert msg.content[1].type == "image"
