"""Tests for TypeScript SDK Generator."""

import tempfile
from pathlib import Path
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field

from foobara_py import Command
from foobara_py.core.registry import CommandRegistry
from foobara_py.generators.typescript_sdk_generator import (
    TypeScriptSDKConfig,
    TypeScriptSDKGenerator,
    generate_typescript_client,
    generate_typescript_sdk,
    generate_typescript_types,
    python_type_to_typescript,
)


# Test models
class AddressModel(BaseModel):
    """Address information."""

    street: str = Field(description="Street address")
    city: str = Field(description="City name")
    country: str = "USA"


class UserInputs(BaseModel):
    """User creation inputs."""

    name: str = Field(description="User's full name")
    email: str = Field(description="Email address")
    age: int = Field(description="Age in years")
    tags: Optional[List[str]] = None
    address: Optional[AddressModel] = None


class UserResult(BaseModel):
    """User result."""

    id: int
    name: str
    email: str
    created_at: str


class CreateUser(Command[UserInputs, UserResult]):
    """Create a new user in the system."""

    Inputs = UserInputs
    Result = UserResult

    def execute(self) -> UserResult:
        return UserResult(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            created_at="2024-01-01T00:00:00Z",
        )


class GetUserInputs(BaseModel):
    """Get user inputs."""

    id: int


class GetUser(Command[GetUserInputs, UserResult]):
    """Get a user by ID."""

    Inputs = GetUserInputs
    Result = UserResult

    def execute(self) -> UserResult:
        return UserResult(
            id=self.inputs.id,
            name="Test",
            email="test@example.com",
            created_at="2024-01-01T00:00:00Z",
        )


class SimpleCommand(Command):
    """A simple command."""

    def execute(self):
        return {"status": "ok"}


class TestPythonTypeToTypescript:
    """Tests for python_type_to_typescript function."""

    def test_string_type(self):
        assert python_type_to_typescript(str, nullable=False) == "string"

    def test_int_type(self):
        assert python_type_to_typescript(int, nullable=False) == "number"

    def test_float_type(self):
        assert python_type_to_typescript(float, nullable=False) == "number"

    def test_bool_type(self):
        assert python_type_to_typescript(bool, nullable=False) == "boolean"

    def test_list_type(self):
        assert python_type_to_typescript(list, nullable=False) == "any[]"

    def test_dict_type(self):
        assert python_type_to_typescript(dict, nullable=False) == "Record<string, any>"

    def test_string_type_name(self):
        assert python_type_to_typescript("str", nullable=False) == "string"
        assert python_type_to_typescript("int", nullable=False) == "number"

    def test_nullable_type(self):
        # String type with nullable=True but no Optional wrapper just returns string
        result = python_type_to_typescript(str, nullable=True, use_strict_null=True)
        assert result == "string"  # Base types don't get null suffix automatically

    def test_without_strict_null(self):
        result = python_type_to_typescript(str, nullable=True, use_strict_null=False)
        assert result == "string"


class TestTypeScriptSDKConfig:
    """Tests for TypeScript SDK configuration."""

    def test_default_config(self):
        config = TypeScriptSDKConfig()
        assert config.output_dir == "./generated"
        assert config.base_url == "http://localhost:8000"
        assert config.use_interfaces is True
        assert config.include_jsdoc is True

    def test_custom_config(self):
        config = TypeScriptSDKConfig(
            output_dir="./dist",
            base_url="https://api.example.com",
            single_file=True,
            include_axios_client=True,
        )
        assert config.output_dir == "./dist"
        assert config.base_url == "https://api.example.com"
        assert config.single_file is True


class TestTypeScriptSDKGenerator:
    """Tests for TypeScript SDK generator."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry."""
        reg = CommandRegistry()
        reg.register(CreateUser)
        reg.register(GetUser)
        return reg

    @pytest.fixture
    def generator(self, registry):
        """Create a generator instance."""
        return TypeScriptSDKGenerator(registry)

    def test_to_camel_case(self, generator):
        assert generator._to_camel_case("CreateUser") == "createUser"
        assert generator._to_camel_case("get_user_by_id") == "getUserById"

    def test_to_pascal_case(self, generator):
        assert generator._to_pascal_case("create_user") == "CreateUser"
        assert generator._to_pascal_case("get-user") == "GetUser"

    def test_generate_jsdoc(self, generator):
        jsdoc = generator._generate_jsdoc("Test description")
        assert "/**" in jsdoc
        assert "Test description" in jsdoc
        assert "*/" in jsdoc

    def test_generate_jsdoc_with_params(self, generator):
        jsdoc = generator._generate_jsdoc("Description", {"name": "User name"})
        assert "@param name" in jsdoc

    def test_generate_interface_from_model(self, generator):
        interface = generator._generate_interface_from_model(UserInputs)
        assert "interface UserInputs" in interface
        assert "name" in interface
        assert "email" in interface
        assert "string" in interface

    def test_generate_interface_with_optional_fields(self, generator):
        interface = generator._generate_interface_from_model(UserInputs)
        assert "tags?" in interface  # Optional field

    def test_generate_command_types(self, generator):
        types = generator._generate_command_types(CreateUser)
        assert "CreateUserInput" in types
        assert "CreateUserResult" in types

    def test_generate_error_types(self, generator):
        error_types = generator._generate_error_types()
        assert "FoobaraError" in error_types
        assert "FoobaraOutcome" in error_types
        assert "FoobaraApiError" in error_types

    def test_generate_fetch_client(self, generator):
        client = generator._generate_fetch_client()
        assert "FoobaraClient" in client
        assert "fetch" in client
        assert "baseUrl" in client

    def test_generate_command_method(self, generator):
        method = generator._generate_command_method(CreateUser)
        assert "createUser" in method
        assert "CreateUserInput" in method
        assert "CreateUserResult" in method
        assert "async" in method


