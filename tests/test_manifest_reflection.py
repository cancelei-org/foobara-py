"""
Tests for manifest and reflection system

Tests:
- Command.reflect() API
- DomainManifest type/entity counting
- MCP resource content reading
- MCP prompt template rendering
"""

import pytest
import json
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.domain.domain import Domain
from foobara_py.manifest.command_manifest import CommandManifest
from foobara_py.manifest.domain_manifest import DomainManifest
from foobara_py.connectors.mcp import MCPConnector


# Reset domain registry before each test
@pytest.fixture(autouse=True)
def reset_domains():
    """Reset domain registry before each test"""
    Domain._registry.clear()
    yield
    Domain._registry.clear()


class TestCommandReflect:
    """Test Command.reflect() API"""

    def test_reflect_returns_command_manifest(self):
        """Test that reflect() returns a CommandManifest object"""
        class TestInputs(BaseModel):
            name: str
            age: int = 18

        class TestResult(BaseModel):
            message: str

        class TestCommand(Command[TestInputs, TestResult]):
            """Test command for reflection"""
            _domain = "Testing"
            _organization = "TestOrg"

            def execute(self) -> TestResult:
                return TestResult(message=f"Hello {self.inputs.name}")

        # Call reflect()
        manifest = TestCommand.reflect()

        # Verify it's a CommandManifest
        assert isinstance(manifest, CommandManifest)
        assert manifest.name == "TestCommand"
        assert manifest.full_name == "TestOrg::Testing::TestCommand"
        assert manifest.description == "Test command for reflection"
        assert manifest.domain == "Testing"
        assert manifest.organization == "TestOrg"

    def test_reflect_includes_input_schema(self):
        """Test that reflect() includes JSON schema for inputs"""
        class UserInputs(BaseModel):
            email: str
            password: str

        class CreateUser(Command[UserInputs, dict]):
            def execute(self) -> dict:
                return {}

        manifest = CreateUser.reflect()

        assert manifest.inputs_schema is not None
        assert "properties" in manifest.inputs_schema
        assert "email" in manifest.inputs_schema["properties"]
        assert "password" in manifest.inputs_schema["properties"]

    def test_reflect_includes_result_schema(self):
        """Test that reflect() includes JSON schema for result"""
        class UserResult(BaseModel):
            id: int
            email: str

        class GetUser(Command[BaseModel, UserResult]):
            def execute(self) -> UserResult:
                return UserResult(id=1, email="test@example.com")

        manifest = GetUser.reflect()

        assert manifest.result_schema is not None
        assert "properties" in manifest.result_schema
        assert "id" in manifest.result_schema["properties"]
        assert "email" in manifest.result_schema["properties"]

    def test_reflect_detects_async_commands(self):
        """Test that reflect() correctly identifies async commands"""
        from foobara_py import AsyncCommand

        class AsyncTestCommand(AsyncCommand[BaseModel, str]):
            async def execute(self) -> str:
                return "async result"

        manifest = AsyncTestCommand.reflect()

        assert manifest.is_async is True

    def test_reflect_without_domain(self):
        """Test reflect() on command without explicit domain"""
        class GlobalCommand(Command[BaseModel, str]):
            """Global command"""
            def execute(self) -> str:
                return "global"

        manifest = GlobalCommand.reflect()

        assert manifest.name == "GlobalCommand"
        assert manifest.domain is None
        assert manifest.organization is None
        # Full name should just be the command name
        assert manifest.full_name == "GlobalCommand"


class TestDomainManifestCounting:
    """Test DomainManifest type and entity counting"""

    def test_count_types_in_domain(self):
        """Test that DomainManifest correctly counts types"""
        domain = Domain("TestDomain")

        # Register some types
        class UserType(BaseModel):
            name: str

        class ProductType(BaseModel):
            title: str

        domain.register_type("UserType", UserType)
        domain.register_type("ProductType", ProductType)

        # Create manifest
        manifest = DomainManifest.from_domain(domain)

        assert manifest.type_count == 2

    def test_count_entities_separately(self):
        """Test that entities are counted separately from types"""
        try:
            from foobara_py.persistence import Entity

            domain = Domain("TestDomain")

            # Register a regular type
            class ProductType(BaseModel):
                title: str

            domain.register_type("ProductType", ProductType)

            # Register an entity
            class User(Entity):
                __tablename__ = "users"
                name: str

            domain.register_type("User", User)

            # Create manifest
            manifest = DomainManifest.from_domain(domain)

            # Should count: 1 type, 1 entity
            assert manifest.type_count == 1
            assert manifest.entity_count == 1

        except ImportError:
            pytest.skip("Entity not available")

    def test_count_commands(self):
        """Test that commands are counted correctly"""
        domain = Domain("TestDomain")

        @domain.command
        class Command1(Command[BaseModel, str]):
            def execute(self) -> str:
                return "1"

        @domain.command
        class Command2(Command[BaseModel, str]):
            def execute(self) -> str:
                return "2"

        manifest = DomainManifest.from_domain(domain)

        assert manifest.command_count == 2
        assert "Command1" in manifest.command_names
        assert "Command2" in manifest.command_names

    def test_hierarchical_full_name(self):
        """Test that full_name includes organization"""
        domain = Domain("Users", organization="MyApp")

        manifest = DomainManifest.from_domain(domain)

        assert manifest.full_name == "MyApp::Users"
        assert manifest.name == "Users"
        assert manifest.organization == "MyApp"

    def test_full_name_without_organization(self):
        """Test full_name when no organization"""
        domain = Domain("Users")

        manifest = DomainManifest.from_domain(domain)

        assert manifest.full_name == "Users"
        assert manifest.name == "Users"
        assert manifest.organization is None


