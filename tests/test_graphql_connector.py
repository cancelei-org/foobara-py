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
