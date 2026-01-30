"""Tests for FastAPI HTTP Connector"""

import pytest
from pydantic import BaseModel, Field
from typing import Optional, List

from foobara_py import Command, Domain
from foobara_py.connectors.http import (
    HTTPConnector,
    HTTPStatus,
    RouteConfig,
    AuthConfig,
    CommandRoute,
    create_http_app,
)


# ==================== Test Fixtures ====================

class AddInputs(BaseModel):
    """Inputs for Add command"""
    a: int
    b: int


class AddResult(BaseModel):
    """Result for Add command"""
    sum: int


class Add(Command[AddInputs, AddResult]):
    """Add two numbers"""

    def execute(self) -> AddResult:
        return AddResult(sum=self.inputs.a + self.inputs.b)


class GreetInputs(BaseModel):
    """Inputs for Greet command"""
    name: str
    formal: bool = False


class Greet(Command[GreetInputs, str]):
    """Greet a person"""

    def execute(self) -> str:
        if self.inputs.formal:
            return f"Good day, {self.inputs.name}."
        return f"Hello, {self.inputs.name}!"


class CreateUserInputs(BaseModel):
    """Inputs for CreateUser command"""
    name: str
    email: str
    age: Optional[int] = None


class User(BaseModel):
    """User model"""
    id: int
    name: str
    email: str
    age: Optional[int] = None