class TestMCPResourceContentReading:
    """Test MCP resource content reading"""

    def test_read_command_resource(self):
        """Test reading command:// resource"""
        class TestCommand(Command[BaseModel, str]):
            """Test command"""
            def execute(self) -> str:
                return "test"

        connector = MCPConnector()
        connector.connect(TestCommand)
        connector.add_resource(
            uri="command://TestCommand",
            name="TestCommand",
            description="Test command resource"
        )

        # Simulate resources/read request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": "command://TestCommand"}
        }

        response_str = connector.run(json.dumps(request))
        response = json.loads(response_str)

        assert "result" in response
        assert "contents" in response["result"]
        assert len(response["result"]["contents"]) > 0

        content = response["result"]["contents"][0]
        assert content["uri"] == "command://TestCommand"
        assert content["mimeType"] == "text/plain"

        # Parse the JSON content
        content_data = json.loads(content["text"])
        assert content_data["name"] == "TestCommand"

    def test_read_domain_resource(self):
        """Test reading domain:// resource"""
        domain = Domain("TestDomain")

        connector = MCPConnector()
        connector.add_resource(
            uri="domain://TestDomain",
            name="TestDomain",
            description="Test domain resource"
        )

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": "domain://TestDomain"}
        }

        response_str = connector.run(json.dumps(request))
        response = json.loads(response_str)

        assert "result" in response
        content = response["result"]["contents"][0]

        # Parse the JSON content
        content_data = json.loads(content["text"])
        assert content_data["name"] == "TestDomain"
        assert content_data["full_name"] == "TestDomain"

    def test_read_nonexistent_resource(self):
        """Test reading a resource that doesn't exist"""
        connector = MCPConnector()

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": "command://NonExistent"}
        }

        response_str = connector.run(json.dumps(request))
        response = json.loads(response_str)

        # Should return an error
        assert "error" in response


class TestMCPPromptRendering:
    """Test MCP prompt template rendering"""

    def test_command_help_prompt(self):
        """Test command_help built-in prompt"""
        class TestCommand(Command[BaseModel, str]):
            """Helpful test command"""
            _domain = "Testing"

            def execute(self) -> str:
                return "test"

        connector = MCPConnector()
        connector.connect(TestCommand)
        connector.add_prompt(
            name="command_help",
            description="Get help for a command",
            arguments=[{"name": "command_name", "required": True}]
        )

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "prompts/get",
            "params": {
                "name": "command_help",
                "arguments": {"command_name": "TestCommand"}
            }
        }

        response_str = connector.run(json.dumps(request))
        response = json.loads(response_str)

        assert "result" in response
        assert "messages" in response["result"]
        assert len(response["result"]["messages"]) > 0

        message = response["result"]["messages"][0]
        assert message["role"] == "user"
        assert "TestCommand" in message["content"]["text"]
        assert "Helpful test command" in message["content"]["text"]

    def test_domain_overview_prompt(self):
        """Test domain_overview built-in prompt"""
        domain = Domain("TestDomain")

        @domain.command
        class Cmd1(Command[BaseModel, str]):
            def execute(self) -> str:
                return "1"

        @domain.command
        class Cmd2(Command[BaseModel, str]):
            def execute(self) -> str:
                return "2"

        connector = MCPConnector()
        connector.add_prompt(
            name="domain_overview",
            description="Get domain overview",
            arguments=[{"name": "domain_name", "required": True}]
        )

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "prompts/get",
            "params": {
                "name": "domain_overview",
                "arguments": {"domain_name": "TestDomain"}
            }
        }

        response_str = connector.run(json.dumps(request))
        response = json.loads(response_str)

        assert "result" in response
        message = response["result"]["messages"][0]

        content_text = message["content"]["text"]
        assert "TestDomain" in content_text
        assert "Commands: 2" in content_text
        assert "Cmd1" in content_text
        assert "Cmd2" in content_text

    def test_custom_template_prompt(self):
        """Test custom prompt with template substitution"""
        connector = MCPConnector()
        connector._prompts["greet"] = {
            "name": "greet",
            "description": "Greeting template",
            "template": "Hello {name}, welcome to {place}!",
            "arguments": [
                {"name": "name", "required": True},
                {"name": "place", "required": True}
            ]
        }

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "prompts/get",
            "params": {
                "name": "greet",
                "arguments": {"name": "Alice", "place": "Wonderland"}
            }
        }

        response_str = connector.run(json.dumps(request))
        response = json.loads(response_str)

        message = response["result"]["messages"][0]
        assert message["content"]["text"] == "Hello Alice, welcome to Wonderland!"
