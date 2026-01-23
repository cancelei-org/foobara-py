"""Tests for Registry module"""

import pytest
from pydantic import BaseModel
from foobara_py.core.registry import (
    CommandRegistry,
    DomainRegistry,
    TypeRegistry,
    get_default_registry,
    register
)
from foobara_py.core.command import Command


class TestInputs(BaseModel):
    value: int


class TestCommand(Command[TestInputs, int]):
    """Test command"""

    def execute(self) -> int:
        return self.inputs.value


class TestCommandRegistry:
    def test_register_command(self):
        registry = CommandRegistry("test")
        registry.register(TestCommand)
        assert registry.get("TestCommand") is not None

    def test_execute_command(self):
        registry = CommandRegistry("test2")
        registry.register(TestCommand)
        outcome = registry.execute("TestCommand", {"value": 42})
        assert outcome.is_success()
        assert outcome.unwrap() == 42

    def test_list_commands(self):
        registry = CommandRegistry("test3")
        registry.register(TestCommand)
        commands = registry.list_commands()
        assert len(commands) == 1
        assert commands[0] == TestCommand

    def test_list_tools(self):
        registry = CommandRegistry("test4")
        registry.register(TestCommand)
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "TestCommand"
        assert "inputSchema" in tools[0]

    def test_get_manifest(self):
        registry = CommandRegistry("test5")
        registry.register(TestCommand)
        manifest = registry.get_manifest()
        assert manifest["registry"] == "test5"
        assert "TestCommand" in manifest["commands"]

    def test_command_not_found(self):
        registry = CommandRegistry("test6")
        with pytest.raises(KeyError):
            registry.execute("NonExistent", {})


class TestDomainRegistry:
    def test_register_command(self):
        domain = DomainRegistry("TestDomain")
        domain.register(TestCommand)
        assert domain.get_command("TestCommand") is not None

    def test_register_type(self):
        domain = DomainRegistry("TestDomain2")

        class User(BaseModel):
            id: int
            name: str

        domain.register_type("User", User)
        assert "User" in domain._types

    def test_list_commands(self):
        domain = DomainRegistry("TestDomain3")
        domain.register(TestCommand)
        commands = domain.list_commands()
        assert len(commands) == 1

    def test_manifest(self):
        domain = DomainRegistry("TestDomain4", organization="Org")
        domain.register(TestCommand)
        manifest = domain.get_manifest()
        assert manifest["name"] == "TestDomain4"
        assert manifest["organization"] == "Org"


class TestTypeRegistry:
    def test_register_type(self):
        registry = TypeRegistry()

        class User(BaseModel):
            id: int

        registry.register("User", User)
        assert registry.get("User") == User

    def test_get_schema(self):
        registry = TypeRegistry()

        class User(BaseModel):
            id: int
            name: str

        registry.register("User", User)
        schema = registry.get_schema("User")
        assert "properties" in schema
        assert "id" in schema["properties"]

    def test_list_types(self):
        registry = TypeRegistry()

        class Type1(BaseModel):
            x: int

        class Type2(BaseModel):
            y: str

        registry.register("Type1", Type1)
        registry.register("Type2", Type2)
        types = registry.list_types()
        assert "Type1" in types
        assert "Type2" in types


class TestRegisterDecorator:
    def test_register_decorator(self):
        @register
        class RegisteredCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return 1

        default_registry = get_default_registry()
        assert default_registry.get("RegisteredCommand") is not None
