"""Tests for JSON Schema and OpenAPI generation."""

import json

import pytest
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.core.registry import CommandRegistry
from foobara_py.generators.json_schema_generator import (
    JsonSchemaGenerator,
    OpenAPIConfig,
    OpenAPIGenerator,
    OpenAPIInfo,
    OpenAPIServer,
    generate_json_schema,
    generate_openapi_json,
    generate_openapi_spec,
    generate_openapi_yaml,
    python_type_to_json_schema,
)


# Test models
class UserInputs(BaseModel):
    """User creation inputs."""

    name: str
    email: str
    age: int


class UserResult(BaseModel):
    """User result."""

    id: int
    name: str
    email: str


class CreateUser(Command[UserInputs, UserResult]):
    """Create a new user."""

    Inputs = UserInputs
    Result = UserResult

    def execute(self) -> UserResult:
        return UserResult(id=1, name=self.inputs.name, email=self.inputs.email)


class SimpleCommand(Command):
    """A simple command without typed inputs/outputs."""

    def execute(self):
        return {"status": "ok"}


class TestPythonTypeToJsonSchema:
    """Tests for python_type_to_json_schema function."""

    def test_string_type(self):
        schema = python_type_to_json_schema(str)
        assert schema == {"type": "string"}

    def test_int_type(self):
        schema = python_type_to_json_schema(int)
        assert schema == {"type": "integer"}

    def test_float_type(self):
        schema = python_type_to_json_schema(float)
        assert schema == {"type": "number"}

    def test_bool_type(self):
        schema = python_type_to_json_schema(bool)
        assert schema == {"type": "boolean"}

    def test_list_type(self):
        schema = python_type_to_json_schema(list)
        assert schema == {"type": "array"}

    def test_dict_type(self):
        schema = python_type_to_json_schema(dict)
        assert schema == {"type": "object"}

    def test_none_type(self):
        schema = python_type_to_json_schema(None)
        assert schema == {"type": "null"}

    def test_string_type_name(self):
        schema = python_type_to_json_schema("str")
        assert schema == {"type": "string"}

    def test_pydantic_model(self):
        schema = python_type_to_json_schema(UserInputs)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "name" in schema["properties"]


