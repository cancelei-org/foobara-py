#!/usr/bin/env python3
"""
MCP Server Example

Demonstrates how to expose foobara-py commands as MCP tools
for AI assistants like Claude.
"""

from pydantic import BaseModel, Field
from foobara_py import Command, Domain, MCPConnector


# Define domains
math = Domain("Math")
text = Domain("Text")


# Math commands
class AddInputs(BaseModel):
    a: float = Field(..., description="First number")
    b: float = Field(..., description="Second number")


@math.command
class Add(Command[AddInputs, float]):
    """Add two numbers together"""

    def execute(self) -> float:
        return self.inputs.a + self.inputs.b


class MultiplyInputs(BaseModel):
    a: float = Field(..., description="First number")
    b: float = Field(..., description="Second number")


@math.command
class Multiply(Command[MultiplyInputs, float]):
    """Multiply two numbers"""

    def execute(self) -> float:
        return self.inputs.a * self.inputs.b


# Text commands
class ReverseTextInputs(BaseModel):
    text: str = Field(..., description="Text to reverse")


@text.command
class ReverseText(Command[ReverseTextInputs, str]):
    """Reverse the characters in a string"""

    def execute(self) -> str:
        return self.inputs.text[::-1]


class WordCountInputs(BaseModel):
    text: str = Field(..., description="Text to count words in")


class WordCountResult(BaseModel):
    word_count: int
    char_count: int
    line_count: int


@text.command
class WordCount(Command[WordCountInputs, WordCountResult]):
    """Count words, characters, and lines in text"""

    def execute(self) -> WordCountResult:
        return WordCountResult(
            word_count=len(self.inputs.text.split()),
            char_count=len(self.inputs.text),
            line_count=len(self.inputs.text.splitlines()) or 1
        )


def create_server():
    """Create and configure the MCP server"""
    connector = MCPConnector(
        name="foobara-example",
        version="1.0.0",
        instructions="A demo MCP server with math and text utilities."
    )

    # Connect all commands from both domains
    connector.connect(math)
    connector.connect(text)

    return connector


if __name__ == "__main__":
    import sys

    server = create_server()

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode: run a sample request
        import json

        # Test tools/list
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        response = json.loads(server.run(json.dumps(request)))
        print("Available tools:")
        for tool in response["result"]["tools"]:
            print(f"  - {tool['name']}: {tool['description']}")

        # Test tools/call
        print("\nTesting Add(5, 3):")
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "Math::Add",
                "arguments": {"a": 5, "b": 3}
            }
        }
        response = json.loads(server.run(json.dumps(request)))
        result = json.loads(response["result"]["content"][0]["text"])
        print(f"  Result: {result}")

        print("\nTesting WordCount('Hello World'):")
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "Text::WordCount",
                "arguments": {"text": "Hello World"}
            }
        }
        response = json.loads(server.run(json.dumps(request)))
        result = json.loads(response["result"]["content"][0]["text"])
        print(f"  Result: {result}")

    else:
        # Production mode: run stdio server
        print("Starting MCP server on stdio...", file=sys.stderr)
        print("Configure in Claude Desktop:", file=sys.stderr)
        print('''
{
  "mcpServers": {
    "foobara-example": {
      "type": "stdio",
      "command": "python",
      "args": ["examples/mcp_server.py"]
    }
  }
}
''', file=sys.stderr)
        server.run_stdio()
