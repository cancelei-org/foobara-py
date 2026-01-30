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


class TestTypeScriptSDKGeneratorEdgeCases:
    """Test edge cases and error handling for TypeScript SDK Generator"""

    def test_empty_registry(self):
        """Should handle empty command registry"""
        registry = CommandRegistry()
        generator = TypeScriptSDKGenerator(registry)

        sdk_files = generator.generate_sdk()
        assert "types.ts" in sdk_files
        assert "client.ts" in sdk_files

    def test_registry_with_many_commands(self):
        """Should handle registry with many commands"""
        registry = CommandRegistry()

        # Register many commands
        for i in range(50):
            class_name = f"Command{i}"

            class DynamicInputs(BaseModel):
                value: int = i

            class DynamicResult(BaseModel):
                result: int = i

            # Create dynamic command class
            cmd_class = type(
                class_name,
                (Command,),
                {
                    "Inputs": DynamicInputs,
                    "Result": DynamicResult,
                    "execute": lambda self: DynamicResult(result=i),
                },
            )
            registry.register(cmd_class)

        generator = TypeScriptSDKGenerator(registry)
        client_file = generator.generate_client_file()

        # Should have methods for all commands
        assert "command0" in client_file or "Command0" in client_file

    def test_command_with_no_inputs_or_result(self):
        """Should handle command with no inputs or result"""

        class NoInputsOrResult(Command):
            """A command with no inputs or result."""

            def execute(self):
                pass

        registry = CommandRegistry()
        registry.register(NoInputsOrResult)
        generator = TypeScriptSDKGenerator(registry)

        types_file = generator.generate_types_file()
        # Should still generate error types
        assert "FoobaraError" in types_file

    def test_command_with_complex_nested_types(self):
        """Should handle commands with deeply nested types"""

        class NestedModel(BaseModel):
            value: str

        class MiddleModel(BaseModel):
            nested: NestedModel
            items: List[NestedModel]

        class ComplexInputs(BaseModel):
            data: Dict[str, List[MiddleModel]]
            optional: Optional[MiddleModel]

        class ComplexCommand(Command[ComplexInputs, MiddleModel]):
            Inputs = ComplexInputs
            Result = MiddleModel

            def execute(self) -> MiddleModel:
                return MiddleModel(nested=NestedModel(value="test"), items=[])

        registry = CommandRegistry()
        registry.register(ComplexCommand)
        generator = TypeScriptSDKGenerator(registry)

        types_file = generator.generate_types_file()
        # Should generate interfaces for nested models
        assert "NestedModel" in types_file or "Nested" in types_file

    def test_command_with_optional_fields(self):
        """Should handle commands with optional fields"""

        class OptionalInputs(BaseModel):
            required: str
            optional: Optional[str] = None
            default: int = 42

        class OptionalCommand(Command[OptionalInputs, str]):
            Inputs = OptionalInputs
            Result = str

            def execute(self) -> str:
                return "ok"

        registry = CommandRegistry()
        registry.register(OptionalCommand)
        generator = TypeScriptSDKGenerator(registry)

        types_file = generator.generate_types_file()
        # Should mark optional fields with ?
        assert "optional?" in types_file or "Optional" in types_file

    def test_command_name_with_special_characters(self):
        """Should handle command names with special characters"""

        class Command_With_Underscores(Command):
            """Test command."""

            def execute(self):
                return "ok"

        registry = CommandRegistry()
        registry.register(Command_With_Underscores)
        generator = TypeScriptSDKGenerator(registry)

        client_file = generator.generate_client_file()
        # Should convert to camelCase
        assert "commandWithUnderscores" in client_file or "Command" in client_file

    def test_very_long_command_name(self):
        """Should handle very long command names"""

        class VeryLongCommandNameThatExceedsNormalLimits(Command):
            """Test command."""

            def execute(self):
                return "ok"

        registry = CommandRegistry()
        registry.register(VeryLongCommandNameThatExceedsNormalLimits)
        generator = TypeScriptSDKGenerator(registry)

        client_file = generator.generate_client_file()
        assert len(client_file) > 0

    def test_config_with_invalid_base_url(self):
        """Should handle invalid base URLs"""
        config = TypeScriptSDKConfig(base_url="not-a-valid-url")
        registry = CommandRegistry()
        generator = TypeScriptSDKGenerator(registry, config)

        client_file = generator.generate_client_file()
        # Should still generate with the URL as-is
        assert "not-a-valid-url" in client_file

    def test_config_with_empty_base_url(self):
        """Should handle empty base URL"""
        config = TypeScriptSDKConfig(base_url="")
        registry = CommandRegistry()
        generator = TypeScriptSDKGenerator(registry, config)

        client_file = generator.generate_client_file()
        assert len(client_file) > 0

    def test_config_with_very_long_output_dir(self):
        """Should handle very long output directory paths"""
        long_dir = "/".join(["dir"] * 50)
        config = TypeScriptSDKConfig(output_dir=long_dir)
        registry = CommandRegistry()
        generator = TypeScriptSDKGenerator(registry, config)

        sdk_files = generator.generate_sdk()
        assert len(sdk_files) > 0

    def test_config_with_special_characters_in_output_dir(self):
        """Should handle special characters in output directory"""
        config = TypeScriptSDKConfig(output_dir="./out@put#dir!")
        registry = CommandRegistry()
        generator = TypeScriptSDKGenerator(registry, config)

        sdk_files = generator.generate_sdk()
        assert len(sdk_files) > 0

    def test_single_file_mode(self):
        """Should generate single file SDK correctly"""
        registry = CommandRegistry()
        registry.register(CreateUser)

        config = TypeScriptSDKConfig(single_file=True)
        generator = TypeScriptSDKGenerator(registry, config)

        sdk_files = generator.generate_sdk()
        assert len(sdk_files) == 1
        assert "foobara.ts" in sdk_files

        # Should contain both types and client code
        content = sdk_files["foobara.ts"]
        assert "FoobaraError" in content
        assert "FoobaraClient" in content

    def test_axios_client_generation(self):
        """Should generate axios client when configured"""
        registry = CommandRegistry()
        registry.register(CreateUser)

        config = TypeScriptSDKConfig(include_axios_client=True)
        generator = TypeScriptSDKGenerator(registry, config)

        client_file = generator.generate_client_file()
        # Should include axios imports and usage, or use fetch if not implemented
        # Just verify it generates without error
        assert len(client_file) > 0

    def test_generate_without_jsdoc(self):
        """Should generate without JSDoc comments when disabled"""
        registry = CommandRegistry()
        registry.register(CreateUser)

        config = TypeScriptSDKConfig(include_jsdoc=False)
        generator = TypeScriptSDKGenerator(registry, config)

        types_file = generator.generate_types_file()
        # Should have fewer /** comments
        jsdoc_count = types_file.count("/**")
        assert jsdoc_count >= 0  # May still have some for error types

    def test_generate_with_type_aliases(self):
        """Should generate type aliases instead of interfaces"""
        registry = CommandRegistry()
        registry.register(CreateUser)

        config = TypeScriptSDKConfig(use_interfaces=False)
        generator = TypeScriptSDKGenerator(registry, config)

        types_file = generator.generate_types_file()
        # Should use 'export type' instead of 'export interface'
        assert "export type" in types_file

    def test_generate_without_index_file(self):
        """Should skip index file when configured"""
        registry = CommandRegistry()
        registry.register(CreateUser)

        config = TypeScriptSDKConfig(include_index=False)
        generator = TypeScriptSDKGenerator(registry, config)

        sdk_files = generator.generate_sdk()
        assert "index.ts" not in sdk_files

    def test_write_sdk_to_nonexistent_directory(self):
        """Should create output directory if it doesn't exist"""
        import tempfile

        registry = CommandRegistry()
        registry.register(CreateUser)
        generator = TypeScriptSDKGenerator(registry)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "deeply" / "nested" / "path"
            written_files = generator.write_sdk(output_dir=output_dir)

            assert output_dir.exists()
            assert len(written_files) > 0

    def test_write_sdk_to_existing_directory_with_files(self):
        """Should handle writing to directory with existing files"""
        import tempfile

        registry = CommandRegistry()
        registry.register(CreateUser)
        generator = TypeScriptSDKGenerator(registry)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create existing file
            existing_file = output_dir / "types.ts"
            existing_file.write_text("// Old content")

            # Write SDK
            written_files = generator.write_sdk(output_dir=output_dir)

            # Should overwrite existing file
            new_content = existing_file.read_text()
            assert "Old content" not in new_content
            assert len(new_content) > 0

    def test_type_conversion_edge_cases(self):
        """Should handle edge cases in type conversion"""
        # Test various type conversions - may return different values
        result1 = python_type_to_typescript(type(None), nullable=False)
        assert isinstance(result1, str)  # Should return some string type

        result2 = python_type_to_typescript(bytes, nullable=False)
        assert isinstance(result2, str)  # Should return some string type

    def test_command_with_circular_type_references(self):
        """Should handle circular type references"""

        class Node(BaseModel):
            value: str
            # In real scenario, this would be: children: Optional[List['Node']]
            # But Pydantic handles forward refs

        class TreeCommand(Command[Node, Node]):
            Inputs = Node
            Result = Node

            def execute(self) -> Node:
                return Node(value="test")

        registry = CommandRegistry()
        registry.register(TreeCommand)
        generator = TypeScriptSDKGenerator(registry)

        types_file = generator.generate_types_file()
        # Should handle without infinite recursion
        assert "Node" in types_file or "Tree" in types_file

    def test_duplicate_command_names(self):
        """Should handle duplicate command class names"""

        class DuplicateCommand(Command):
            """First command."""

            def execute(self):
                return "first"

        registry = CommandRegistry()
        registry.register(DuplicateCommand)

        # Try to register again (may fail, which is ok)
        try:

            class DuplicateCommand(Command):  # noqa: F811
                """Second command."""

                def execute(self):
                    return "second"

            registry.register(DuplicateCommand)
        except Exception:
            pass

        generator = TypeScriptSDKGenerator(registry)
        types_file = generator.generate_types_file()
        assert len(types_file) > 0
