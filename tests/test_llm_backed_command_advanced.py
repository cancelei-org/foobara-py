"""Advanced tests for LlmBackedCommand"""

import pytest
import json
from unittest.mock import Mock, MagicMock
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from foobara_py.ai.llm_backed_command import (
    LlmBackedCommand,
    AsyncLlmBackedCommand,
    LlmBackedCommandError,
    LlmProvider,
    LlmMessage,
    _type_to_json_schema,
    _strip_think_tags,
    _strip_code_fences,
    _extract_last_json_block,
)


class MockProvider(LlmProvider):
    """Mock LLM provider for testing"""

    def __init__(self, response: str = '{"result": "test"}'):
        self.response = response
        self.calls = []

    def generate(self, messages, temperature=0.0, model=None):
        self.calls.append({
            "messages": messages,
            "temperature": temperature,
            "model": model
        })
        return self.response


class TestHelperFunctions:
    """Test helper functions in detail"""

    def test_strip_think_tags_empty(self):
        """Should handle empty string"""
        assert _strip_think_tags("") == ""

    def test_strip_think_tags_no_tags(self):
        """Should leave text without tags unchanged"""
        text = "This is normal text"
        assert _strip_think_tags(text) == text

    def test_strip_think_tags_multiple(self):
        """Should remove multiple think tags"""
        text = "<THINK>first</THINK>content<THINK>second</THINK>more"
        result = _strip_think_tags(text)
        assert "first" not in result
        assert "second" not in result
        assert "content" in result
        assert "more" in result

    def test_strip_think_tags_nested_content(self):
        """Should handle nested-like content"""
        text = "<THINK>outer<inner>nested</inner>outer</THINK>final"
        result = _strip_think_tags(text)
        assert "nested" not in result
        assert "final" in result

    def test_strip_code_fences_empty(self):
        """Should handle empty string"""
        assert _strip_code_fences("") == ""

    def test_strip_code_fences_no_fences(self):
        """Should leave unfenced text unchanged"""
        text = "normal text"
        assert _strip_code_fences(text) == text

    def test_strip_code_fences_multiple_languages(self):
        """Should handle various language tags"""
        text = '```python\ncode here\n```'
        result = _strip_code_fences(text)
        assert result == "code here"

    def test_extract_last_json_block_none(self):
        """Should return None when no JSON blocks"""
        text = "just plain text"
        assert _extract_last_json_block(text) is None

    def test_extract_last_json_block_single(self):
        """Should extract single JSON block"""
        text = 'text\n```json\n{"key": "value"}\n```\nmore'
        result = _extract_last_json_block(text)
        assert result == '{"key": "value"}'

    def test_extract_last_json_block_multiple(self):
        """Should extract the last one"""
        text = '```json\n{"first": 1}\n```\ntext\n```json\n{"last": 2}\n```'
        result = _extract_last_json_block(text)
        assert result == '{"last": 2}'

    def test_type_to_json_schema(self):
        """Should convert Pydantic model to JSON schema"""
        class TestModel(BaseModel):
            name: str
            age: int

        schema = _type_to_json_schema(TestModel)
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]


class TestLlmBackedCommandConfiguration:
    """Test LlmBackedCommand configuration options"""

    def test_custom_description(self):
        """Should use custom description"""
        class TestInputs(BaseModel):
            text: str

        class CustomDescCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Custom description here"

        assert CustomDescCommand.__description__ == "Custom description here"

    def test_custom_temperature(self):
        """Should use custom temperature"""
        class TestInputs(BaseModel):
            text: str

        class CustomTempCommand(LlmBackedCommand[TestInputs, str]):
            __temperature__ = 0.8

        assert CustomTempCommand.__temperature__ == 0.8

    def test_custom_model(self):
        """Should use custom model"""
        class TestInputs(BaseModel):
            text: str

        class CustomModelCommand(LlmBackedCommand[TestInputs, str]):
            __llm_model__ = "custom-model-v1"

        assert CustomModelCommand.__llm_model__ == "custom-model-v1"

    def test_custom_provider(self):
        """Should use custom provider"""
        mock_provider = MockProvider()

        class TestInputs(BaseModel):
            text: str

        class CustomProviderCommand(LlmBackedCommand[TestInputs, str]):
            __llm_provider__ = mock_provider

        assert CustomProviderCommand.__llm_provider__ is mock_provider


