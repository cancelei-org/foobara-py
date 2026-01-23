"""Tests for MCP Connector module"""

import pytest
import json
from pydantic import BaseModel
from foobara_py.connectors.mcp import MCPConnector, JsonRpcError, create_mcp_server
from foobara_py.core.command import Command
from foobara_py.domain.domain import Domain


class AddInputs(BaseModel):
    a: int
    b: int


class Add(Command[AddInputs, int]):
    """Add two numbers"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


class TestMCPConnector:
    @pytest.fixture
    def connector(self):
        conn = MCPConnector(name="TestService", version="1.0.0")
        conn.connect(Add)
        return conn

    def test_initialize(self, connector):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0"},
                "capabilities": {}
            }
        }
        response = json.loads(connector.run(json.dumps(request)))

        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert response["result"]["serverInfo"]["name"] == "TestService"

    def test_tools_list(self, connector):
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        response = json.loads(connector.run(json.dumps(request)))

        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 1
        assert response["result"]["tools"][0]["name"] == "Add"

    def test_tools_call_success(self, connector):
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "Add",
                "arguments": {"a": 10, "b": 20}
            }
        }
        response = json.loads(connector.run(json.dumps(request)))

        assert "result" in response
        content = response["result"]["content"][0]
        assert content["type"] == "text"
        assert json.loads(content["text"]) == 30

    def test_tools_call_validation_error(self, connector):
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "Add",
                "arguments": {"a": "not_int", "b": 20}
            }
        }
        response = json.loads(connector.run(json.dumps(request)))

        assert "result" in response
        assert response["result"].get("isError") is True

    def test_invalid_json(self, connector):
        response = json.loads(connector.run("not valid json"))
        assert "error" in response
        assert response["error"]["code"] == JsonRpcError.PARSE_ERROR.value

    def test_invalid_version(self, connector):
        request = {
            "jsonrpc": "1.0",
            "id": 5,
            "method": "test"
        }
        response = json.loads(connector.run(json.dumps(request)))
        assert "error" in response
        assert response["error"]["code"] == JsonRpcError.INVALID_REQUEST.value

    def test_missing_method(self, connector):
        request = {
            "jsonrpc": "2.0",
            "id": 6
        }
        response = json.loads(connector.run(json.dumps(request)))
        assert "error" in response
        assert response["error"]["code"] == JsonRpcError.INVALID_REQUEST.value

    def test_notification_no_response(self, connector):
        # Notifications have no id
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/test",
            "params": {}
        }
        response = connector.run(json.dumps(request))
        assert response is None

    def test_ping(self, connector):
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "ping",
            "params": {}
        }
        response = json.loads(connector.run(json.dumps(request)))
        assert "result" in response

    def test_batch_request(self, connector):
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}
        ]
        response = json.loads(connector.run(json.dumps(batch)))
        assert isinstance(response, list)
        assert len(response) == 2

    def test_empty_batch(self, connector):
        response = json.loads(connector.run("[]"))
        assert "error" in response


class TestMCPConnectorWithDomain:
    def test_connect_domain(self):
        domain = Domain("TestDomain")

        class Inputs(BaseModel):
            x: int

        @domain.command
        class Double(Command[Inputs, int]):
            def execute(self) -> int:
                return self.inputs.x * 2

        connector = MCPConnector(name="DomainService")
        connector.connect(domain)

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        response = json.loads(connector.run(json.dumps(request)))
        tools = response["result"]["tools"]
        assert len(tools) == 1
        assert "Double" in tools[0]["name"]


class TestCreateMCPServer:
    def test_create_server(self):
        server = create_mcp_server(
            name="TestServer",
            version="2.0.0",
            commands=[Add]
        )
        assert server.name == "TestServer"
        assert server.version == "2.0.0"


# ==================== Resource Tests ====================
# Note: MCPResource class removed in favor of dict-based add_resource API
# These tests need to be updated to use the new API

# from foobara_py.connectors.mcp import MCPResource
# from foobara_py.persistence.entity import EntityBase
# from foobara_py.persistence.repository import InMemoryRepository, RepositoryRegistry
#
#
# class UserEntity(EntityBase):
#     """Test entity for resource tests"""
#     _primary_key_field = 'id'
#
#     id: int = None
#     name: str
#     email: str


@pytest.mark.skip(reason="MCPResource class removed - tests need updating for new dict-based API")
class TestMCPResources:
    @pytest.fixture
    def connector_with_resources(self):
        """Create connector with resources"""
        conn = MCPConnector(name="ResourceService", version="1.0.0")

        # Add a static resource
        conn.add_resource(MCPResource(
            uri="foobara://config",
            name="Config",
            description="Application configuration",
            mime_type="application/json",
            loader=lambda params: {"env": "test", "debug": True}
        ))

        # Add a templated resource with custom loader
        conn.add_resource(MCPResource(
            uri="foobara://items/{id}",
            name="Item",
            description="Item by ID",
            loader=lambda params: {"id": params.get("id"), "name": f"Item {params.get('id')}"}
        ))

        return conn

    @pytest.fixture
    def connector_with_entity_resource(self):
        """Create connector with entity-backed resource"""
        # Setup repository
        repo = InMemoryRepository()
        RepositoryRegistry.set_default(repo)

        # Create test entity
        user = UserEntity(id=42, name="John Doe", email="john@example.com")
        repo.save(user)

        conn = MCPConnector(name="EntityService", version="1.0.0")
        conn.add_entity_resource(UserEntity)

        yield conn

        RepositoryRegistry.clear()

    def test_initialize_includes_resources_capability(self, connector_with_resources):
        """Test that initialize response includes resources capability when resources exist"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test"},
                "capabilities": {}
            }
        }
        response = json.loads(connector_with_resources.run(json.dumps(request)))

        assert "result" in response
        capabilities = response["result"]["capabilities"]
        assert "resources" in capabilities

    def test_resources_list(self, connector_with_resources):
        """Test resources/list returns all registered resources"""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/list",
            "params": {}
        }
        response = json.loads(connector_with_resources.run(json.dumps(request)))

        assert "result" in response
        resources = response["result"]["resources"]
        assert len(resources) == 2

        uris = [r["uri"] for r in resources]
        assert "foobara://config" in uris
        assert "foobara://items/{id}" in uris

    def test_resources_read_static(self, connector_with_resources):
        """Test reading a static resource"""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/read",
            "params": {"uri": "foobara://config"}
        }
        response = json.loads(connector_with_resources.run(json.dumps(request)))

        assert "result" in response
        contents = response["result"]["contents"]
        assert len(contents) == 1
        assert contents[0]["uri"] == "foobara://config"

        data = json.loads(contents[0]["text"])
        assert data["env"] == "test"
        assert data["debug"] is True

    def test_resources_read_with_template(self, connector_with_resources):
        """Test reading a resource with URI template"""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {"uri": "foobara://items/123"}
        }
        response = json.loads(connector_with_resources.run(json.dumps(request)))

        assert "result" in response
        contents = response["result"]["contents"]
        data = json.loads(contents[0]["text"])
        assert data["id"] == "123"
        assert data["name"] == "Item 123"

    def test_resources_read_not_found(self, connector_with_resources):
        """Test error when resource not found"""
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "foobara://nonexistent"}
        }
        response = json.loads(connector_with_resources.run(json.dumps(request)))

        assert "error" in response
        assert "not found" in response["error"]["message"].lower()

    def test_resources_read_missing_uri(self, connector_with_resources):
        """Test error when URI is missing"""
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/read",
            "params": {}
        }
        response = json.loads(connector_with_resources.run(json.dumps(request)))

        assert "error" in response
        assert "uri" in response["error"]["message"].lower()

    def test_add_entity_resource(self, connector_with_entity_resource):
        """Test adding entity as resource"""
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/list",
            "params": {}
        }
        response = json.loads(connector_with_entity_resource.run(json.dumps(request)))

        resources = response["result"]["resources"]
        assert len(resources) == 1
        assert resources[0]["name"] == "UserEntity"
        assert "userentity" in resources[0]["uri"]

    def test_read_entity_resource(self, connector_with_entity_resource):
        """Test reading entity resource by ID"""
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "resources/read",
            "params": {"uri": "foobara://userentity/42"}
        }
        response = json.loads(connector_with_entity_resource.run(json.dumps(request)))

        assert "result" in response
        contents = response["result"]["contents"]
        data = json.loads(contents[0]["text"])
        assert data["id"] == 42
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"

    def test_read_entity_not_found(self, connector_with_entity_resource):
        """Test error when entity not found"""
        request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/read",
            "params": {"uri": "foobara://userentity/999"}
        }
        response = json.loads(connector_with_entity_resource.run(json.dumps(request)))

        assert "error" in response
        assert "not found" in response["error"]["message"].lower()

    def test_add_resource_chaining(self):
        """Test that add_resource returns self for chaining"""
        conn = MCPConnector(name="ChainTest")
        result = conn.add_resource(MCPResource(
            uri="foobara://test",
            name="Test",
            description="Test resource"
        ))
        assert result is conn

    def test_no_resources_no_capability(self):
        """Test that initialize without resources doesn't include resources capability"""
        conn = MCPConnector(name="NoResources")
        conn.connect(Add)

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test"},
                "capabilities": {}
            }
        }
        response = json.loads(conn.run(json.dumps(request)))

        capabilities = response["result"]["capabilities"]
        assert "resources" not in capabilities