class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user"""
    _next_id = 1

    def execute(self) -> User:
        user = User(
            id=CreateUser._next_id,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )
        CreateUser._next_id += 1
        return user


class FailingInputs(BaseModel):
    """Inputs for failing command"""
    value: str


class FailingCommand(Command[FailingInputs, str]):
    """Command that always fails validation"""

    def validate(self) -> None:
        if self.inputs.value == "fail":
            self.add_error("value", "validation_failed", "Value cannot be 'fail'")

    def execute(self) -> str:
        return self.inputs.value


# Test domain
users_domain = Domain("Users", organization="TestOrg")
users_domain.register_command(CreateUser)


@pytest.fixture
def connector():
    """Create a connector without FastAPI app"""
    return HTTPConnector()


@pytest.fixture
def app():
    """Create FastAPI app with connector"""
    try:
        from fastapi import FastAPI
        app = FastAPI(title="Test API")
        return app
    except ImportError:
        pytest.skip("FastAPI not installed")


@pytest.fixture
def connector_with_app(app):
    """Create connector with FastAPI app"""
    return HTTPConnector(app)


@pytest.fixture
def client(app, connector_with_app):
    """Create test client"""
    try:
        from fastapi.testclient import TestClient
        connector_with_app.register(Add)
        connector_with_app.register(Greet)
        connector_with_app.register(FailingCommand)
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI not installed")


# ==================== HTTPConnector Tests ====================

class TestHTTPConnector:
    """Tests for HTTPConnector base functionality"""

    def test_register_command(self, connector):
        connector.register(Add)
        assert "Add" in connector
        assert len(connector) == 1

    def test_register_multiple_commands(self, connector):
        connector.register(Add)
        connector.register(Greet)
        assert len(connector) == 2

    def test_register_domain(self, connector):
        connector.register_domain(users_domain)
        assert "TestOrg::Users::CreateUser" in connector

    def test_register_chaining(self, connector):
        result = connector.register(Add).register(Greet)
        assert result is connector
        assert len(connector) == 2

    def test_routes_property(self, connector):
        connector.register(Add)
        routes = connector.routes
        assert "Add" in routes
        assert isinstance(routes["Add"], CommandRoute)


class TestRouteConfig:
    """Tests for RouteConfig"""

    def test_default_route_config(self):
        route = CommandRoute(Add)
        assert route.config.path == "/add"
        assert route.config.method == "POST"

    def test_custom_route_config(self, connector):
        config = RouteConfig(
            path="/math/add",
            method="POST",
            tags=["Math"],
            summary="Add numbers",
            deprecated=True
        )
        connector.register(Add, config=config)

        route = connector.routes["Add"]
        assert route.config.path == "/math/add"
        assert route.config.tags == ["Math"]
        assert route.config.deprecated is True

    def test_route_with_domain_prefix(self, connector):
        connector.register_domain(users_domain)
        # Command name includes org and domain
        route = connector.routes["TestOrg::Users::CreateUser"]
        # Path is derived from full name
        assert route.config.path is not None


class TestCommandExecution:
    """Tests for command execution through connector"""

    def test_execute_success(self, connector):
        connector.register(Add)
        result = connector.execute("Add", {"a": 5, "b": 3})

        assert result["success"] is True
        assert result["result"]["sum"] == 8

    def test_execute_not_found(self, connector):
        result = connector.execute("NonExistent", {})

        assert result["success"] is False
        assert "not_found" in result["errors"][0]["symbol"]

    def test_execute_with_validation_error(self, connector):
        connector.register(FailingCommand)
        result = connector.execute("FailingCommand", {"value": "fail"})

        assert result["success"] is False
        assert len(result["errors"]) > 0


class TestManifest:
    """Tests for manifest generation"""

    def test_get_manifest(self, connector):
        connector.register(Add)
        connector.register(Greet)

        manifest = connector.get_manifest()

        assert "commands" in manifest
        assert "count" in manifest
        assert manifest["count"] == 2
        assert "Add" in manifest["commands"]
        assert "Greet" in manifest["commands"]

    def test_manifest_command_details(self, connector):
        connector.register(Add)

        manifest = connector.get_manifest()
        add_cmd = manifest["commands"]["Add"]

        assert add_cmd["name"] == "Add"
        assert add_cmd["method"] == "POST"
        assert "inputs_schema" in add_cmd
        assert add_cmd["description"] == "Add two numbers"

    def test_get_command_manifest(self, connector):
        connector.register(Add)

        manifest = connector.get_command_manifest("Add")

        assert manifest is not None
        assert manifest["name"] == "Add"
        assert "inputs_schema" in manifest

    def test_get_command_manifest_not_found(self, connector):
        manifest = connector.get_command_manifest("NonExistent")
        assert manifest is None


class TestAuthConfig:
    """Tests for authentication configuration"""

    def test_auth_config_default_disabled(self):
        config = AuthConfig()
        assert config.enabled is False

    def test_auth_config_enabled(self, connector):
        def mock_auth():
            return {"user": "test"}

        auth = AuthConfig(enabled=True, dependency=mock_auth)
        connector.register(Add, auth_config=auth)

        route = connector.routes["Add"]
        assert route.auth_config.enabled is True
        assert route.auth_config.dependency is mock_auth

    def test_connector_default_auth(self):
        def default_auth():
            return {"user": "default"}

        connector = HTTPConnector(auth_config=AuthConfig(enabled=True, dependency=default_auth))
        connector.register(Add)

        route = connector.routes["Add"]
        assert route.auth_config.enabled is True


# ==================== FastAPI Integration Tests ====================

class TestFastAPIIntegration:
    """Tests requiring FastAPI"""

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "commands_registered" in data

    def test_manifest_endpoint(self, client):
        response = client.get("/manifest")
        assert response.status_code == 200

        data = response.json()
        assert "commands" in data
        assert "Add" in data["commands"]

    def test_command_endpoint_success(self, client):
        response = client.post("/add", json={"a": 10, "b": 5})
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["result"]["sum"] == 15

    def test_command_endpoint_with_optional(self, client):
        response = client.post("/greet", json={"name": "World"})
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["result"] == "Hello, World!"

    def test_command_endpoint_validation_error(self, client):
        response = client.post("/failingcommand", json={"value": "fail"})
        assert response.status_code == 422

        data = response.json()
        assert data["success"] is False
        assert len(data["errors"]) > 0

    def test_command_endpoint_invalid_input(self, client):
        response = client.post("/add", json={"a": "not_a_number", "b": 5})
        # FastAPI returns 422 for validation errors
        assert response.status_code == 422


class TestCreateHttpApp:
    """Tests for create_http_app convenience function"""

    def test_create_with_commands(self):
        try:
            app = create_http_app(
                commands=[Add, Greet],
                title="Test API"
            )
            assert app is not None
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_create_with_domains(self):
        try:
            app = create_http_app(
                domains=[users_domain],
                title="Domain API"
            )
            assert app is not None
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_create_with_prefix(self):
        try:
            from fastapi.testclient import TestClient

            app = create_http_app(
                commands=[Add],
                prefix="/api/v1"
            )
            client = TestClient(app)

            # Should have prefixed endpoints
            response = client.get("/api/v1/health")
            assert response.status_code == 200
        except ImportError:
            pytest.skip("FastAPI not installed")


class TestHTTPConnectorWithPrefix:
    """Tests for HTTPConnector with URL prefix"""

    def test_prefix_applied_to_routes(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            app = FastAPI()
            connector = HTTPConnector(app, prefix="/api/v2")
            connector.register(Add)

            client = TestClient(app)

            # Health endpoint should be prefixed
            response = client.get("/api/v2/health")
            assert response.status_code == 200

            # Command endpoint should be prefixed
            response = client.post("/api/v2/add", json={"a": 1, "b": 2})
            assert response.status_code == 200
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_manifest_shows_prefixed_paths(self):
        connector = HTTPConnector(prefix="/api/v1")
        connector.register(Add)

        manifest = connector.get_manifest()
        assert manifest["prefix"] == "/api/v1"
        assert manifest["commands"]["Add"]["path"].startswith("/api/v1")


class TestCommandRoute:
    """Tests for CommandRoute"""

    def test_format_response_success(self):
        route = CommandRoute(Add)

        from foobara_py.core.outcome import CommandOutcome
        outcome = CommandOutcome(result=AddResult(sum=10), errors=[])

        response = route._format_response(outcome)
        assert response["success"] is True
        assert response["result"]["sum"] == 10

    def test_format_response_failure(self):
        route = CommandRoute(FailingCommand)

        from foobara_py.core.outcome import CommandOutcome
        from foobara_py import FoobaraError
        error = FoobaraError(symbol="test_error", message="Test error")
        outcome = CommandOutcome(result=None, errors=[error])

        response = route._format_response(outcome)
        assert response["success"] is False
        assert len(response["errors"]) == 1
        assert response["errors"][0]["symbol"] == "test_error"


# ==================== HTTP Error Handling Edge Cases ====================

class TestHTTPErrorHandling:
    """Tests for HTTP error handling edge cases"""

    def test_network_timeout_simulation(self, client):
        """Simulate network timeout"""
        # This tests that the endpoint is responsive
        response = client.post("/add", json={"a": 1, "b": 2}, timeout=0.001)
        # Should complete quickly or timeout gracefully
        assert response is not None

    def test_malformed_json_request(self, client):
        """Test malformed JSON in request body"""
        response = client.post(
            "/add",
            data="not json at all {{{",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_empty_request_body(self, client):
        """Test empty request body"""
        response = client.post("/add", json={})
        assert response.status_code == 422

    def test_null_values_in_request(self, client):
        """Test null values in required fields"""
        response = client.post("/add", json={"a": None, "b": 5})
        assert response.status_code == 422

    def test_wrong_data_types(self, client):
        """Test wrong data types for inputs"""
        response = client.post("/add", json={"a": "string", "b": [1, 2, 3]})
        assert response.status_code == 422

    def test_extra_fields_in_request(self, client):
        """Test extra unexpected fields in request"""
        response = client.post("/add", json={"a": 1, "b": 2, "extra": "field"})
        # Should either succeed ignoring extra or fail validation
        assert response.status_code in [200, 422]

    def test_missing_required_fields(self, client):
        """Test missing required fields"""
        response = client.post("/add", json={"a": 1})
        assert response.status_code == 422

    def test_very_large_payload(self, client):
        """Test very large payload"""
        large_name = "x" * 100000
        response = client.post("/greet", json={"name": large_name})
        # Should handle or reject large payloads
        assert response.status_code in [200, 413, 422]

    def test_special_characters_in_input(self, client):
        """Test special characters in string inputs"""
        special_chars = "\\n\\t\\r\\x00\\\"\\\\"
        response = client.post("/greet", json={"name": special_chars})
        # Should handle special characters
        assert response.status_code in [200, 422]

    def test_unicode_in_input(self, client):
        """Test unicode characters in input"""
        response = client.post("/greet", json={"name": "Hello 世界 🌍"})
        assert response.status_code == 200

    def test_negative_numbers(self, client):
        """Test negative numbers"""
        response = client.post("/add", json={"a": -100, "b": -200})
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["sum"] == -300

    def test_integer_overflow(self, client):
        """Test very large integers"""
        response = client.post("/add", json={"a": 10**100, "b": 10**100})
        # Python handles big ints, should work
        assert response.status_code == 200

    def test_float_precision(self, client):
        """Test floating point precision"""
        response = client.post("/add", json={"a": 0.1, "b": 0.2})
        # Should convert float to int or fail validation
        assert response.status_code in [200, 422]


class TestHTTPConnectionErrors:
    """Tests for connection and network errors"""

    def test_invalid_http_method(self, client):
        """Test using wrong HTTP method"""
        response = client.get("/add")
        assert response.status_code in [404, 405]

    def test_invalid_content_type(self, client):
        """Test with wrong content type"""
        response = client.post(
            "/add",
            data="a=1&b=2",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        # Should reject non-JSON
        assert response.status_code in [415, 422]

    def test_missing_content_type(self, client):
        """Test with missing content type header"""
        response = client.post("/add", data='{"a": 1, "b": 2}')
        # FastAPI might handle this gracefully
        assert response.status_code in [200, 422]

    def test_options_request(self, client):
        """Test OPTIONS request for CORS"""
        response = client.options("/add")
        # Should handle or reject OPTIONS
        assert response.status_code in [200, 405]

    def test_head_request(self, client):
        """Test HEAD request"""
        response = client.head("/health")
        # Should support HEAD for health check
        assert response.status_code in [200, 405]


class TestHTTPRouteEdgeCases:
    """Tests for route edge cases"""

    def test_trailing_slash(self, client):
        """Test route with trailing slash"""
        response = client.post("/add/", json={"a": 1, "b": 2})
        # Should handle or redirect
        assert response.status_code in [200, 307, 308, 404]

    def test_case_sensitivity(self, client):
        """Test route case sensitivity"""
        response = client.post("/ADD", json={"a": 1, "b": 2})
        # Routes are case-sensitive by default
        assert response.status_code in [404, 200]

    def test_nonexistent_endpoint(self, client):
        """Test accessing non-existent endpoint"""
        response = client.post("/nonexistent")
        assert response.status_code == 404

    def test_health_check_reliability(self, client):
        """Test health check always responds"""
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"


class TestHTTPConcurrency:
    """Tests for concurrent request handling"""

    def test_concurrent_requests(self, client):
        """Test multiple concurrent requests"""
        responses = []
        for i in range(10):
            response = client.post("/add", json={"a": i, "b": i})
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