class TestLlmBackedCommandMessageBuilding:
    """Test message building in LlmBackedCommand"""

    def test_build_messages_default(self):
        """Should build default messages"""
        class TestInputs(BaseModel):
            text: str
            count: int = 1

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test command"

        mock_provider = MockProvider(response='"result"')
        TestCommand.__llm_provider__ = mock_provider

        cmd = TestCommand(text="hello", count=5)
        cmd._inputs = TestInputs(text="hello", count=5)
        cmd._construct_messages()

        assert len(cmd.messages) == 2
        assert cmd.messages[0].role == "system"
        assert cmd.messages[1].role == "user"
        assert "Test command" in cmd.messages[0].content
        assert "hello" in cmd.messages[1].content

    def test_build_messages_custom_override(self):
        """Should allow custom message building"""
        class TestInputs(BaseModel):
            text: str

        class CustomMessageCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

            def build_messages(self) -> List[LlmMessage]:
                return [
                    LlmMessage(role="system", content="Custom system prompt"),
                    LlmMessage(role="user", content=f"Process: {self.inputs.text}"),
                ]

        mock_provider = MockProvider(response='"result"')
        CustomMessageCommand.__llm_provider__ = mock_provider

        cmd = CustomMessageCommand(text="test")
        cmd._inputs = TestInputs(text="test")
        cmd._construct_messages()

        assert cmd.messages[0].content == "Custom system prompt"
        assert "Process: test" in cmd.messages[1].content


class TestLlmBackedCommandJsonParsing:
    """Test JSON parsing and error recovery"""

    def test_parse_valid_json(self):
        """Should parse valid JSON"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, int]):
            __description__ = "Test"

        mock_provider = MockProvider(response='42')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=10)
        assert outcome.is_success()
        assert outcome.unwrap() == 42

    def test_parse_json_with_whitespace(self):
        """Should handle JSON with extra whitespace"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='  \n  "result"  \n  ')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)
        assert outcome.is_success()
        assert outcome.unwrap() == "result"

    def test_parse_json_invalid(self):
        """Should raise error on invalid JSON"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='this is not json')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)
        assert outcome.is_failure()

    def test_parse_json_with_think_tags_recovery(self):
        """Should strip think tags before parsing"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, int]):
            __description__ = "Test"

        mock_provider = MockProvider(response='<THINK>analyzing...</THINK>42')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)
        assert outcome.is_success()
        assert outcome.unwrap() == 42

    def test_parse_json_with_code_fence_recovery(self):
        """Should extract from code fence"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, int]):
            __description__ = "Test"

        mock_provider = MockProvider(response='```json\n42\n```')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)
        assert outcome.is_success()
        assert outcome.unwrap() == 42

    def test_parse_json_wrapped_in_result(self):
        """Should unwrap {result: ...} wrapping"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='{"result": "unwrapped"}')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)
        assert outcome.is_success()
        assert outcome.unwrap() == "unwrapped"

    def test_parse_complex_result_not_unwrapped(self):
        """Should not unwrap complex objects with multiple keys"""
        class TestInputs(BaseModel):
            x: int

        class ResultModel(BaseModel):
            result: str
            metadata: str

        class TestCommand(LlmBackedCommand[TestInputs, ResultModel]):
            __description__ = "Test"

        mock_provider = MockProvider(
            response='{"result": "data", "metadata": "info"}'
        )
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["result"] == "data"
        assert result["metadata"] == "info"