class TestJsonSchemaGenerator:
    """Tests for JsonSchemaGenerator class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return CommandRegistry()

    @pytest.fixture
    def generator(self, registry):
        """Create a generator instance."""
        registry.register(CreateUser)
        return JsonSchemaGenerator(registry)

    def test_generate_command_input_schema(self, generator):
        schema = generator.generate_command_input_schema(CreateUser)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "email" in schema["properties"]
        assert "age" in schema["properties"]

    def test_generate_command_output_schema(self, generator):
        schema = generator.generate_command_output_schema(CreateUser)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "id" in schema["properties"]
        assert "name" in schema["properties"]

    def test_generate_command_error_schema(self, generator):
        schema = generator.generate_command_error_schema(CreateUser)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "key" in schema["properties"]
        assert "message" in schema["properties"]
        assert "category" in schema["properties"]

    def test_generate_command_schema(self, generator):
        schema = generator.generate_command_schema(CreateUser)
        assert schema["title"] == "CreateUser"
        assert "description" in schema
        assert "properties" in schema
        assert "inputs" in schema["properties"]
        assert "result" in schema["properties"]
        assert "errors" in schema["properties"]

    def test_generate_all_schemas(self, generator):
        schemas = generator.generate_all_schemas()
        assert "CreateUser" in schemas
        assert schemas["CreateUser"]["title"] == "CreateUser"

    def test_simple_command_schema(self, registry):
        registry.register(SimpleCommand)
        generator = JsonSchemaGenerator(registry)
        schema = generator.generate_command_schema(SimpleCommand)
        assert schema["title"] == "SimpleCommand"


class TestOpenAPIConfig:
    """Tests for OpenAPI configuration."""

    def test_default_config(self):
        config = OpenAPIConfig()
        assert config.info.title == "Foobara API"
        assert config.info.version == "1.0.0"
        assert len(config.servers) == 1

    def test_custom_config(self):
        config = OpenAPIConfig(
            info=OpenAPIInfo(
                title="My API",
                version="2.0.0",
                description="My custom API"
            ),
            servers=[
                OpenAPIServer(url="https://api.example.com", description="Production"),
                OpenAPIServer(url="http://localhost:3000", description="Development"),
            ]
        )
        assert config.info.title == "My API"
        assert config.info.version == "2.0.0"
        assert len(config.servers) == 2


class TestOpenAPIGenerator:
    """Tests for OpenAPIGenerator class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return CommandRegistry()

    @pytest.fixture
    def generator(self, registry):
        """Create an OpenAPI generator instance."""
        registry.register(CreateUser)
        return OpenAPIGenerator(registry)

    def test_command_to_path(self, generator):
        path = generator._command_to_path("CreateUser")
        assert path == "/commands/create-user"

    def test_command_to_path_with_namespace(self, generator):
        path = generator._command_to_path("Users::CreateUser")
        assert path == "/commands/users/create-user"

    def test_command_to_operation_id(self, generator):
        op_id = generator._command_to_operation_id("Users::CreateUser")
        assert op_id == "Users_CreateUser"

    def test_generate_path_item(self, generator):
        path_item = generator.generate_path_item(CreateUser)
        assert "post" in path_item
        assert path_item["post"]["operationId"] == "CreateUser"
        assert "requestBody" in path_item["post"]
        assert "responses" in path_item["post"]
        assert "200" in path_item["post"]["responses"]
        assert "400" in path_item["post"]["responses"]

    def test_generate_components(self, generator):
        components = generator.generate_components()
        assert "schemas" in components
        assert "AuthError" in components["schemas"]
        assert "ServerError" in components["schemas"]
        assert "securitySchemes" in components
        assert "bearerAuth" in components["securitySchemes"]

    def test_generate_spec(self, generator):
        spec = generator.generate_spec()
        assert spec["openapi"] == "3.0.3"
        assert "info" in spec
        assert spec["info"]["title"] == "Foobara API"
        assert "paths" in spec
        assert "/commands/create-user" in spec["paths"]
        assert "components" in spec

    def test_generate_spec_with_custom_config(self, registry):
        config = OpenAPIConfig(
            info=OpenAPIInfo(title="Custom API", version="3.0.0"),
            servers=[OpenAPIServer(url="https://api.example.com")]
        )
        registry.register(CreateUser)
        generator = OpenAPIGenerator(registry, config)
        spec = generator.generate_spec()
        assert spec["info"]["title"] == "Custom API"
        assert spec["info"]["version"] == "3.0.0"
        assert spec["servers"][0]["url"] == "https://api.example.com"

    def test_generate_spec_with_specific_commands(self, registry):
        registry.register(CreateUser)
        registry.register(SimpleCommand)
        generator = OpenAPIGenerator(registry)
        spec = generator.generate_spec([CreateUser])
        assert "/commands/create-user" in spec["paths"]
        assert "/commands/simple-command" not in spec["paths"]

    def test_generate_yaml(self, generator):
        yaml_str = generator.generate_yaml()
        assert "openapi: 3.0.3" in yaml_str
        assert "Foobara API" in yaml_str
        assert "/commands/create-user" in yaml_str

    def test_generate_json(self, generator):
        json_str = generator.generate_json()
        spec = json.loads(json_str)
        assert spec["openapi"] == "3.0.3"
        assert "/commands/create-user" in spec["paths"]


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        reg = CommandRegistry()
        reg.register(CreateUser)
        return reg

    def test_generate_json_schema(self, registry):
        schema = generate_json_schema(CreateUser, registry)
        assert schema["title"] == "CreateUser"
        assert "properties" in schema

    def test_generate_openapi_spec(self, registry):
        spec = generate_openapi_spec([CreateUser], registry=registry)
        assert spec["openapi"] == "3.0.3"
        assert "/commands/create-user" in spec["paths"]

    def test_generate_openapi_yaml(self, registry):
        yaml_str = generate_openapi_yaml([CreateUser], registry=registry)
        assert "openapi: 3.0.3" in yaml_str

    def test_generate_openapi_json(self, registry):
        json_str = generate_openapi_json([CreateUser], registry=registry)
        spec = json.loads(json_str)
        assert spec["openapi"] == "3.0.3"

    def test_generate_openapi_json_with_indent(self, registry):
        json_str = generate_openapi_json([CreateUser], registry=registry, indent=4)
        # Check indentation (4 spaces)
        assert "    " in json_str


class TestOpenAPISecuritySchemes:
    """Tests for security scheme configuration."""

    def test_custom_security_schemes(self):
        config = OpenAPIConfig(
            security_schemes={
                "oauth2": {
                    "type": "oauth2",
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "https://example.com/oauth/authorize",
                            "tokenUrl": "https://example.com/oauth/token",
                            "scopes": {
                                "read": "Read access",
                                "write": "Write access"
                            }
                        }
                    }
                }
            }
        )
        registry = CommandRegistry()
        registry.register(CreateUser)
        generator = OpenAPIGenerator(registry, config)
        components = generator.generate_components()
        assert "oauth2" in components["securitySchemes"]

    def test_default_security(self):
        config = OpenAPIConfig(
            default_security=[{"bearerAuth": []}]
        )
        registry = CommandRegistry()
        registry.register(CreateUser)
        generator = OpenAPIGenerator(registry, config)
        spec = generator.generate_spec()
        assert "security" in spec
        assert spec["security"] == [{"bearerAuth": []}]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_registry(self):
        registry = CommandRegistry()
        generator = OpenAPIGenerator(registry)
        spec = generator.generate_spec()
        assert spec["paths"] == {}

    def test_command_without_docstring(self):
        class NoDocCommand(Command):
            def execute(self):
                return None

        registry = CommandRegistry()
        registry.register(NoDocCommand)
        generator = OpenAPIGenerator(registry)
        path_item = generator.generate_path_item(NoDocCommand)
        assert path_item["post"]["description"] == ""

    def test_nested_pydantic_models(self):
        class Address(BaseModel):
            street: str
            city: str

        class UserWithAddress(BaseModel):
            name: str
            address: Address

        class CreateUserWithAddress(Command[UserWithAddress, UserResult]):
            Inputs = UserWithAddress

            def execute(self):
                return UserResult(id=1, name="test", email="test@example.com")

        registry = CommandRegistry()
        registry.register(CreateUserWithAddress)
        generator = JsonSchemaGenerator(registry)
        schema = generator.generate_command_input_schema(CreateUserWithAddress)
        assert "address" in schema["properties"]
