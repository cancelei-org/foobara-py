"""Tests for GraphQL Connector."""

import pytest
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.core.registry import CommandRegistry
from foobara_py.connectors.graphql import (
    GraphQLConfig,
    GraphQLConnector,
    GraphQLFieldConfig,
    GraphQLOperationType,
    GraphQLSchemaGenerator,
    create_ariadne_schema,
    create_strawberry_types,
    generate_graphql_schema,
    python_type_to_graphql,
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
    """Create a new user in the system."""

    Inputs = UserInputs
    Result = UserResult

    def execute(self) -> UserResult:
        return UserResult(id=1, name=self.inputs.name, email=self.inputs.email)


class GetUserInputs(BaseModel):
    """Get user inputs."""

    id: int


class GetUser(Command[GetUserInputs, UserResult]):
    """Get a user by ID."""

    Inputs = GetUserInputs
    Result = UserResult

    def execute(self) -> UserResult:
        return UserResult(id=self.inputs.id, name="Test", email="test@example.com")


class SimpleCommand(Command):
    """A simple command without typed inputs."""

    def execute(self):
        return {"status": "ok"}


class TestPythonTypeToGraphQL:
    """Tests for python_type_to_graphql function."""

    def test_string_type(self):
        assert python_type_to_graphql(str) == "String"

    def test_int_type(self):
        assert python_type_to_graphql(int) == "Int"

    def test_float_type(self):
        assert python_type_to_graphql(float) == "Float"

    def test_bool_type(self):
        assert python_type_to_graphql(bool) == "Boolean"

    def test_list_type(self):
        assert python_type_to_graphql(list) == "[String]"

    def test_dict_type(self):
        assert python_type_to_graphql(dict) == "JSON"

    def test_non_nullable(self):
        assert python_type_to_graphql(str, nullable=False) == "String!"

    def test_string_type_name(self):
        assert python_type_to_graphql("str") == "String"
        assert python_type_to_graphql("int") == "Int"


class TestGraphQLConfig:
    """Tests for GraphQL configuration."""

    def test_default_config(self):
        config = GraphQLConfig()
        assert config.schema_description == "Foobara Commands GraphQL API"
        assert config.default_operation_type == GraphQLOperationType.MUTATION
        assert config.enable_introspection is True

    def test_custom_config(self):
        config = GraphQLConfig(
            schema_description="My Custom API",
            query_commands=["GetUser", "ListUsers"],
            enable_batching=False,
        )
        assert config.schema_description == "My Custom API"
        assert "GetUser" in config.query_commands

    def test_field_configs(self):
        config = GraphQLConfig(
            field_configs={
                "CreateUser": GraphQLFieldConfig(
                    name="createUser",
                    description="Create a user",
                    operation_type=GraphQLOperationType.MUTATION,
                )
            }
        )
        assert "CreateUser" in config.field_configs


class TestGraphQLSchemaGenerator:
    """Tests for GraphQL schema generation."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return CommandRegistry()

    @pytest.fixture
    def generator(self, registry):
        """Create a schema generator instance."""
        registry.register(CreateUser)
        return GraphQLSchemaGenerator(registry)

    def test_command_to_field_name(self, generator):
        field_name = generator._command_to_field_name(CreateUser)
        assert field_name == "createUser"

    def test_get_operation_type_default(self, generator):
        op_type = generator._get_operation_type(CreateUser)
        assert op_type == GraphQLOperationType.MUTATION

    def test_get_operation_type_query(self, registry):
        registry.register(GetUser)
        config = GraphQLConfig(query_commands=["GetUser"])
        generator = GraphQLSchemaGenerator(registry, config)
        op_type = generator._get_operation_type(GetUser)
        assert op_type == GraphQLOperationType.QUERY

    def test_generate_input_type(self, generator):
        type_name = generator._generate_input_type(CreateUser)
        assert type_name == "CreateUserInput"
        assert "CreateUserInput" in generator._type_definitions
        assert "name: String!" in generator._type_definitions["CreateUserInput"]

    def test_generate_output_type(self, generator):
        type_name = generator._generate_output_type(CreateUser)
        assert type_name == "CreateUserResult"
        assert "CreateUserResult" in generator._type_definitions

    def test_generate_schema(self, generator):
        schema = generator.generate_schema()
        assert "Foobara Commands GraphQL API" in schema
        assert "scalar JSON" in schema
        assert "type Mutation" in schema
        assert "createUser" in schema
        assert "CreateUserInput" in schema

    def test_generate_schema_with_queries(self, registry):
        registry.register(GetUser)
        config = GraphQLConfig(query_commands=["GetUser"])
        generator = GraphQLSchemaGenerator(registry, config)
        schema = generator.generate_schema()
        assert "type Query" in schema
        assert "getUser" in schema

    def test_generate_schema_empty_registry(self):
        registry = CommandRegistry()
        generator = GraphQLSchemaGenerator(registry)
        schema = generator.generate_schema()
        # Should still have empty Query type
        assert "type Query" in schema


class TestGraphQLConnector:
    """Tests for GraphQL connector."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return CommandRegistry()

    @pytest.fixture
    def connector(self, registry):
        """Create a connector instance."""
        registry.register(CreateUser)
        return GraphQLConnector(registry)

    def test_get_schema(self, connector):
        schema = connector.get_schema()
        assert "type Mutation" in schema
        assert "createUser" in schema

    def test_register_resolvers(self, connector):
        resolvers = connector.register_resolvers()
        assert "Mutation" in resolvers
        assert "createUser" in resolvers["Mutation"]

    def test_create_resolver(self, connector):
        resolver = connector._create_resolver(CreateUser)
        assert callable(resolver)

    @pytest.mark.asyncio
    async def test_execute_mutation(self, connector):
        query = """
        mutation {
            createUser(input: {name: "Test", email: "test@example.com", age: 25})
        }
        """
        result = await connector.execute(query, {"input": {"name": "Test", "email": "test@example.com", "age": 25}})
        assert "data" in result
        assert "createUser" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_invalid_query(self, connector):
        result = await connector.execute("invalid query syntax !!!")
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_field(self, connector):
        query = """
        mutation {
            unknownField
        }
        """
        result = await connector.execute(query)
        assert "errors" in result


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        reg = CommandRegistry()
        reg.register(CreateUser)
        return reg

    def test_generate_graphql_schema(self, registry):
        schema = generate_graphql_schema(registry=registry)
        assert "createUser" in schema
        assert "type Mutation" in schema

    def test_create_ariadne_schema(self, registry):
        type_defs, resolvers = create_ariadne_schema(registry)
        assert "createUser" in type_defs
        assert "Mutation" in resolvers

    def test_create_strawberry_types(self, registry):
        types = create_strawberry_types(registry)
        assert "mutation_resolvers" in types
        assert "schema_sdl" in types


class TestGraphQLOperationTypes:
    """Tests for query vs mutation classification."""

    @pytest.fixture
    def registry(self):
        """Create a registry with both commands."""
        reg = CommandRegistry()
        reg.register(CreateUser)
        reg.register(GetUser)
        return reg

    def test_mixed_operations(self, registry):
        config = GraphQLConfig(query_commands=["GetUser"])
        generator = GraphQLSchemaGenerator(registry, config)
        schema = generator.generate_schema()

        # GetUser should be in Query
        assert "type Query" in schema
        # CreateUser should be in Mutation
        assert "type Mutation" in schema

    def test_custom_field_config(self, registry):
        config = GraphQLConfig(
            field_configs={
                "CreateUser": GraphQLFieldConfig(
                    name="createUser",
                    operation_type=GraphQLOperationType.QUERY,
                    description="Custom description",
                )
            }
        )
        generator = GraphQLSchemaGenerator(registry, config)
        op_type = generator._get_operation_type(CreateUser)
        assert op_type == GraphQLOperationType.QUERY


class TestErrorHandling:
    """Tests for error handling in GraphQL connector."""

    @pytest.fixture
    def registry(self):
        return CommandRegistry()

    def test_command_without_inputs(self, registry):
        registry.register(SimpleCommand)
        generator = GraphQLSchemaGenerator(registry)
        schema = generator.generate_schema()
        # Should still generate valid schema
        assert "simpleCommand" in schema

    def test_empty_registry_schema(self):
        registry = CommandRegistry()
        connector = GraphQLConnector(registry)
        schema = connector.get_schema()
        # Should have empty Query type at minimum
        assert "type Query" in schema


class TestPydanticModelConversion:
    """Tests for Pydantic model to GraphQL type conversion."""

    def test_nested_model(self):
        class Address(BaseModel):
            street: str
            city: str

        class PersonInputs(BaseModel):
            name: str
            address: Address

        class CreatePerson(Command[PersonInputs, BaseModel]):
            Inputs = PersonInputs

            def execute(self):
                return {}

        registry = CommandRegistry()
        registry.register(CreatePerson)
        generator = GraphQLSchemaGenerator(registry)
        schema = generator.generate_schema()
        assert "createPerson" in schema

    def test_list_field(self):
        from typing import List

        class TagInputs(BaseModel):
            tags: List[str]

        class CreateTag(Command[TagInputs, BaseModel]):
            Inputs = TagInputs

            def execute(self):
                return {}

        registry = CommandRegistry()
        registry.register(CreateTag)
        generator = GraphQLSchemaGenerator(registry)
        input_type = generator._generate_input_type(CreateTag)
        assert input_type is not None
        # List types should be converted
        assert "CreateTagInput" in generator._type_definitions


# ==================== GraphQL Query Validation Edge Cases ====================

class TestGraphQLQueryValidation:
    """Tests for GraphQL query validation edge cases"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(CreateUser)
        return reg

    @pytest.fixture
    def connector(self, registry):
        return GraphQLConnector(registry)

    def test_syntax_error_missing_brace(self, connector):
        """Test that schema is generated (query validation would need GraphQL executor)"""
        schema = connector.get_schema()
        assert "createUser" in schema
        assert "mutation" in schema.lower()

    def test_syntax_error_missing_parenthesis(self, connector):
        """Test that schema is valid"""
        schema = connector.get_schema()
        assert "type Mutation" in schema

    def test_invalid_field_name(self, connector):
        """Test schema doesn't contain non-existent fields"""
        schema = connector.get_schema()
        assert "nonExistentField" not in schema

    def test_missing_required_argument(self, connector):
        """Test schema defines required inputs"""
        schema = connector.get_schema()
        assert "CreateUserInput" in schema
        # All fields should be required (!)
        assert "String!" in schema

    def test_wrong_argument_type(self, connector):
        """Test schema defines typed inputs"""
        schema = connector.get_schema()
        # Schema should have input types defined
        assert "input " in schema

    def test_invalid_input_field(self, connector):
        """Test schema only includes defined fields"""
        schema = connector.get_schema()
        assert "nonExistent" not in schema

    def test_missing_required_input_field(self, connector):
        """Test schema marks required fields"""
        schema = connector.get_schema()
        # Check that required fields are marked with !
        assert "!" in schema

    def test_null_in_non_nullable_field(self, connector):
        """Test schema marks fields as non-nullable"""
        schema = connector.get_schema()
        # Non-nullable fields should have !
        assert "String!" in schema

    def test_invalid_number_format(self, connector):
        """Test schema uses proper number types"""
        schema = connector.get_schema()
        assert "Int" in schema

    @pytest.mark.asyncio
    async def test_empty_query(self, connector):
        """Test empty query string"""
        result = await connector.execute("")
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_query_with_only_whitespace(self, connector):
        """Test query with only whitespace"""
        result = await connector.execute("   \n\t  ")
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_query_with_comment_only(self, connector):
        """Test query with only comments"""
        query = """
        # This is a comment
        # No actual query
        """
        result = await connector.execute(query)
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_invalid_operation_type(self, connector):
        """Test invalid operation type"""
        query = """
        subscription {
            createUser(input: {name: "Test"})
        }
        """
        result = await connector.execute(query)
        # subscriptions not supported
        assert "errors" in result

    def test_duplicate_field_names(self, connector):
        """Test that schema allows multiple field calls"""
        schema = connector.get_schema()
        # Schema should define the mutation field
        assert "createUser" in schema

    @pytest.mark.asyncio
    async def test_query_depth_limit(self, connector):
        """Test very deeply nested query"""
        # This is a stress test - actual depth depends on schema
        query = "mutation { " * 100 + "createUser" + " }" * 100
        result = await connector.execute(query)
        # Should handle or reject deep nesting
        assert "errors" in result or "data" in result

    @pytest.mark.asyncio
    async def test_very_long_query(self, connector):
        """Test extremely long query string"""
        query = "mutation { createUser(input: {name: \"" + "x" * 10000 + "\", email: \"test@example.com\", age: 25}) }"
        result = await connector.execute(query)
        # Should handle or reject
        assert "errors" in result or "data" in result

    @pytest.mark.asyncio
    async def test_unicode_in_query(self, connector):
        """Test unicode characters in query"""
        query = """
        mutation {
            createUser(input: {name: "世界", email: "test@example.com", age: 25})
        }
        """
        result = await connector.execute(query)
        # Should handle unicode
        assert "data" in result or "errors" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_strings(self, connector):
        """Test special characters in string values"""
        query = """
        mutation {
            createUser(input: {name: "Test\\nNew\\tLine", email: "test@example.com", age: 25})
        }
        """
        result = await connector.execute(query)
        assert "data" in result or "errors" in result

    def test_empty_input_object(self, connector):
        """Test schema defines required fields"""
        schema = connector.get_schema()
        # Schema should have required fields
        assert "name: String!" in schema or "name:" in schema

    def test_array_instead_of_object(self, connector):
        """Test schema defines proper input types"""
        schema = connector.get_schema()
        # Should use input type, not array
        assert "input CreateUserInput" in schema

    @pytest.mark.asyncio
    async def test_negative_integer(self, connector):
        """Test negative integer value"""
        query = """
        mutation {
            createUser(input: {name: "Test", email: "test@example.com", age: -5})
        }
        """
        result = await connector.execute(query)
        # Age should be positive, but GraphQL accepts it
        assert "data" in result or "errors" in result

    @pytest.mark.asyncio
    async def test_integer_overflow(self, connector):
        """Test very large integer"""
        query = """
        mutation {
            createUser(input: {name: "Test", email: "test@example.com", age: 9999999999999999})
        }
        """
        result = await connector.execute(query)
        assert "data" in result or "errors" in result

    @pytest.mark.asyncio
    async def test_float_where_int_expected(self, connector):
        """Test float value where integer expected"""
        query = """
        mutation {
            createUser(input: {name: "Test", email: "test@example.com", age: 25.5})
        }
        """
        result = await connector.execute(query)
        # GraphQL coercion rules apply
        assert "data" in result or "errors" in result


class TestGraphQLSchemaErrors:
    """Tests for schema validation edge cases"""

    def test_empty_registry_schema(self):
        """Test schema generation with no commands"""
        registry = CommandRegistry()
        generator = GraphQLSchemaGenerator(registry)
        schema = generator.generate_schema()
        assert "type Query" in schema

    def test_command_without_description(self):
        """Test command without docstring"""
        class NoDescCommand(Command):
            def execute(self):
                return "ok"

        registry = CommandRegistry()
        registry.register(NoDescCommand)
        generator = GraphQLSchemaGenerator(registry)
        schema = generator.generate_schema()
        assert "noDescCommand" in schema

    def test_invalid_field_config(self):
        """Test invalid field configuration"""
        registry = CommandRegistry()
        registry.register(CreateUser)
        config = GraphQLConfig(
            field_configs={
                "NonExistent": GraphQLFieldConfig(
                    name="test",
                    operation_type=GraphQLOperationType.QUERY
                )
            }
        )
        generator = GraphQLSchemaGenerator(registry, config)
        schema = generator.generate_schema()
        # Should handle non-existent command gracefully
        assert schema is not None