class TestGenerateTypesFile:
    """Tests for types file generation."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(CreateUser)
        return reg

    def test_generate_types_file(self, registry):
        generator = TypeScriptSDKGenerator(registry)
        types_file = generator.generate_types_file()

        assert "// Auto-generated" in types_file
        assert "FoobaraError" in types_file
        assert "CreateUserInput" in types_file
        assert "CreateUserResult" in types_file

    def test_generate_types_with_specific_commands(self, registry):
        registry.register(GetUser)
        generator = TypeScriptSDKGenerator(registry)
        types_file = generator.generate_types_file([CreateUser])

        assert "CreateUserInput" in types_file
        assert "GetUserInput" not in types_file


class TestGenerateClientFile:
    """Tests for client file generation."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(CreateUser)
        reg.register(GetUser)
        return reg

    def test_generate_client_file(self, registry):
        generator = TypeScriptSDKGenerator(registry)
        client_file = generator.generate_client_file()

        assert "// Auto-generated" in client_file
        assert "import type" in client_file
        assert "FoobaraClient" in client_file
        assert "createUser" in client_file
        assert "getUser" in client_file

    def test_generate_client_with_custom_base_url(self, registry):
        config = TypeScriptSDKConfig(base_url="https://api.example.com")
        generator = TypeScriptSDKGenerator(registry, config)
        client_file = generator.generate_client_file()

        assert "https://api.example.com" in client_file


class TestGenerateSDK:
    """Tests for full SDK generation."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(CreateUser)
        return reg

    def test_generate_sdk_multiple_files(self, registry):
        generator = TypeScriptSDKGenerator(registry)
        files = generator.generate_sdk()

        assert "types.ts" in files
        assert "client.ts" in files
        assert "index.ts" in files

    def test_generate_sdk_single_file(self, registry):
        config = TypeScriptSDKConfig(single_file=True)
        generator = TypeScriptSDKGenerator(registry, config)
        files = generator.generate_sdk()

        assert len(files) == 1
        assert "foobara.ts" in files

    def test_generate_sdk_without_index(self, registry):
        config = TypeScriptSDKConfig(include_index=False)
        generator = TypeScriptSDKGenerator(registry, config)
        files = generator.generate_sdk()

        assert "index.ts" not in files

    def test_write_sdk(self, registry):
        generator = TypeScriptSDKGenerator(registry)

        with tempfile.TemporaryDirectory() as tmpdir:
            written_files = generator.write_sdk(output_dir=tmpdir)

            assert len(written_files) >= 2
            for file_path in written_files:
                assert file_path.exists()
                assert file_path.read_text()


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(CreateUser)
        return reg

    def test_generate_typescript_sdk(self, registry):
        files = generate_typescript_sdk(registry)
        assert "types.ts" in files
        assert "client.ts" in files

    def test_generate_typescript_types(self, registry):
        types = generate_typescript_types(registry)
        assert "FoobaraError" in types
        assert "CreateUserInput" in types

    def test_generate_typescript_client(self, registry):
        client = generate_typescript_client(registry)
        assert "FoobaraClient" in client
        assert "createUser" in client


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_registry(self):
        registry = CommandRegistry()
        generator = TypeScriptSDKGenerator(registry)

        types_file = generator.generate_types_file()
        assert "FoobaraError" in types_file  # Should still have error types

    def test_command_without_typed_inputs(self):
        registry = CommandRegistry()
        registry.register(SimpleCommand)
        generator = TypeScriptSDKGenerator(registry)

        types_file = generator.generate_types_file()
        # Should not crash, should still generate error types
        assert "FoobaraError" in types_file

    def test_no_jsdoc(self):
        config = TypeScriptSDKConfig(include_jsdoc=False)
        registry = CommandRegistry()
        registry.register(CreateUser)
        generator = TypeScriptSDKGenerator(registry, config)

        # Generate interface (not full types file which includes error types with JSDoc)
        interface = generator._generate_interface_from_model(UserInputs, "TestModel")
        # User-defined interfaces should not have jsdoc for field descriptions
        assert interface.count("/**") <= 1  # May have description at top but not for fields

    def test_type_aliases_instead_of_interfaces(self):
        config = TypeScriptSDKConfig(use_interfaces=False)
        registry = CommandRegistry()
        registry.register(CreateUser)
        generator = TypeScriptSDKGenerator(registry, config)

        types_file = generator.generate_types_file()
        assert "export type CreateUserInput =" in types_file


class TestComplexTypes:
    """Tests for complex type conversions."""

    def test_list_of_strings(self):
        from typing import List

        result = python_type_to_typescript(List[str], nullable=False)
        assert "string[]" in result

    def test_optional_type(self):
        from typing import Optional

        result = python_type_to_typescript(Optional[str], nullable=True)
        assert "string" in result
        assert "null" in result

    def test_dict_with_types(self):
        from typing import Dict

        result = python_type_to_typescript(Dict[str, int], nullable=False)
        assert "Record<string, number>" in result


class TestIndexFileGeneration:
    """Tests for index file generation."""

    def test_generate_index_file(self):
        registry = CommandRegistry()
        generator = TypeScriptSDKGenerator(registry)

        index_file = generator.generate_index_file()
        assert "export * from './types'" in index_file
        assert "export * from './client'" in index_file