class TestLlmBackedCommandSchemas:
    """Test JSON schema generation"""

    def test_simple_input_schema(self):
        """Should generate schema for simple inputs"""
        class SimpleInputs(BaseModel):
            name: str
            age: int

        class TestCommand(LlmBackedCommand[SimpleInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='"test"')
        TestCommand.__llm_provider__ = mock_provider

        cmd = TestCommand(name="John", age=30)
        cmd._inputs = SimpleInputs(name="John", age=30)
        schema = cmd._get_inputs_json_schema()

        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]

    def test_complex_input_schema(self):
        """Should handle complex input schemas"""
        class Address(BaseModel):
            street: str
            city: str

        class ComplexInputs(BaseModel):
            name: str
            addresses: List[Address]
            metadata: Dict[str, Any]

        class TestCommand(LlmBackedCommand[ComplexInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='"test"')
        TestCommand.__llm_provider__ = mock_provider

        cmd = TestCommand(
            name="Test",
            addresses=[{"street": "Main", "city": "NYC"}],
            metadata={"key": "value"}
        )
        cmd._inputs = ComplexInputs(
            name="Test",
            addresses=[Address(street="Main", city="NYC")],
            metadata={"key": "value"}
        )
        schema = cmd._get_inputs_json_schema()

        assert "properties" in schema
        assert "addresses" in schema["properties"]

    def test_result_schema_simple_type(self):
        """Should handle simple result types"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='"test"')
        TestCommand.__llm_provider__ = mock_provider

        cmd = TestCommand(x=1)
        cmd._inputs = TestInputs(x=1)
        schema = cmd._get_result_json_schema()

        assert schema["type"] == "string"

    def test_result_schema_model_type(self):
        """Should handle Pydantic model result types"""
        class TestInputs(BaseModel):
            x: int

        class ResultModel(BaseModel):
            output: str
            confidence: float

        class TestCommand(LlmBackedCommand[TestInputs, ResultModel]):
            __description__ = "Test"

        mock_provider = MockProvider(
            response='{"output": "test", "confidence": 0.95}'
        )
        TestCommand.__llm_provider__ = mock_provider

        cmd = TestCommand(x=1)
        cmd._inputs = TestInputs(x=1)
        schema = cmd._get_result_json_schema()

        assert "properties" in schema
        assert "output" in schema["properties"]
        assert "confidence" in schema["properties"]

    def test_python_type_to_json_type_all_types(self):
        """Should convert all Python types to JSON types"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        cmd = TestCommand(x=1)
        cmd._inputs = TestInputs(x=1)

        assert cmd._python_type_to_json_type(str) == "string"
        assert cmd._python_type_to_json_type(int) == "integer"
        assert cmd._python_type_to_json_type(float) == "number"
        assert cmd._python_type_to_json_type(bool) == "boolean"
        assert cmd._python_type_to_json_type(list) == "array"
        assert cmd._python_type_to_json_type(dict) == "object"

    def test_python_type_to_json_type_unknown(self):
        """Should default to string for unknown types"""
        class TestInputs(BaseModel):
            x: int

        class CustomType:
            pass

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        cmd = TestCommand(x=1)
        cmd._inputs = TestInputs(x=1)

        assert cmd._python_type_to_json_type(CustomType) == "string"


class TestAsyncLlmBackedCommand:
    """Test AsyncLlmBackedCommand"""

    @pytest.mark.asyncio
    async def test_async_execution(self):
        """Should execute asynchronously"""
        class TestInputs(BaseModel):
            text: str

        class AsyncTestCommand(AsyncLlmBackedCommand[TestInputs, str]):
            __description__ = "Async test"

        mock_provider = MockProvider(response='"async result"')
        AsyncTestCommand.__llm_provider__ = mock_provider

        outcome = await AsyncTestCommand.run(text="test")

        assert outcome.is_success()
        assert outcome.unwrap() == "async result"

    @pytest.mark.asyncio
    async def test_async_with_complex_result(self):
        """Should handle complex results asynchronously"""
        class TestInputs(BaseModel):
            x: int

        class ResultModel(BaseModel):
            value: int
            doubled: int

        class AsyncTestCommand(AsyncLlmBackedCommand[TestInputs, ResultModel]):
            __description__ = "Double a number"

        mock_provider = MockProvider(
            response='{"value": 5, "doubled": 10}'
        )
        AsyncTestCommand.__llm_provider__ = mock_provider

        outcome = await AsyncTestCommand.run(x=5)

        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["value"] == 5
        assert result["doubled"] == 10

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """Should handle errors in async execution"""
        class TestInputs(BaseModel):
            x: int

        class AsyncTestCommand(AsyncLlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='invalid json')
        AsyncTestCommand.__llm_provider__ = mock_provider

        outcome = await AsyncTestCommand.run(x=1)

        assert outcome.is_failure()

    @pytest.mark.asyncio
    async def test_async_custom_messages(self):
        """Should support custom message building in async"""
        class TestInputs(BaseModel):
            text: str

        class AsyncCustomCommand(AsyncLlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

            def build_messages(self) -> List[LlmMessage]:
                return [
                    LlmMessage(role="system", content="Custom async prompt"),
                    LlmMessage(role="user", content=self.inputs.text),
                ]

        mock_provider = MockProvider(response='"custom response"')
        AsyncCustomCommand.__llm_provider__ = mock_provider

        outcome = await AsyncCustomCommand.run(text="hello")

        assert outcome.is_success()
        assert mock_provider.calls[0]["messages"][0].content == "Custom async prompt"


class TestLlmBackedCommandErrorHandling:
    """Test error handling in LlmBackedCommand"""

    def test_llm_backed_command_error_attributes(self):
        """Should store raw and stripped answers in error"""
        error = LlmBackedCommandError(
            "Parse failed",
            raw_answer="<THINK>...</THINK>bad",
            stripped_answer="bad"
        )

        assert "Parse failed" in str(error)
        assert error.raw_answer == "<THINK>...</THINK>bad"
        assert error.stripped_answer == "bad"

    def test_llm_backed_command_error_minimal(self):
        """Should work with just message"""
        error = LlmBackedCommandError("Simple error")

        assert "Simple error" in str(error)
        assert error.raw_answer is None
        assert error.stripped_answer is None

    def test_json_decode_error_with_recovery_attempt(self):
        """Should try to extract JSON block before failing"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        # Valid JSON in a code block
        mock_provider = MockProvider(
            response='Here is the result:\n```json\n"extracted"\n```\nDone!'
        )
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)

        assert outcome.is_success()
        assert outcome.unwrap() == "extracted"

    def test_json_decode_error_no_recovery(self):
        """Should fail when no recovery possible"""
        class TestInputs(BaseModel):
            x: int

        class TestCommand(LlmBackedCommand[TestInputs, str]):
            __description__ = "Test"

        mock_provider = MockProvider(response='completely invalid {{{ json')
        TestCommand.__llm_provider__ = mock_provider

        outcome = TestCommand.run(x=1)

        assert outcome.is_failure()
